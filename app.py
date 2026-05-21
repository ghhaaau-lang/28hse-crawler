import os
import re
import json
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TEST_FAKE_LISTING = os.environ.get("TEST_FAKE_LISTING", "0") == "1"

LOCAL_PROCESSED_FILE = "processed_ids.json"


def load_processed_ids():
    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已讀取 processed_ids：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ processed_ids.json 讀取失敗：{e}")

    print("ℹ️ 尚無 processed_ids 記錄，將視為第一次執行。")
    return set()


def save_processed_ids(processed_ids):
    try:
        with open(LOCAL_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(list(processed_ids))}, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存 processed_ids：{len(processed_ids)} 筆")
    except Exception as e:
        print(f"❌ processed_ids.json 保存失敗：{e}")


def send_discord_message(message_text):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL，請檢查 GitHub Secrets")
        return False

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message_text},
            timeout=15
        )

        if response.status_code in [200, 204]:
            print("✨ [Discord] 訊息發送成功")
            return True
        else:
            print(f"❌ [Discord] 發送失敗，狀態碼：{response.status_code}")
            print(f"❌ 回應內容：{response.text}")
            return False

    except Exception as e:
        print(f"❌ [Discord] 連線失敗：{e}")
        return False


def crawl_28hse():
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
        print(f"📄 28hse HTML 長度：{len(res.text)}")

        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # 測試用：把所有含 item-數字 的連結先抓出來
        items = soup.find_all("a", href=re.compile(r"item-\d+"))

        print(f"🏠 28hse 抓到 item 連結：{len(items)} 筆")

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
                    title = "28hse 業主盤"

                listings.append({
                    "id": house_id,
                    "title": f"[28hse] {title[:80]}",
                    "link": link
                })

            except Exception as e:
                print(f"⚠️ 28hse 單筆解析失敗：{e}")

    except Exception as e:
        print(f"❌ 28hse 抓取失敗：{e}")

    return listings


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = []

    # 只測 28hse，先停用 House730
    all_listings.extend(crawl_28hse())

    # 假新盤測試
    if TEST_FAKE_LISTING:
        print("🧪 TEST_FAKE_LISTING=1，加入假新盤測試")
        all_listings.append({
            "id": "test_fake_listing_001",
            "title": "[測試] 太子 2房 業主盤",
            "link": "https://example.com/test-listing"
        })

    print(f"📦 總共抓到：{len(all_listings)} 筆")

    new_listings = [h for h in all_listings if h["id"] not in processed_ids]
    print(f"🆕 新樓盤：{len(new_listings)} 筆")

    if new_listings:
        msg = f"🏠 **【最新業主盤測試】新發現 {len(new_listings)} 筆**\n"
        msg += "-------------------------\n"

        for i, house in enumerate(new_listings, 1):
            msg += f"**{i}. {house['title']}**\n"
            msg += f"🔗 詳情：{house['link']}\n"
            msg += "-------------------------\n"
            processed_ids.add(house["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed_ids")

    else:
        print("沒有新樓盤更新。")
