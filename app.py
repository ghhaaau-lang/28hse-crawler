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

        print(f"❌ [Discord] 發送失敗，狀態碼：{response.status_code}")
        print(f"❌ 回應內容：{response.text}")
        return False

    except Exception as e:
        print(f"❌ [Discord] 連線失敗：{e}")
        return False


def clean_title(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return "28hse 業主盤"
    return text[:90]


def normalize_28hse_link(link):
    if not link:
        return ""

    # 有些 href 可能是 escaped slash
    link = link.replace("\\/", "/")

    if link.startswith("http"):
        return link

    if link.startswith("/"):
        return "https://www.28hse.com" + link

    return "https://www.28hse.com/" + link


def crawl_28hse():
    """
    28hse 修正版：
    1. 先抓 HTML 裡所有 a[href]
    2. 再用全文 regex 抓所有可能的 item-數字連結
    3. 自動去重
    """
    url = "https://www.28hse.com/rent/apartment?owner_type=1"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en-US;q=0.7,en;q=0.6",
        "Referer": "https://www.28hse.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    listings = []
    seen_ids = set()

    try:
        res = requests.get(url, headers=headers, timeout=20)
        print(f"🔎 28hse 狀態碼：{res.status_code}")
        print(f"📄 28hse HTML 長度：{len(res.text)}")

        if res.status_code != 200:
            print("❌ 28hse 讀取失敗，非 200。")
            return []

        html = res.text
        soup = BeautifulSoup(html, "html.parser")

        # =========================
        # 方法 1：從 a[href] 抓 item
        # =========================
        all_a_tags = soup.find_all("a", href=True)
        print(f"🔗 28hse 全部 a href 數量：{len(all_a_tags)}")

        href_item_tags = []

        for a in all_a_tags:
            href = a.get("href", "")
            if "item-" in href:
                href_item_tags.append(a)

        print(f"🏠 28hse a[href] 含 item- 數量：{len(href_item_tags)}")

        for a in href_item_tags:
            try:
                raw_link = a.get("href", "")
                link = normalize_28hse_link(raw_link)

                id_match = re.search(r"item-(\d+)", link)
                if not id_match:
                    continue

                house_id = f"28hse_{id_match.group(1)}"

                if house_id in seen_ids:
                    continue

                seen_ids.add(house_id)

                title = clean_title(a.get_text(" ", strip=True))

                listings.append({
                    "id": house_id,
                    "title": f"[28hse] {title}",
                    "link": link
                })

            except Exception as e:
                print(f"⚠️ 28hse a[href] 單筆解析失敗：{e}")

        # =========================
        # 方法 2：全文 regex 備援抓 link
        # =========================
        regex_links = set()

        patterns = [
            r'https?:\\?/\\?/www\.28hse\.com\\?/rent\\?/apartment\\?/item-\d+[^"\'<\s]*',
            r'https?://www\.28hse\.com/rent/apartment/item-\d+[^"\'<\s]*',
            r'/rent/apartment/item-\d+[^"\'<\s]*',
            r'rent/apartment/item-\d+[^"\'<\s]*',
        ]

        for pattern in patterns:
            for match in re.findall(pattern, html):
                link = match.replace("\\/", "/")
                link = normalize_28hse_link(link)
                regex_links.add(link)

        print(f"🧩 28hse regex 備援抓到 link：{len(regex_links)} 條")

        for link in regex_links:
            try:
                id_match = re.search(r"item-(\d+)", link)
                if not id_match:
                    continue

                house_id = f"28hse_{id_match.group(1)}"

                if house_id in seen_ids:
                    continue

                seen_ids.add(house_id)

                listings.append({
                    "id": house_id,
                    "title": "[28hse] 業主盤",
                    "link": link
                })

            except Exception as e:
                print(f"⚠️ 28hse regex 單筆解析失敗：{e}")

        # =========================
        # Debug：如果還是 0 筆，印出前幾個 href 看結構
        # =========================
        if not listings:
            print("⚠️ 28hse 仍然抓到 0 筆，印出前 20 個 href 供檢查：")
            for i, a in enumerate(all_a_tags[:20], 1):
                print(f"href sample {i}: {a.get('href', '')}")

            # 同時檢查 HTML 裡有沒有 item- 字樣
            if "item-" in html:
                print("ℹ️ HTML 裡有 item-，但目前規則沒抓到，可能是 escaped 或路徑格式不同。")
            else:
                print("ℹ️ HTML 裡完全沒有 item-，可能資料是 JS/API 動態載入。")

    except Exception as e:
        print(f"❌ 28hse 抓取失敗：{e}")

    print(f"✅ 28hse 最終整理後：{len(listings)} 筆")
    return listings


if __name__ == "__main__":
    print("🚀 28hse Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = []

    # 只跑 28hse，先不跑 House730
    all_listings.extend(crawl_28hse())

    # 假新盤測試：需要時才開
    if TEST_FAKE_LISTING:
        print("🧪 TEST_FAKE_LISTING=1，加入假新盤測試")
        all_listings.append({
            "id": "test_fake_listing_002",
            "title": "[測試] 28hse 修正版測試盤",
            "link": "https://example.com/test-28hse"
        })

    print(f"📦 總共抓到：{len(all_listings)} 筆")

    new_listings = [h for h in all_listings if h["id"] not in processed_ids]
    print(f"🆕 新樓盤：{len(new_listings)} 筆")

    if new_listings:
        msg = f"🏠 **【28hse 業主盤通知】新發現 {len(new_listings)} 筆**\n"
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
