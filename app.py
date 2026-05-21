import os
import requests
import json
import re
from bs4 import BeautifulSoup

# 🎯 雲端大腦：讀寫 Redis / KV 資料庫
KV_URL = os.environ.get("KV_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
FORCE_DISCORD_TEST = os.environ.get("FORCE_DISCORD_TEST", "0") == "1"


def load_processed_ids():
    if not KV_URL:
        print("⚠️ 沒有設定 KV_URL，這次只用本次記憶，不會保存已處理樓盤。")
        return set()

    try:
        response = requests.get(f"{KV_URL}/processed_ids", timeout=10)
        if response.status_code == 200:
            ids = response.json().get("ids", [])
            print(f"✅ 已讀取 processed_ids：{len(ids)} 筆")
            return set(ids)
        else:
            print(f"⚠️ 讀取 KV 失敗，狀態碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 讀取 KV 發生錯誤：{e}")

    return set()


def save_processed_ids(processed_ids):
    if not KV_URL:
        print("⚠️ 沒有 KV_URL，略過保存 processed_ids。")
        return

    try:
        payload = {"ids": list(processed_ids)}
        response = requests.post(f"{KV_URL}/processed_ids", json=payload, timeout=10)

        if response.status_code in [200, 201, 204]:
            print(f"✅ 已保存 processed_ids：{len(processed_ids)} 筆")
        else:
            print(f"⚠️ 保存 KV 失敗，狀態碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 保存 KV 發生錯誤：{e}")


def send_discord_message(message_text):
    """🚀 直連 Discord Webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL 環境變數")
        return False

    # Discord content 上限約 2000 字，保守切 1800
    chunks = []
    text = message_text

    while len(text) > 1800:
        cut = text.rfind("\n", 0, 1800)
        if cut == -1:
            cut = 1800
        chunks.append(text[:cut])
        text = text[cut:].strip()

    if text:
        chunks.append(text)

    success_count = 0

    for idx, chunk in enumerate(chunks, 1):
        payload = {"content": chunk}

        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)

            if response.status_code in [200, 204]:
                print(f"✨ [Discord] 第 {idx}/{len(chunks)} 段訊息發送成功！")
                success_count += 1
            else:
                print(f"❌ [Discord] 發送失敗，狀態碼: {response.status_code}")
                print(f"❌ 回應內容: {response.text}")

        except Exception as e:
            print(f"❌ [Discord] 連線失敗: {str(e)}")

    return success_count == len(chunks)


def crawl_28hse():
    """28hse 業主自讓盤"""
    url = "https://www.28hse.com/rent/apartment?owner_type=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    listings = []

    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"🔎 28hse 狀態碼：{res.status_code}")

        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.find_all("a", href=re.compile(r"/rent/apartment/item-\d+"))

        print(f"🏠 28hse 抓到原始項目：{len(items)} 筆")

        for item in items:
            try:
                title = item.text.strip().split("\n")[0]
                link = item["href"]

                if not link.startswith("http"):
                    link = f"https://www.28hse.com{link}"

                id_match = re.search(r"item-(\d+)", link)
                house_id = f"28hse_{id_match.group(1)}" if id_match else f"28hse_{link}"

                if title:
                    listings.append({
                        "id": house_id,
                        "title": f"[28hse] {title}",
                        "link": link
                    })

            except Exception as e:
                print(f"⚠️ 28hse 單筆解析失敗：{e}")
                continue

    except Exception as e:
        print(f"❌ 28hse 抓取失敗：{e}")

    return listings


def crawl_house730():
    """House730 業主自讓盤"""
    url = "https://www.house730.com/rent/o1/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    listings = []

    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"🔎 House730 狀態碼：{res.status_code}")

        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.find_all("a", href=re.compile(r"/rent-property-\d+/"))

        print(f"🏠 House730 抓到原始項目：{len(items)} 筆")

        for item in items:
            try:
                title_el = item.find("div", class_="title") or item.find("h3")
                title = title_el.text.strip() if title_el else "精選業主自讓盤"

                link = item["href"]

                if not link.startswith("http"):
                    link = f"https://www.house730.com{link}"

                id_match = re.search(r"property-(\d+)", link)
                house_id = f"730_{id_match.group(1)}" if id_match else f"730_{link}"

                if not any(x["id"] == house_id for x in listings):
                    listings.append({
                        "id": house_id,
                        "title": f"[House730] {title}",
                        "link": link
                    })

            except Exception as e:
                print(f"⚠️ House730 單筆解析失敗：{e}")
                continue

    except Exception as e:
        print(f"❌ House730 抓取失敗：{e}")

    return listings


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取，請檢查 GitHub Secrets")

    if KV_URL:
        print("✅ KV_URL 已讀取")
    else:
        print("⚠️ KV_URL 未設定，會影響去重保存")

    # ✅ 強制測試 Discord 通知
    if FORCE_DISCORD_TEST:
        send_discord_message("✅ GitHub Actions 測試通知成功，Discord Webhook 已接通")
        print("🧪 FORCE_DISCORD_TEST=1，測試通知已執行")

    processed_ids = load_processed_ids()

    all_listings = crawl_28hse() + crawl_house730()
    print(f"📦 雙源總共抓到：{len(all_listings)} 筆")

    new_listings = [h for h in all_listings if h["id"] not in processed_ids]
    print(f"🆕 新樓盤：{len(new_listings)} 筆")

    if new_listings:
        msg_content = (
            f"🏠 **【最新業主盤雙源聯防】新發現 {len(new_listings)} 筆**\n"
            f"-------------------------\n"
        )

        for i, house in enumerate(new_listings, 1):
            msg_content += (
                f"**{i}. {house['title']}**\n"
                f"🔗 詳情: {house['link']}\n"
                f"-------------------------\n"
            )
            processed_ids.add(house["id"])

        ok = send_discord_message(msg_content)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆全新雙源資料至 Discord！")
        else:
            print("⚠️ Discord 發送沒有完全成功，暫不保存 processed_ids，避免漏通知。")

    else:
        print("雙源均無新樓盤更新。")
