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


def send_discord_message(message_text):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL")
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

        print(f"❌ [Discord] 發送失敗：{response.status_code}")
        print(response.text[:500])
        return False

    except Exception as e:
        print(f"❌ [Discord] 連線失敗：{e}")
        return False


def load_processed_ids():
    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已讀取 processed_ids：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ processed_ids.json 讀取失敗：{e}")

    print("ℹ️ 尚無 processed_ids 記錄")
    return set()


def save_processed_ids(processed_ids):
    try:
        with open(LOCAL_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(list(processed_ids))}, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存 processed_ids：{len(processed_ids)} 筆")
    except Exception as e:
        print(f"❌ processed_ids.json 保存失敗：{e}")


def extract_links_from_text(text):
    links = set()

    patterns = [
        r"https?://www\.28hse\.com/rent/apartment/item-\d+[^\"'<\s]*",
        r"/rent/apartment/item-\d+[^\"'<\s]*",
        r"rent/apartment/item-\d+[^\"'<\s]*",
        r"item-\d+",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text):
            match = match.replace("\\/", "/")

            if match.startswith("http"):
                link = match
            elif match.startswith("/"):
                link = BASE + match
            elif match.startswith("rent/"):
                link = BASE + "/" + match
            elif match.startswith("item-"):
                link = BASE + "/rent/apartment/" + match
            else:
                continue

            links.add(link)

    return sorted(links)


def parse_json_for_items(data):
    """
    嘗試從 JSON 裡面找 item id / url / title。
    因為未知格式，先用遞迴掃所有欄位。
    """
    results = []

    def walk(obj):
        if isinstance(obj, dict):
            # 常見欄位猜測
            possible_id = (
                obj.get("id")
                or obj.get("item_id")
                or obj.get("itemId")
                or obj.get("property_id")
                or obj.get("propertyId")
            )

            possible_url = (
                obj.get("url")
                or obj.get("link")
                or obj.get("href")
                or obj.get("detail_url")
                or obj.get("detailUrl")
            )

            possible_title = (
                obj.get("title")
                or obj.get("name")
                or obj.get("subject")
                or obj.get("estate_name")
                or obj.get("building_name")
                or obj.get("addr")
            )

            if possible_id or possible_url:
                text_blob = json.dumps(obj, ensure_ascii=False)

                id_match = re.search(r"item-(\d+)", text_blob)
                if id_match:
                    item_id = id_match.group(1)
                    link = BASE + f"/rent/apartment/item-{item_id}"
                    title = possible_title or "28hse 業主盤"

                    results.append({
                        "id": f"28hse_{item_id}",
                        "title": f"[28hse] {str(title)[:80]}",
                        "link": link
                    })

            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(data)

    # 去重
    unique = {}
    for item in results:
        unique[item["id"]] = item

    return list(unique.values())


def parse_response_to_listings(response_text):
    listings = []

    # 1. 先試 JSON
    try:
        data = json.loads(response_text)
        print("✅ 回應可解析為 JSON")

        print("JSON 頂層型態：", type(data).__name__)

        if isinstance(data, dict):
            print("JSON 頂層 keys：", list(data.keys())[:30])

        json_items = parse_json_for_items(data)
        print(f"🧩 從 JSON 嘗試解析到：{len(json_items)} 筆")
        listings.extend(json_items)

    except Exception:
        print("ℹ️ 回應不是純 JSON，改用 HTML / text 解析")

    # 2. 再用全文 link regex
    links = extract_links_from_text(response_text)
    print(f"🔗 從回應文字抓到 item link：{len(links)} 條")

    for link in links:
        id_match = re.search(r"item-(\d+)", link)
        if not id_match:
            continue

        item_id = id_match.group(1)

        listings.append({
            "id": f"28hse_{item_id}",
            "title": "[28hse] 業主盤",
            "link": link
        })

    # 3. 去重
    unique = {}
    for item in listings:
        unique[item["id"]] = item

    return list(unique.values())


def build_params():
    """
    從之前 form 抓到的欄位整理出基本查詢參數。
    """
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


def test_dosearch():
    session = requests.Session()
    headers = get_headers()
    params = build_params()

    print("🚀 28hse /property/dosearch Test started")

    # 先打一次搜尋頁，建立 session cookies
    first = session.get(SEARCH_PAGE, headers={
        **headers,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }, timeout=20)

    print(f"🔎 搜尋頁狀態碼：{first.status_code}")
    print(f"📄 搜尋頁 HTML 長度：{len(first.text)}")
    print(f"🍪 cookies 數量：{len(session.cookies)}")

    all_listings = []

    tests = [
        ("GET params", "get", params),
        ("POST form", "post", params),
        ("POST json", "post_json", params),
    ]

    for test_name, method, payload in tests:
        print(f"\n========== 測試 {test_name} ==========")

        try:
            if method == "get":
                r = session.get(DOSEARCH_URL, headers=headers, params=payload, timeout=20)
            elif method == "post":
                r = session.post(DOSEARCH_URL, headers=headers, data=payload, timeout=20)
            else:
                r = session.post(DOSEARCH_URL, headers=headers, json=payload, timeout=20)

            print(f"狀態碼：{r.status_code}")
            print(f"URL：{r.url}")
            print(f"回應長度：{len(r.text)}")
            print(f"Content-Type：{r.headers.get('content-type')}")
            print("回應前 500 字：")
            print(r.text[:500].replace("\n", " ")[:500])

            listings = parse_response_to_listings(r.text)
            print(f"✅ {test_name} 解析後：{len(listings)} 筆")

            all_listings.extend(listings)

        except Exception as e:
            print(f"❌ {test_name} 測試失敗：{e}")

    unique = {}
    for item in all_listings:
        unique[item["id"]] = item

    final = list(unique.values())
    print(f"\n🎯 /property/dosearch 最終整理：{len(final)} 筆")

    return final


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = test_dosearch()

    print(f"📦 總共抓到：{len(all_listings)} 筆")

    new_listings = [x for x in all_listings if x["id"] not in processed_ids]
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
