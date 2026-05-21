import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_ids.json"


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


def extract_item_links(html):
    links = set()

    patterns = [
        r"https?://www\.28hse\.com/rent/apartment/item-\d+[^\"'<\s]*",
        r"/rent/apartment/item-\d+[^\"'<\s]*",
        r"rent/apartment/item-\d+[^\"'<\s]*",
        r"item-\d+",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, html):
            match = match.replace("\\/", "/")

            if match.startswith("http"):
                link = match
            elif match.startswith("/"):
                link = "https://www.28hse.com" + match
            elif match.startswith("rent/"):
                link = "https://www.28hse.com/" + match
            elif match.startswith("item-"):
                link = "https://www.28hse.com/rent/apartment/" + match
            else:
                continue

            links.add(link)

    return sorted(links)


def parse_listings_from_links(links):
    listings = []

    for link in links:
        id_match = re.search(r"item-(\d+)", link)
        if not id_match:
            continue

        house_id = f"28hse_{id_match.group(1)}"

        listings.append({
            "id": house_id,
            "title": "[28hse] 業主盤",
            "link": link
        })

    return listings


def get_headers():
    return {
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


def crawl_28hse_form_test():
    base_url = "https://www.28hse.com/rent/apartment?owner_type=1"
    session = requests.Session()
    headers = get_headers()

    print("🚀 28hse Form Test started")

    try:
        first = session.get(base_url, headers=headers, timeout=20)
        print(f"🔎 第一次請求狀態碼：{first.status_code}")
        print(f"📄 第一次 HTML 長度：{len(first.text)}")

        if first.status_code != 200:
            return []

        first_links = extract_item_links(first.text)
        print(f"🏠 第一次直接找到 item link：{len(first_links)} 條")

        if first_links:
            return parse_listings_from_links(first_links)

        soup = BeautifulSoup(first.text, "html.parser")
        forms = soup.find_all("form")
        print(f"🧾 form 數量：{len(forms)}")

        test_results = []

        for form_index, form in enumerate(forms, 1):
            action = form.get("action") or "/rent/apartment"
            method = (form.get("method") or "get").lower()

            target_url = urljoin("https://www.28hse.com", action)

            params = {}

            inputs = form.find_all(["input", "select", "textarea"])

            for inp in inputs:
                name = inp.get("name")
                if not name:
                    continue

                value = inp.get("value", "")

                # 保留原本 hidden 值
                params[name] = value

            # 強制加幾個關鍵參數
            params["buyRent"] = "rent"
            params["mobilePageChannel"] = "apartment"
            params["propertyDoSearchVersion"] = "2.0"
            params["owner_type"] = "1"
            params["page"] = "1"

            print(f"\n========== 測試 form {form_index} ==========")
            print(f"method={method}")
            print(f"target_url={target_url}")
            print(f"params keys={list(params.keys())[:40]}")
            print(f"params count={len(params)}")

            try:
                if method == "post":
                    r = session.post(target_url, headers=headers, data=params, timeout=20)
                else:
                    r = session.get(target_url, headers=headers, params=params, timeout=20)

                print(f"form {form_index} 狀態碼：{r.status_code}")
                print(f"form {form_index} URL：{r.url}")
                print(f"form {form_index} HTML 長度：{len(r.text)}")

                links = extract_item_links(r.text)
                print(f"form {form_index} 找到 item link：{len(links)} 條")

                if links:
                    test_results.extend(parse_listings_from_links(links))

                # Debug：看看有沒有 item_ids
                item_ids_match = re.findall(r'item_ids["\']?\s*[:=]\s*["\']?([^"\'<>\s]+)', r.text)
                print(f"form {form_index} item_ids 疑似數量：{len(item_ids_match)}")

                if item_ids_match[:5]:
                    print(f"item_ids samples：{item_ids_match[:5]}")

            except Exception as e:
                print(f"⚠️ form {form_index} 測試失敗：{e}")

        # 去重
        unique = {}
        for item in test_results:
            unique[item["id"]] = item

        listings = list(unique.values())
        print(f"\n✅ 28hse form test 最終整理：{len(listings)} 筆")
        return listings

    except Exception as e:
        print(f"❌ 28hse form test 失敗：{e}")
        return []


if __name__ == "__main__":
    print("🚀 Crawler started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_28hse_form_test()

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
