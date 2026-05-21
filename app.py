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


def parse_result_content_html(html):
    listings = []
    soup = BeautifulSoup(html, "html.parser")

    print(f"🧩 resultContentHtml 長度：{len(html)}")

    # 先看 HTML 裡有什麼 href
    links = soup.find_all("a", href=True)
    print(f"🔗 resultContentHtml a[href] 數量：{len(links)}")

    sample_count = 0
    for a in links:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        if sample_count < 20:
            print(f"href sample {sample_count + 1}: {href} | text={text[:80]}")
            sample_count += 1

        full_link = normalize_link(href)

        # 28hse 可能不是 item-，也可能是 property- / rent/apartment
        if not any(k in full_link.lower() for k in ["item-", "property", "rent", "apartment"]):
            continue

        id_match = re.search(r"(?:item-|property-|id=)(\d+)", full_link)

        if id_match:
            item_id = id_match.group(1)
        else:
            # 沒有明確 ID 就用 link 當 ID
            item_id = re.sub(r"\W+", "_", full_link)[-80:]

        title = text or "28hse 業主盤"

        # 過濾太短或無意義 title
        if len(title) < 2:
            title = "28hse 業主盤"

        listings.append({
            "id": f"28hse_{item_id}",
            "title": f"[28hse] {title[:90]}",
            "link": full_link
        })

    # 備援：全文 regex 找 URL / item
    regex_patterns = [
        r"https?://www\.28hse\.com/[^\"'<>\s]+",
        r"/rent/[^\"'<>\s]+",
        r"/property/[^\"'<>\s]+",
        r"item-\d+",
    ]

    for pattern in regex_patterns:
        for match in re.findall(pattern, html):
            link = normalize_link(match)
            id_match = re.search(r"(?:item-|property-|id=)(\d+)", link)

            if id_match:
                item_id = id_match.group(1)
            else:
                item_id = re.sub(r"\W+", "_", link)[-80:]

            if any(k in link.lower() for k in ["item-", "property", "rent", "apartment"]):
                listings.append({
                    "id": f"28hse_{item_id}",
                    "title": "[28hse] 業主盤",
                    "link": link
                })

    # 去重
    unique = {}
    for item in listings:
        unique[item["id"]] = item

    final = list(unique.values())
    print(f"✅ 從 resultContentHtml 解析到：{len(final)} 筆")

    return final


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


def crawl_28hse_dosearch():
    session = requests.Session()
    headers = get_headers()
    params = build_params()

    print("🚀 28hse /property/dosearch 正式解析 started")

    first = session.get(
        SEARCH_PAGE,
        headers={
            **headers,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20
    )

    print(f"🔎 搜尋頁狀態碼：{first.status_code}")
    print(f"📄 搜尋頁 HTML 長度：{len(first.text)}")
    print(f"🍪 cookies 數量：{len(session.cookies)}")

    r = session.get(DOSEARCH_URL, headers=headers, params=params, timeout=20)

    print(f"🔎 dosearch 狀態碼：{r.status_code}")
    print(f"📄 dosearch 回應長度：{len(r.text)}")
    print(f"Content-Type：{r.headers.get('content-type')}")

    if r.status_code != 200:
        print(r.text[:1000])
        return []

    try:
        data = r.json()
        print("✅ dosearch 回應可解析為 JSON")
        print("JSON 頂層 keys：", list(data.keys())[:30])

        result_html = extract_result_html_from_json(data)

        if not result_html:
            print("⚠️ 沒拿到 resultContentHtml，印出 JSON 前 1000 字：")
            print(json.dumps(data, ensure_ascii=False)[:1000])
            return []

        return parse_result_content_html(result_html)

    except Exception as e:
        print(f"❌ JSON 解析失敗：{e}")
        print(r.text[:1000])
        return []


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_28hse_dosearch()

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
