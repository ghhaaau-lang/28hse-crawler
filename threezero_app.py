import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_threezero_ids.json"

BASE = "https://www.threezero.com.hk"
START_URL = "https://www.threezero.com.hk/"


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": BASE,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_processed_ids():
    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已讀取 {LOCAL_PROCESSED_FILE}：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ 讀取 {LOCAL_PROCESSED_FILE} 失敗：{e}")

    print(f"ℹ️ 尚無 {LOCAL_PROCESSED_FILE}，將視為第一次執行")
    return set()


def save_processed_ids(processed_ids):
    try:
        with open(LOCAL_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"ids": sorted(list(processed_ids))},
                f,
                ensure_ascii=False,
                indent=2
            )
        print(f"✅ 已保存 {LOCAL_PROCESSED_FILE}：{len(processed_ids)} 筆")
    except Exception as e:
        print(f"❌ 保存 {LOCAL_PROCESSED_FILE} 失敗：{e}")


def send_discord_message(message_text):
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
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": chunk},
                timeout=15
            )

            if response.status_code in [200, 204]:
                print(f"✨ [Discord] 第 {index}/{len(chunks)} 段訊息發送成功")
                success_count += 1
            else:
                print(f"❌ [Discord] 發送失敗：{response.status_code}")
                print(response.text[:500])

        except Exception as e:
            print(f"❌ [Discord] 連線失敗：{e}")

    return success_count == len(chunks)


def parse_threezero_listings(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    print(f"🔗 threezero a[href] 數量：{len(links)}")

    listings = {}

    for a in links:
        href = a.get("href", "")
        full_link = urljoin(page_url, href)
        text = clean_text(a.get_text(" ", strip=True))

        if "/singleproperty/" not in full_link:
            continue

        # 排除外站或不相關
        if "threezero.com.hk" not in full_link:
            continue

        # 用 URL slug 當 ID
        slug = full_link.rstrip("/").split("/singleproperty/")[-1]
        if not slug:
            continue

        house_id = f"threezero_{slug}"

        # 標題與描述通常在 a text 裡
        title = text or "threezero 租盤"

        # 過濾太短或無意義
        if len(title) < 3:
            title = "threezero 租盤"

        listings[house_id] = {
            "id": house_id,
            "title": f"[threezero免佣] {title[:120]}",
            "link": full_link,
        }

    final = list(listings.values())

    print(f"✅ threezero 解析到租盤：{len(final)} 筆")

    for i, item in enumerate(final[:10], 1):
        print(f"sample {i}: {item['title']} | {item['link']}")

    return final


def crawl_threezero():
    print("🚀 threezero 正式版 started")

    session = requests.Session()
    headers = get_headers()

    try:
        response = session.get(START_URL, headers=headers, timeout=20)

        print(f"🔎 threezero 狀態碼：{response.status_code}")
        print(f"📄 HTML 長度：{len(response.text)}")
        print(f"Final URL：{response.url}")

        if response.status_code != 200:
            print(response.text[:1000])
            return []

        return parse_threezero_listings(response.text, response.url)

    except Exception as e:
        print(f"❌ threezero 抓取失敗：{e}")
        return []


if __name__ == "__main__":
    print("🚀 threezero Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_threezero()

    print(f"📦 總共抓到 threezero 租盤：{len(all_listings)} 筆")

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

    print(f"🆕 threezero 新租盤：{len(new_listings)} 筆")

    if new_listings:
        msg = f"🏠 **【threezero 免佣租盤通知】新發現 {len(new_listings)} 筆**\n"
        msg += "-------------------------\n"

        for i, house in enumerate(new_listings, 1):
            msg += f"**{i}. {house['title']}**\n"
            msg += f"🔗 詳情：{house['link']}\n"
            msg += "-------------------------\n"
            processed_ids.add(house["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆 threezero 租盤至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("沒有新的 threezero 租盤更新。")
