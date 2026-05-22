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


def normalize_contact_signal(raw):
    raw = str(raw or "").strip()
    raw = re.sub(r"\s+", "", raw)

    if not raw:
        return ""

    digits = re.sub(r"\D", "", raw)

    if digits.startswith("852"):
        digits = digits[3:]

    # 完整香港電話
    if re.match(r"^[235679]\d{7}$", digits):
        return digits

    # 遮罩號碼，例如 +******8634 / ******8634
    if "*" in raw:
        tail_match = re.search(r"(\d{3,4})$", raw)
        if tail_match:
            return f"尾數{tail_match.group(1)}"

    # ending in 8634
    if re.match(r"^\d{3,4}$", digits):
        return f"尾數{digits}"

    return ""


def extract_contact_signals(text):
    signals = set()

    if not text:
        return []

    patterns = [
        r"\+?\d{0,3}\s*\*{3,}\s*\d{3,4}",
        r"(?:ending in|ends with|尾數|尾号)\s*[:：]?\s*(\d{3,4})",
        r"(?:\+852\s*)?([235679]\d{3}[\s\-]?\d{4})",
        r"(?:\+852\s*)?([235679]\d{7})",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            if isinstance(match, tuple):
                match = match[0]

            signal = normalize_contact_signal(match)

            if signal:
                signals.add(signal)

    # 如果完整電話存在，就移除相同尾數
    full_numbers = [s for s in signals if re.match(r"^[235679]\d{7}$", s)]
    tails_to_remove = set()

    for num in full_numbers:
        tails_to_remove.add(f"尾數{num[-4:]}")
        tails_to_remove.add(f"尾數{num[-3:]}")

    signals = signals - tails_to_remove

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


def get_view_listing_count(page):
    try:
        return page.get_by_text("View listing", exact=True).count()
    except Exception:
        return 0


def extract_current_page_result(page, fallback_title, fallback_link):
    body_text = clean_text(page.locator("body").inner_text(timeout=10000))

    try:
        input_values = page.locator("input, textarea").evaluate_all(
            """els => els.map(el => [
                el.value || '',
                el.placeholder || '',
                el.name || '',
                el.id || ''
            ].join(' '))"""
        )
        input_text = clean_text(" ".join(input_values))
    except Exception:
        input_text = ""

    combined_text = f"{body_text} {input_text}"

    signals = extract_contact_signals(combined_text)

    title = page.title() or fallback_title
    title = clean_text(title)

    if "Just a moment" in title:
        print("🚫 詳情頁仍是 Cloudflare / Just a moment")
        return None

    if not signals:
        print(f"⚠️ 詳情頁沒有看到遮罩/電話：{title[:80]}")
        return None

    contact_text = " / ".join(signals)

    # 用當前 URL 優先
    link = page.url or fallback_link
    item_key = re.sub(r"\W+", "_", link)[-140:]
    contact_key = re.sub(r"\W+", "_", contact_text)
    notify_id = f"asiaxpat_{item_key}_{contact_key}"

    print(f"✅ 詳情頁看到聯絡號碼：{contact_text} | {title[:80]}")

    return {
        "id": notify_id,
        "title": f"[AsiaXPAT] {title[:180]}",
        "link": link,
        "contact": contact_text,
    }


def crawl_asiaxpat():
    print("🚀 AsiaXPAT 首頁點擊詳情頁版 started")

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

            count = get_view_listing_count(page)
            print(f"🔗 首頁 View listing 按鈕數量：{count}")

            if count == 0:
                text = clean_text(page.locator("body").inner_text(timeout=10000))
                print("首頁前 1000 字：")
                print(text[:1000])
                return []

            max_items = min(count, 20)

            for index in range(max_items):
                print("\n-------------------------")
                print(f"🔎 點擊詳情 {index + 1}/{max_items}")

                try:
                    # 每次回首頁後重新抓 locator，避免 DOM 失效
                    buttons = page.get_by_text("View listing", exact=True)

                    # 取得點擊前附近文字，當 fallback title
                    fallback_title = "AsiaXPAT classified"

                    try:
                        parent_text = buttons.nth(index).locator("xpath=ancestor::a[1]").inner_text(timeout=3000)
                        if parent_text:
                            fallback_title = clean_text(parent_text.replace("View listing", ""))
                    except Exception:
                        pass

                    # 有些 View listing 是 a，有些可能是 button；先抓 href
                    fallback_link = ""

                    try:
                        href = buttons.nth(index).locator("xpath=ancestor::a[1]").get_attribute("href", timeout=3000)
                        if href:
                            if href.startswith("http"):
                                fallback_link = href
                            else:
                                fallback_link = "https://hongkong.asiaxpat.com" + href
                    except Exception:
                        pass

                    buttons.nth(index).scroll_into_view_if_needed(timeout=10000)
                    page.wait_for_timeout(500)

                    buttons.nth(index).click(timeout=15000)

                    page.wait_for_load_state("domcontentloaded", timeout=60000)
                    page.wait_for_timeout(6000)

                    print(f"詳情頁 URL：{page.url}")
                    print(f"詳情頁 title：{page.title()}")

                    result = extract_current_page_result(page, fallback_title, fallback_link)

                    if result:
                        results.append(result)

                    # 回上一頁
                    page.go_back(wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)

                except Exception as e:
                    print(f"⚠️ 點擊詳情失敗：{e}")

                    # 嘗試回首頁
                    try:
                        page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(5000)
                    except Exception:
                        pass

            unique = {}

            for item in results:
                unique[item["id"]] = item

            final = list(unique.values())

            print(f"\n✅ AsiaXPAT 點擊版找到遮罩/電話 listing：{len(final)} 筆")

            for i, item in enumerate(final[:10], 1):
                print(f"contact sample {i}: {item['title']} | {item['contact']} | {item['link']}")

            return final

        except Exception as e:
            print(f"❌ AsiaXPAT 點擊詳情頁版失敗：{e}")
            return []

        finally:
            browser.close()


if __name__ == "__main__":
    print("🚀 AsiaXPAT Click Contact Radar started")

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
        msg = f"📞 **【AsiaXPAT 點擊版電話雷達】新發現 {len(new_listings)} 筆聯絡號碼變化**\n"
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
            print(f"🎉 成功推送 {len(new_listings)} 筆 AsiaXPAT 點擊版電話 listing 至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("目前沒有新的 AsiaXPAT 遮罩/電話 listing。")
