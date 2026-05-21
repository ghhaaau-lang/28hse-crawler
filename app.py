import os
import re
import json
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_owner_ids.json"

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
                print(f"✅ 已讀取 {LOCAL_PROCESSED_FILE}：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ {LOCAL_PROCESSED_FILE} 讀取失敗：{e}")

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
        print(f"❌ {LOCAL_PROCESSED_FILE} 保存失敗：{e}")


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

        # 第一層：要求 28hse 回業主類型
        "owner_type": "1",
    }


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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
    超嚴格業主版：
    只有卡片文字明確出現 業主 / 免佣 / 自讓 / 直接業主，才通知。
    其他全部跳過。
    """
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    print(f"🔗 resultContentHtml a[href] 數量：{len(links)}")

    owner_keywords = [
        "業主",
        "業主盤",
        "直接業主",
        "自讓",
        "免佣",
        "免佣金",
        "放租免佣",
        "業主放盤",
        "業主自讓",
        "owner",
        "no commission",
    ]

    agent_keywords = [
        "代理",
        "地產",
        "經紀",
        "中介",
        "agency",
        "agent",
        "分行",
    ]

    listings = {}
    skipped_not_owner = 0
    skipped_agent = 0

    for a in links:
        raw_href = a.get("href", "")
        href = normalize_link(raw_href)
        text = clean_text(a.get_text(" ", strip=True))

        match = re.search(r"/rent/apartment/property-(\d+)", href)

        if not match:
            continue

        property_id = match.group(1)
        house_id = f"28hse_{property_id}"

        # 找外層卡片，盡量拿整張卡片文字判斷
        card = (
            a.find_parent("div", class_=re.compile(r"(result|property|listing|item|estate|search|content)", re.I))
            or a.find_parent("div")
        )

        card_text = clean_text(card.get_text(" ", strip=True)) if card else text
        card_text_lower = card_text.lower()

        has_owner_keyword = any(k.lower() in card_text_lower for k in owner_keywords)
        has_agent_keyword = any(k.lower() in card_text_lower for k in agent_keywords)

        if has_agent_keyword:
            skipped_agent += 1
            print(f"🚫 排除房仲/代理盤：{property_id} | {card_text[:100]}")
            continue

        if not has_owner_keyword:
            skipped_not_owner += 1
            print(f"⚠️ 跳過非明確業主盤：{property_id} | {card_text[:100]}")
            continue

        # 標題優先用 a text，太短就用卡片文字
        title = text

        if len(title) <= 2:
            title = card_text

        title = clean_text(title)

        if not title:
            title = "28hse 業主盤"

        if house_id not in listings:
            listings[house_id] = {
                "id": house_id,
                "title": f"[28hse業主] {title[:90]}",
                "link": href,
            }
        else:
            old_title = listings[house_id]["title"]
            new_title = f"[28hse業主] {title[:90]}"

            if len(new_title) > len(old_title):
                listings[house_id]["title"] = new_title

    final = list(listings.values())

    print(f"🚫 排除房仲/代理盤：{skipped_agent} 次")
    print(f"⚠️ 跳過非明確業主盤：{skipped_not_owner} 次")
    print(f"✅ 超嚴格業主盤解析到：{len(final)} 筆")

    for i, item in enumerate(final[:10], 1):
        print(f"owner sample {i}: {item['title']} | {item['link']}")

    return final


def crawl_28hse_dosearch():
    session = requests.Session()
    headers = get_headers()
    params = build_params()

    print("🚀 28hse /property/dosearch 超嚴格業主版 started")

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

    print(f"📦 總共抓到明確業主樓盤：{len(all_listings)} 筆")

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

    print(f"🆕 新明確業主樓盤：{len(new_listings)} 筆")

    if new_listings:
        msg = f"🏠 **【28hse 明確業主盤通知】新發現 {len(new_listings)} 筆**\n"
        msg += "-------------------------\n"

        for i, house in enumerate(new_listings, 1):
            msg += f"**{i}. {house['title']}**\n"
            msg += f"🔗 詳情：{house['link']}\n"
            msg += "-------------------------\n"
            processed_ids.add(house["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆明確業主盤至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids，避免漏通知")

    else:
        print("沒有新的明確業主樓盤更新。")
