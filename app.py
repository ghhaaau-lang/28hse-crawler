import os
import re
import json
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_ids.json"

BASE = "https://www.28hse.com"
SEARCH_PAGE = "https://www.28hse.com/rent/apartment?owner_type=1"
DOSEARCH_URL = "https://www.28hse.com/property/dosearch"


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": SEARCH_PAGE,
        "Origin": BASE,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def load_processed_ids():
    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已讀取 processed_ids：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ processed_ids.json 讀取失敗：{e}")

    print("ℹ️ 尚無 processed_ids 記錄，將視為第一次執行")
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
        print(f"✅ 已保存 processed_ids：{len(processed_ids)} 筆")
    except Exception as e:
        print(f"❌ processed_ids.json 保存失敗：{e}")


def send_discord_message(message_text):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL，請檢查 GitHub Secrets")
        return False

    # Discord 單則 content 約 2000 字，保守切 1800
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


def build_params():
    return {
        "page": "1",
        "searchText": "",
        "myfav": "",
        "myvisited": "",
        "item_ids": "",
        "sortBy": "default",
        "is_grid_mode": "",
        "search_words_thing": "default",
        "buyRent": "rent",
        "mobilePageChannel": "apartment",
        "cat_ids": "",
        "search_words_value": "",
        "is_return_newmenu": "",
        "plan_id": "",
        "propertyDoSearchVersion": "2.0",
        "locations": "",
        "locations_by_text": "0",
        "mainType": "5",
        "mainType_by_text": "0",
        "otherRentalShortCut": "",
        "otherRentalShortCut_by_text": "0",
        "price": "",
        "price_by_text": "0",
        "areaOption": "",
        "areaOption_by_text": "0",
        "areaRange": "",
        "areaRange_by_text": "0",
        "roomRange": "",
        "roomRange_by_text": "0",
        "searchTags": "",
        "searchTags_by_text": "0",
        "others": "",
        "others_by_text": "0",
        "direction": "",
        "direction_by_text": "0",
        "landlordAgency": "",
        "landlordAgency_by_text": "0",
        "yearRange": "",
        "yearRange_by_text": "0",
        "floors": "",
        "floors_by_text": "0",
        "kitchen_type": "",
        "kitchen_type_by_text": "0",
        "developer": "",
        "developer_by_text": "0",
        "more_options": "",
        "more_options_by_text": "0",
        "owner_type": "1",
    }


def clean_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def normalize_link(link):
    if not link:
        return ""

    link = link.replace("\\/", "/").strip()

    if link.startswith("http"):
        return link

    if link.startswith("//"):
        return "https:" + link

    if link.startswith("/"):
        return BASE + link

    return BASE + "/" + link


def extract_result_html_from_json(data):
    paths = [
        ["data", "results", "resultContentHtml"],
        ["result", "resultContentHtml"],
        ["results", "resultContentHtml"],
        ["data", "resultContentHtml"],
    ]

    for path in paths:
        cur = data
        ok = True

        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break

        if ok and isinstance(cur, str) and cur.strip():
            print(f"✅ 找到 resultContentHtml path：{'.'.join(path)}")
            return cur

    print("❌ 找不到 resultContentHtml")
    return ""


def parse_result_content_html(html):
    """
    只保留主樓盤連結：
    https://www.28hse.com/rent/apartment/property-3857733
    """
    soup = BeautifulSoup(html, "html.parser")

    links = soup.find_all("a", href=True)
    print(f"🔗 resultContentHtml a[href] 數量：{len(links)}")

    listings = {}
    current_property_id = None
    current_title_parts = []

    for a in links:
        raw_href = a.get("href", "")
        href = normalize_link(raw_href)
        text = clean_text(a.get_text(" ", strip=True))

        match = re.search(r"/rent/apartment/property-(\d+)", href)

        if not match:
            continue

        property_id = match.group(1)
        house_id = f"28hse_{property_id}"

        # 優先取有文字的 a text 作標題
        if text and len(text) >= 2:
            title = text
        else:
            title = "28hse 業主盤"

        # 同一個 property 可能有多個 a，例如價格、標題、圖片
        # 用第一個有效 title，但如果後面 title 更像樓盤描述，就更新
        if house_id not in listings:
            listings[house_id] = {
                "id": house_id,
                "title": f"[28hse] {title[:90]}",
                "link": href,
            }
        else:
            old_title = listings[house_id]["title"]

            # 過濾太短 title，例如「5」「9」「黃金」
            if len(title) > 6 and len(old_title) < len(f"[28hse] {title}"):
                listings[house_id]["title"] = f"[28hse] {title[:90]}"

    final = list(listings.values())
    print(f"✅ 主樓盤 property 解析到：{len(final)} 筆")

    for i, item in enumerate(final[:10], 1):
        print(f"sample {i}: {item['title']} | {item['link']}")

    return final


def crawl_28hse_dosearch():
    session = requests.Session()
    headers = get_headers()
    params = build_params()

    print("🚀 28hse /property/dosearch 正式版 started")

    # 先打搜尋頁，建立 cookie
    first = session.get(
        SEARCH_PAGE,
        headers={
            **headers,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20
    )

    print(f"🔎 搜尋頁狀態碼：{first.status_code}")
    print(f"🍪 cookies 數量：{len(session.cookies)}")

    response = session.get(
        DOSEARCH_URL,
        headers=headers,
        params=params,
        timeout=20
    )

    print(f"🔎 dosearch 狀態碼：{response.status_code}")
    print(f"📄 dosearch 回應長度：{len(response.text)}")
    print(f"Content-Type：{response.headers.get('content-type')}")

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    try:
        data = response.json()
        print("✅ dosearch 回應可解析為 JSON")
        print("JSON 頂層 keys：", list(data.keys())[:30])
    except Exception as e:
        print(f"❌ JSON 解析失敗：{e}")
        print(response.text[:1000])
        return []

    result_html = extract_result_html_from_json(data)

    if not result_html:
        print("⚠️ 無 resultContentHtml，印出 JSON 前 1000 字")
        print(json.dumps(data, ensure_ascii=False)[:1000])
        return []

    print(f"🧩 resultContentHtml 長度：{len(result_html)}")

    return parse_result_content_html(result_html)


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_28hse_dosearch()

    print(f"📦 總共抓到樓盤：{len(all_listings)} 筆")

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

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
            print("⚠️ Discord 發送失敗，暫不保存 processed_ids，避免漏通知")

    else:
        print("沒有新樓盤更新。")
