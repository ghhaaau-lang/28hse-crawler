import json
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

OWNER_PROCESSED_FILE = "processed_owner_ids.json"
THREEZERO_PROCESSED_FILE = "processed_threezero_ids.json"

HSE_BASE = "https://www.28hse.com"
HSE_SEARCH_PAGE = "https://www.28hse.com/rent/apartment?owner_type=1"
HSE_DOSEARCH_URL = "https://www.28hse.com/property/dosearch"

THREEZERO_BASE = "https://www.threezero.com.hk"
THREEZERO_START_URL = "https://www.threezero.com.hk/"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_processed_ids(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"Loaded {filename}: {len(ids)} ids")
                return set(ids)
        except Exception as e:
            print(f"Failed to read {filename}: {e}")

    print(f"No {filename}; treating this as the first run")
    return set()


def save_processed_ids(filename, processed_ids):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                {"ids": sorted(list(processed_ids))},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Saved {filename}: {len(processed_ids)} ids")
    except Exception as e:
        print(f"Failed to save {filename}: {e}")


def send_discord_message(message_text):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL is missing. Please check GitHub Secrets.")
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
                timeout=15,
            )

            if response.status_code in [200, 204]:
                print(f"[Discord] Sent chunk {index}/{len(chunks)}")
                success_count += 1
            else:
                print(f"[Discord] Send failed: {response.status_code}")
                print(response.text[:500])

        except Exception as e:
            print(f"[Discord] Connection failed: {e}")

    return success_count == len(chunks)


def hse_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": HSE_SEARCH_PAGE,
        "Origin": HSE_BASE,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def hse_search_params():
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


def normalize_hse_link(link):
    if not link:
        return ""

    link = link.replace("\\/", "/").strip()

    if link.startswith("http"):
        return link
    if link.startswith("//"):
        return "https:" + link
    if link.startswith("/"):
        return HSE_BASE + link
    return HSE_BASE + "/" + link


def extract_hse_result_html(data):
    paths = [
        ["data", "results", "resultContentHtml"],
        ["result", "resultContentHtml"],
        ["results", "resultContentHtml"],
        ["data", "resultContentHtml"],
    ]

    for path in paths:
        cur = data

        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                break
        else:
            if isinstance(cur, str) and cur.strip():
                print(f"Found resultContentHtml path: {'.'.join(path)}")
                return cur

    print("Could not find resultContentHtml")
    return ""


def parse_hse_result_content_html(html):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    print(f"28hse a[href] count: {len(links)}")

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
        href = normalize_hse_link(a.get("href", ""))
        text = clean_text(a.get_text(" ", strip=True))

        match = re.search(r"/rent/apartment/property-(\d+)", href)
        if not match:
            continue

        property_id = match.group(1)
        house_id = f"28hse_{property_id}"

        card = (
            a.find_parent(
                "div",
                class_=re.compile(r"(result|property|listing|item|estate|search|content)", re.I),
            )
            or a.find_parent("div")
        )

        card_text = clean_text(card.get_text(" ", strip=True)) if card else text
        card_text_lower = card_text.lower()

        has_owner_keyword = any(k.lower() in card_text_lower for k in owner_keywords)
        has_agent_keyword = any(k.lower() in card_text_lower for k in agent_keywords)

        if has_agent_keyword:
            skipped_agent += 1
            print(f"Skip agent listing: {property_id} | {card_text[:100]}")
            continue

        if not has_owner_keyword:
            skipped_not_owner += 1
            print(f"Skip non-explicit owner listing: {property_id} | {card_text[:100]}")
            continue

        title = text
        if len(title) <= 2:
            title = card_text

        title = clean_text(title) or "28hse 業主盤"

        existing = listings.get(house_id)
        listing = {
            "id": house_id,
            "title": f"[28hse業主] {title[:90]}",
            "link": href,
        }

        if not existing or len(listing["title"]) > len(existing["title"]):
            listings[house_id] = listing

    final = list(listings.values())

    print(f"Skipped agent listings: {skipped_agent}")
    print(f"Skipped non-explicit owner listings: {skipped_not_owner}")
    print(f"Parsed 28hse owner listings: {len(final)}")

    for i, item in enumerate(final[:10], 1):
        print(f"28hse sample {i}: {item['title']} | {item['link']}")

    return final


