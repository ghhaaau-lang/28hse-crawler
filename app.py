import os
import re
import json
import requests
from bs4 import BeautifulSoup

# =========================
# 基本設定
# =========================

KV_URL = os.environ.get("KV_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# 測試用：在 GitHub Actions env 加 TEST_FAKE_LISTING=1，就會塞一筆假新盤測試通知
TEST_FAKE_LISTING = os.environ.get("TEST_FAKE_LISTING", "0") == "1"

LOCAL_PROCESSED_FILE = "processed_ids.json"


# =========================
# 已處理 ID：讀取 / 保存
# =========================

def load_processed_ids():
    """
    優先使用 KV_URL。
    如果沒有 KV_URL，就讀本地 processed_ids.json。
    """
    if KV_URL:
        try:
            response = requests.get(f"{KV_URL}/processed_ids", timeout=10)
            if response.status_code == 200:
                ids = response.json().get("ids", [])
                print(f"✅ 已從 KV 讀取 processed_ids：{len(ids)} 筆")
                return set(ids)
            else:
                print(f"⚠️ KV 讀取失敗，狀態碼：{response.status_code}")
        except Exception as e:
            print(f"⚠️ KV 讀取錯誤：{e}")

    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已從本地檔案讀取 processed_ids：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ 本地 processed_ids.json 讀取失敗：{e}")

    print("ℹ️ 尚無 processed_ids 記錄，將視為第一次執行。")
    return set()


def save_processed_ids(processed_ids):
    """
    優先保存到 KV_URL。
    如果沒有 KV_URL，就保存到本地 processed_ids.json。
    """
    ids_list = sorted(list(processed_ids))

    if KV_URL:
        try:
            payload = {"ids": ids_list}
            response = requests.post(f"{KV_URL}/processed_ids", json=payload, timeout=10)

            if response.status_code in [200, 201, 204]:
                print(f"✅ 已保存 processed_ids 到 KV：{len(ids_list)} 筆")
                return
            else:
                print(f"⚠️ KV 保存失敗，狀態碼：{response.status_code}")
        except Exception as e:
            print(f"⚠️ KV 保存錯誤：{e}")

    try:
        with open(LOCAL_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump({"ids": ids_list}, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存 processed_ids 到本地檔案：{len(ids_list)} 筆")
    except Exception as e:
        print(f"❌ 本地 processed_ids.json 保存失敗：{e}")


# =========================
# Discord 發送
# =========================

def send_discord_message(message_text):
    """
    發送 Discord Webhook。
    Discord 單則 content 上限約 2000 字，這裡保守切 1800 字。
    """
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL，請檢查 GitHub Secrets")
        return False

    chunks = []
    text = message_text.strip()

    while len(text) > 1800:
        cut = text.rfind("\n", 0, 1800)
        if cut == -1:
            cut = 1800
        chunks.append(text[:cut])
        text = text[cut:].strip()

    if text:
        chunks.append(text)

    success_count = 0

    for index, chunk in enumerate(chunks, 1):
        payload = {"content": chunk}

        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)

            if response.status_code in [200, 204]:
                print(f"✨ [Discord] 第 {index}/{len(chunks)} 段訊息發送成功")
                success_count += 1
            else:
                print(f"❌ [Discord] 發送失敗，狀態碼：{response.status_code}")
                print(f"❌ [Discord] 回應內容：{response.text}")

        except Exception as e:
            print(f"❌ [Discord] 連線失敗：{e}")

    return success_count == len(chunks)


# =========================
# 爬蟲：28hse
# =========================

def crawl_28hse():
    """
    28hse 業主自讓盤。
    目前如果抓到 0 筆，可能是頁面改版 / 動態載入。
    """
    url = "https://www.28hse.com/rent/apartment?owner_type=1"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": "https://www.28hse.com/",
    }

    listings = []

    try:
        res = requests.get(url, headers=headers, timeout=15)
        print(f"🔎 28hse 狀態碼：{res.status_code}")

        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # 原本規則
        items = soup.find_all("a", href=re.compile(r"/rent/apartment/item-\d+"))

        # 備援規則：只要 href 有 item-數字 都先抓
        if not items:
            items = soup.find_all("a", href=re.compile(r"item-\d+"))

        print(f"🏠 28hse 抓到原始項目：{len(items)} 筆")

        seen = set()

        for item in items:
            try:
                link = item.get("href", "")
                if not link:
                    continue

                if not link.startswith("http"):
                    link = f"https://www.28hse.com{link}"

                id_match = re.search(r"item-(\d+)", link)
                if not id_match:
                    continue

                house_id = f"28hse_{id_match.group(1)}"

                if house_id in seen:
                    continue
                seen.add(house_id)

                title = item.get_text(" ", strip=True)
                if not title:
                    title = "業主自讓盤"

                listings.append({
                    "id": house_id,
                    "title": f"[28hse] {title[:80]}",
                    "link": link
                })

            except Exception as e:
                print(f"⚠️ 28hse 單筆解析失敗：{e}")
                continue

    except Exception as e:
        print(f"❌ 28hse 抓取失敗：{e}")

    return listings


# =========================
# 爬蟲：House730
# =========================

def crawl_house730():
    """
    House730 租盤。
    若 GitHub Actions 顯示 403，代表網站可能擋雲端 IP。
    """
    url = "https://www.house730.com/rent/o1/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": "https://www.house730.com/",
    }

    listings = []

    try:
        res = requests.get(url, headers=headers, timeout=15)
        print(f"🔎 House730 狀態碼：{res.status_code}")

        if res.status_code != 200:
            print("⚠️ House730 未能正常讀取，可能被 403 擋住。")
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.find_all("a", href=re.compile(r"/rent-property-\d+/"))

        print(f"🏠 House730 抓到原始項目：{len(items)} 筆")

        seen = set()

        for item in items:
            try:
                link = item.get("href", "")
                if not link:
                    continue

                if not link.startswith("http"):
                    link = f"https://www.house730.com{link}"

                id_match = re.search(r"property-(\d+)", link)
                if not id_match:
                    continue

                house_id = f"730_{id_match.group(1)}"

                if house_id in seen:
                    continue
                seen.add(house_id)

                title_el = item.find("div", class_="title") or item.find("h3")
                title = title_el.get_text(" ", strip=True) if title_el else item.get_text(" ", strip=True)

                if not title:
                    title = "House730 租盤"

                listings.append({
                    "id": house_id,
                    "title": f"[House730] {title[:80]}",
                    "link": link
                })

            except Exception as e:
                print(f"⚠️ House730 單筆解析失敗：{e}")
                continue

    except Exception as e:
        print(f"❌ House730 抓取失敗：{e}")

    return listings


# =========================
# 主流程
# =========================

if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取，請檢查 GitHub Secrets")

    if KV_URL:
        print("✅ KV_URL 已讀取，會使用 KV 去重")
    else:
        print("⚠️ KV_URL 未設定，會使用本地 processed_ids.json 去重")

    processed_ids = load_processed_ids()

    all_listings = []

    # 1. 真實爬蟲
    all_listings.extend(crawl_28hse())
    all_listings.extend(crawl_house730())

    # 2. 假新盤測試
    if TEST_FAKE_LISTING:
        print("🧪 TEST_FAKE_LISTING=1，加入假新盤測試")
        all_listings.append({
            "id": "test_fake_listing_001",
            "title": "[測試] 太子 2房 業主盤",
            "link": "https://example.com/test-listing"
        })

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
                f"🔗 詳情：{house['link']}\n"
                f"-------------------------\n"
            )
            processed_ids.add(house["id"])

        ok = send_discord_message(msg_content)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆新資料至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed_ids，避免漏通知")

    else:
        print("雙源均無新樓盤更新。")
