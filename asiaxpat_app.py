import os
import re
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_asiaxpat_masked_contacts.json"

START_URL = "https://hongkong.asiaxpat.com/classifieds"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_contact_signals(text):
    """
    抓公開可見的聯絡號碼資訊：
    - +******8634
    - ******8634
    - +852******8634
    - phone ending in 8634
    - contact me on whatsapp 92078634
    """
    signals = set()

    if not text:
        return []

    patterns = [
        # +******8634 / ******8634 / +852******8634
        r"\+?\d{0,3}\s*\*{3,}\s*\d{3,4}",

        # ending in 8634 / ends with 8634
        r"(?:ending in|ends with|尾數|尾号)\s*[:：]?\s*(\d{3,4})",

        # 完整香港電話
        r"(?:\+852\s*)?([235679]\d{3}[\s\-]?\d{4})",
        r"(?:\+852\s*)?([235679]\d{7})",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            if isinstance(match, tuple):
                match = match[0]

            raw = str(match).strip()

            if not raw:
                continue

            # 如果是完整電話，整理成 8 位
            digits = re.sub(r"\D", "", raw)

            if digits.startswith("852"):
                digits = digits[3:]

            if re.match(r"^[235679]\d{7}$", digits):
                signals.add(digits)
                continue

            # 如果是尾數，保留 tail 格式
            if re.match(r"^\d{3,4}$", digits):
                signals.add(f"尾數{digits}")
                continue

            # 如果是遮罩號碼，保留原樣但整理空格
            if "*" in raw:
                masked = re.sub(r"\s+", "", raw)
                signals.add(masked)

    return sorted(signals)


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


def get_listing_links(page):
    links = page.locator("a").evaluate_all(
        """els => els.map(a => ({
            text: a.innerText || '',
            href: a.href || ''
        }))"""
    )

    listings = {}

    for item in links:
        text = clean_text(item.get("text", ""))
        href = item.get("href", "")

        if not text or not href:
            continue

        if "View listing" not in text:
            continue

        if "/classifieds/" not in href:
            continue

        item_key = re.sub(r"\W+", "_", href)[-140:]
        item_id = f"asiaxpat_{item_key}"

        title = clean_text(text.replace("View listing", ""))

        if not title:
            title = "AsiaXPAT classified"

        listings[item_id] = {
            "id": item_id,
            "title": f"[AsiaXPAT] {title[:180]}",
            "link": href,
            "list_text": text,
        }

    final = list(listings.values())

    print(f"🔗 首頁抓到 View listing：{len(final)} 筆")

    for i, item in enumerate(final[:10], 1):
        print(f"listing sample {i}: {item['title'][:100]} | {item['link']}")

    return final


def extract_visible_inputs(page):
    """
    有些遮罩電話是在 input value 裡，body inner_text 不一定抓得到。
    所以把 input / textarea value 也抓出來。
    """
    try:
        values = page.locator("input, textarea").evaluate_all(
            """els => els.map(el => ({
                value: el.value || '',
                placeholder: el.placeholder || '',
                name: el.name || '',
                id: el.id || ''
            }))"""
        )

        chunks = []

        for item in values:
            chunks.append(item.get("value", ""))
            chunks.append(item.get("placeholder", ""))
            chunks.append(item.get("name", ""))
            chunks.append(item.get("id", ""))

        return clean_text(" ".join(chunks))

    except Exception as e:
        print(f"⚠️ input value 抓取失敗：{e}")
        return ""


def crawl_asiaxpat():
    print("🚀 AsiaXPAT 遮罩電話尾數雷達 started")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )

        page = context.new_page()

        try:
            response = page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)

            print(f"🔎 首頁 status: {response.status if response else 'no response'}")
            print(f"🌐 final url: {page.url}")
            print(f"📌 title: {page.title()}")

            page.wait_for_timeout(8000)

            body_text = clean_text(page.locator("body").inner_text(timeout=10000))

            print(f"📝 首頁 body text length：{len(body_text)}")
            print("首頁 view listing:", body_text.lower().count("view listing"))

            listings = get_listing_links(page)

            for index, item in enumerate(listings, 1):
                link = item["link"]
                list_text = item["list_text"]

                print("\n-------------------------")
                print(f"🔎 詳情頁 {index}/{len(listings)}")
                print(f"URL：{link}")

                detail_page = context.new_page()

                try:
                    detail_response = detail_page.goto(
                        link,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    print(f"詳情頁 status: {detail_response.status if detail_response else 'no response'}")
                    print(f"詳情頁 title: {detail_page.title()}")

                    detail_page.wait_for_timeout(5000)

                    detail_text = clean_text(
                        detail_page.locator("body").inner_text(timeout=10000)
                    )

                    input_text = extract_visible_inputs(detail_page)
                    html_text = detail_page.content()

                    combined_text = f"{list_text} {detail_text} {input_text} {html_text}"

                    signals = extract_contact_signals(combined_text)

                    if not signals:
                        print(f"⚠️ 沒看到遮罩/電話：{item['title'][:80]}")
                        continue

                    contact_text = " / ".join(signals)

                    # 用 listing + contact signal 做去重
                    contact_key = re.sub(r"\W+", "_", contact_text)
                    notify_id = f"{item['id']}_{contact_key}"

                    print(f"✅ 看到聯絡號碼標記：{contact_text} | {item['title'][:80]}")

                    results.append({
                        "id": notify_id,
                        "title": item["title"],
                        "link": link,
                        "contact": contact_text,
                    })

                except Exception as e:
                    print(f"⚠️ 詳情頁失敗：{e}")

                finally:
                    detail_page.close()

            unique = {}

            for item in results:
                unique[item["id"]] = item

            final = list(unique.values())

            print(f"\n✅ AsiaXPAT 看到遮罩/電話的 listing：{len(final)} 筆")

            for i, item in enumerate(final[:10], 1):
                print(f"contact sample {i}: {item['title']} | {item['contact']} | {item['link']}")

            return final

        except Exception as e:
            print(f"❌ AsiaXPAT 遮罩電話版失敗：{e}")
            return []

        finally:
            browser.close()


if __name__ == "__main__":
    print("🚀 AsiaXPAT Masked Contact Radar started")

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

    print(f"🆕 AsiaXPAT 新遮罩/電話 listing：{len(new_listings)} 筆")

    if new_listings:
        msg = f"📞 **【AsiaXPAT 遮罩電話雷達】新發現 {len(new_listings)} 筆聯絡號碼變化**\n"
        msg += "-------------------------\n"

        for i, item in enumerate(new_listings, 1):
            msg += f"**{i}. {item['title']}**\n"
            msg += f"📞 顯示號碼：**{item['contact']}**\n"
            msg += f"🔗 連結：{item['link']}\n"
            msg += "-------------------------\n"

            processed_ids.add(item["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆 AsiaXPAT 遮罩電話 listing 至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("目前沒有新的 AsiaXPAT 遮罩/電話 listing。")