def crawl_28hse_dosearch():
    session = requests.Session()
    headers = hse_headers()

    print("28hse crawler started")

    first = session.get(
        HSE_SEARCH_PAGE,
        headers={
            **headers,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20,
    )

    print(f"28hse search status: {first.status_code}")
    print(f"28hse cookies count: {len(session.cookies)}")

    response = session.get(
        HSE_DOSEARCH_URL,
        headers=headers,
        params=hse_search_params(),
        timeout=20,
    )

    print(f"28hse dosearch status: {response.status_code}")
    print(f"28hse dosearch response length: {len(response.text)}")
    print(f"28hse Content-Type: {response.headers.get('content-type')}")

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    try:
        data = response.json()
        print("28hse dosearch response parsed as JSON")
        print("28hse JSON top-level keys:", list(data.keys())[:30])
    except Exception as e:
        print(f"28hse JSON parse failed: {e}")
        print(response.text[:1000])
        return []

    result_html = extract_hse_result_html(data)
    if not result_html:
        print("No 28hse resultContentHtml; JSON preview:")
        print(json.dumps(data, ensure_ascii=False)[:1000])
        return []

    print(f"28hse resultContentHtml length: {len(result_html)}")
    return parse_hse_result_content_html(result_html)


def threezero_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": THREEZERO_BASE,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def normalize_phone_number(value):
    digits = re.sub(r"\D+", "", value or "")

    if digits.startswith("852") and len(digits) == 11:
        digits = digits[3:]

    if re.fullmatch(r"[235689]\d{7}", digits):
        return digits

    return ""


def extract_phone_numbers(html):
    soup = BeautifulSoup(html, "html.parser")
    phones = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if href.lower().startswith("tel:"):
            phone = normalize_phone_number(href)
            if phone:
                phones.add(phone)

    text = soup.get_text(" ", strip=True)
    phone_pattern = re.compile(r"(?:\+?852[\s-]*)?([235689]\d[\s-]*\d{2}[\s-]*\d{4})")

    for match in phone_pattern.finditer(text):
        phone = normalize_phone_number(match.group(1))
        if phone:
            phones.add(phone)

    return sorted(phones)


def parse_threezero_listings(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    print(f"threezero a[href] count: {len(links)}")

    listings = {}

    for a in links:
        full_link = urljoin(page_url, a.get("href", ""))
        text = clean_text(a.get_text(" ", strip=True))

        if "/singleproperty/" not in full_link:
            continue
        if "threezero.com.hk" not in full_link:
            continue

        slug = full_link.rstrip("/").split("/singleproperty/")[-1]
        if not slug:
            continue

        title = text or "threezero 租盤"
        if len(title) < 3:
            title = "threezero 租盤"

        house_id = f"threezero_{slug}"
        listings[house_id] = {
            "id": house_id,
            "title": f"[threezero] {title[:120]}",
            "link": full_link,
        }

    final = list(listings.values())

    print(f"Parsed threezero listings: {len(final)}")

    for i, item in enumerate(final[:10], 1):
        print(f"threezero sample {i}: {item['title']} | {item['link']}")

    return final


def add_threezero_phone_numbers(session, listings):
    checked = []

    for item in listings:
        try:
            response = session.get(item["link"], headers=threezero_headers(), timeout=20)
            print(f"threezero detail status: {response.status_code} | {item['link']}")

            if response.status_code != 200:
                item["phones"] = []
                checked.append(item)
                continue

            item["phones"] = extract_phone_numbers(response.text)
            print(f"threezero phones found: {len(item['phones'])} | {item['phones']}")
            checked.append(item)

        except Exception as e:
            item["phones"] = []
            print(f"threezero detail failed: {e} | {item['link']}")
            checked.append(item)

    return checked


def crawl_threezero():
    print("threezero crawler started")

    session = requests.Session()

    try:
        response = session.get(THREEZERO_START_URL, headers=threezero_headers(), timeout=20)

        print(f"threezero status: {response.status_code}")
        print(f"threezero HTML length: {len(response.text)}")
        print(f"threezero final URL: {response.url}")

        if response.status_code != 200:
            print(response.text[:1000])
            return []

        listings = parse_threezero_listings(response.text, response.url)
        return add_threezero_phone_numbers(session, listings)

    except Exception as e:
        print(f"threezero crawl failed: {e}")
        return []


def run_crawler(name, crawl_func, processed_file, message_title, empty_message):
    print(f"===== {name} started =====")
    processed_ids = load_processed_ids(processed_file)

    all_listings = crawl_func()
    print(f"{name} total listings: {len(all_listings)}")

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

    print(f"{name} new listings: {len(new_listings)}")

    if not new_listings:
        print(empty_message)
        print(f"===== {name} finished =====")
        return

    msg = f"🏠 **【{message_title}】新發現 {len(new_listings)} 筆**\n"
    msg += "-------------------------\n"

    for i, house in enumerate(new_listings, 1):
        msg += f"**{i}. {house['title']}**\n"
        msg += f"🔗 詳情：{house['link']}\n"
        msg += "-------------------------\n"
        processed_ids.add(house["id"])

    ok = send_discord_message(msg)

    if ok:
        save_processed_ids(processed_file, processed_ids)
        print(f"{name} pushed {len(new_listings)} new listings to Discord")
    else:
        print(f"{name} Discord send failed; processed ids were not saved")

    print(f"===== {name} finished =====")


def run_threezero_crawler():
    print("===== threezero started =====")
    processed_ids = load_processed_ids(THREEZERO_PROCESSED_FILE)

    all_listings = crawl_threezero()
    print(f"threezero total listings checked: {len(all_listings)}")

    new_listings = []
    migrated_phone_keys = set()

    for item in all_listings:
        phone_keys = [f"phone:{phone}" for phone in item.get("phones", [])]

        if not phone_keys:
            print(f"Skip threezero listing with no phone number: {item['link']}")
            continue

        new_phone_keys = [key for key in phone_keys if key not in processed_ids]
        has_saved_phone_key = any(key in processed_ids for key in phone_keys)

        if new_phone_keys:
            if item["id"] in processed_ids and not has_saved_phone_key:
                print(f"Migrate existing threezero listing to phone keys: {item['link']}")
                migrated_phone_keys.update(new_phone_keys)
                continue

            item["new_phone_keys"] = new_phone_keys
            new_listings.append(item)

    print(f"threezero listings with new phone numbers: {len(new_listings)}")

    if not new_listings:
        if migrated_phone_keys:
            processed_ids.update(migrated_phone_keys)
            save_processed_ids(THREEZERO_PROCESSED_FILE, processed_ids)
            print(f"Migrated {len(migrated_phone_keys)} threezero phone numbers without notification")

        print("沒有新的 threezero 電話號碼更新。")
        print("===== threezero finished =====")
        return

    msg = f"🏠 **【threezero 租盤電話通知】新發現 {len(new_listings)} 筆**\n"
    msg += "-------------------------\n"

    for i, house in enumerate(new_listings, 1):
        msg += f"**{i}. {house['title']}**\n"
        msg += f"📞 電話：{', '.join(house.get('phones', []))}\n"
        msg += f"🔗 詳情：{house['link']}\n"
        msg += "-------------------------\n"

    ok = send_discord_message(msg)

    if ok:
        processed_ids.update(migrated_phone_keys)

        for house in new_listings:
            processed_ids.update(house["new_phone_keys"])
        save_processed_ids(THREEZERO_PROCESSED_FILE, processed_ids)
        print(f"threezero pushed {len(new_listings)} listings with new phone numbers to Discord")
    else:
        print("threezero Discord send failed; processed phone numbers were not saved")

    print("===== threezero finished =====")


def main():
    print("Combined crawler started")

    if DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL loaded")
    else:
        print("DISCORD_WEBHOOK_URL missing")

    run_crawler(
        name="28hse",
        crawl_func=crawl_28hse_dosearch,
        processed_file=OWNER_PROCESSED_FILE,
        message_title="28hse 明確業主盤通知",
        empty_message="沒有新的明確業主樓盤更新。",
    )

    run_threezero_crawler()

    print("Combined crawler finished")


if __name__ == "__main__":
    main()
