import os
import re
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_asiaxpat_ids.json"

URL = "https://hongkong.asiaxpat.com/classifieds"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_hk_phones(text):
    phones = set()

    if not text:
        return []

    patterns = [
        r"(?:\+852\s*)?([569]\d{3}[\s\-]?\d{4})",
        r"(?:\+852\s*)?([569]\d{7})",
        r"wa\.me/(?:852)?([569]\d{7})",
        r"api\.whatsapp\.com/send\?phone=(?:852)?([569]\d{7})",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            phone = re.sub(r"\D", "", match)

            if phone.startswith("852"):
                phone = phone[3:]

            if re.match(r"^[569]\d{7}$", phone):
                phones.add(phone)

    return sorted(phones)


def load_processed_ids():
    if Path(LOCAL_PROCESSED_FILE).exists():
        try:
            data = json.loads(Path(LOCAL_PROCESSED_FILE).read_text(encoding="utf-8"))
            ids = data.get("ids", [])
            print(f"✅ 已讀取 {LOCAL_PROCESSED_FILE}：{len(ids)} 筆")
            return set(ids)
        except Exception as e:
            print(f"⚠️ 讀取 {LOCAL_PROCESSED_FILE} 失敗：{e}")

    print(f"ℹ️ 尚無 {LOCAL_PROCESSED_FILE}，將視為第一次執行")
    return set()


def save_processed_ids(processed_ids):
    try:
        Path(LOCAL_PROCESSED_FILE).write_text(
            json.dumps(
                {"ids": sorted(list(processed_ids))},
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
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


def crawl_asiaxpat():
    print("🚀 AsiaXPAT Playwright 正式版 started")

    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )

        try:
            response = page.goto(URL, wait_until="domcontentloaded", timeout=60000)

            print(f"🔎 status: {response.status if response else 'no response'}")
            print(f"🌐 final url: {page.url}")
            print(f"📌 title: {page.title()}")

            page.wait_for_timeout(10000)

            body_text = clean_text(page.locator("body").inner_text(timeout=10000))
            print(f"📝 body text length：{len(body_text)}")

            lower_text = body_text.lower()

            print("whatsapp:", lower_text.count("whatsapp"))
            print("phone:", lower_text.count("phone"))
            print("view listing:", lower_text.count("view listing"))

            links = page.locator("a").evaluate_all(
                """els => els.map(a => ({
                    text: a.innerText || '',
                    href: a.href || ''
                }))"""
            )

            print(f"🔗 a[href] 數量：{len(links)}")

            for item in links:
                text = clean_text(item.get("text", ""))
                href = item.get("href", "")

                if not text or not href:
                    continue

                if "View listing" not in text:
                    continue

                full_text = text

                phones = extract_hk_phones(full_text)

                if not phones:
                    continue

                item_key = re.sub(r"\W+", "_", href)[-140:]
                item_id = f"asiaxpat_{item_key}"

                title = text.replace("View listing", "").strip()
                title = clean_text(title)

                if not title:
                    title = "AsiaXPAT classified"

                listings.append({
                    "id": item_id,
                    "title": f"[AsiaXPAT] {title[:180]}",
                    "link": href,
                    "phones": " / ".join(phones),
                })

            unique = {}

            for item in listings:
                unique[item["id"]] = item

            final = list(unique.values())

            print(f"✅ AsiaXPAT 有電話 listing：{len(final)} 筆")

            for i, item in enumerate(final[:10], 1):
                print(f"sample {i}: {item['title']} | phone={item['phones']} | {item['link']}")

            return final

        except Exception as e:
            print(f"❌ AsiaXPAT Playwright 正式版失敗：{e}")
            return []

        finally:
            browser.close()


if __name__ == "__main__":
    print("🚀 AsiaXPAT Phone Radar started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_asiaxpat()

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

    print(f"🆕 AsiaXPAT 新電話 listing：{len(new_listings)} 筆")

    if new_listings:
        msg = f"📞 **【AsiaXPAT 電話雷達】新發現 {len(new_listings)} 筆有電話分類廣告**\n"
        msg += "-------------------------\n"

        for i, item in enumerate(new_listings, 1):
            msg += f"**{i}. {item['title']}**\n"
            msg += f"📞 電話：**{item['phones']}**\n"
            msg += f"🔗 連結：{item['link']}\n"
            msg += "-------------------------\n"

            processed_ids.add(item["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆 AsiaXPAT 電話 listing 至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("目前沒有新的 AsiaXPAT 電話 listing。")
