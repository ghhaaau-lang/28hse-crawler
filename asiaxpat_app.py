import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://hongkong.asiaxpat.com/classifieds"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_hk_phones(text):
    phones = set()

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


def main():
    print("🚀 AsiaXPAT Playwright test started")

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

            # 給 Cloudflare / JS 一點時間
            page.wait_for_timeout(10000)

            html = page.content()
            text = clean_text(page.locator("body").inner_text(timeout=10000))

            print(f"📄 html length: {len(html)}")
            print(f"📝 text length: {len(text)}")

            lower_html = html.lower()
            lower_text = text.lower()

            print("\n========== Cloudflare 檢查 ==========")
            for word in [
                "just a moment",
                "cloudflare",
                "challenges.cloudflare.com",
                "turnstile",
                "captcha",
                "checking your browser",
            ]:
                print(f"{word}: {lower_html.count(word)}")

            print("\n========== 關鍵字檢查 ==========")
            for word in [
                "classifieds",
                "view listing",
                "whatsapp",
                "phone",
                "furniture",
                "property",
                "for sale",
                "hong kong",
            ]:
                print(f"{word}: {lower_text.count(word)}")

            print("\n========== 文字前 1500 字 ==========")
            print(text[:1500])

            print("\n========== 連結 sample ==========")
            links = page.locator("a").evaluate_all(
                """els => els.slice(0, 150).map(a => ({
                    text: a.innerText || '',
                    href: a.href || ''
                }))"""
            )

            print(f"a[href] sample count: {len(links)}")

            for i, item in enumerate(links[:80], 1):
                link_text = clean_text(item.get("text", ""))
                href = item.get("href", "")
                print(f"{i}. {link_text[:100]} | {href}")

            print("\n========== 電話檢查 ==========")
            phones = extract_hk_phones(text)
            print(f"電話數量：{len(phones)}")

            for phone in phones[:50]:
                print(f"phone: {phone}")

            Path("asiaxpat_playwright_debug.html").write_text(html, encoding="utf-8")
            print("✅ saved asiaxpat_playwright_debug.html")

        except Exception as e:
            print(f"❌ AsiaXPAT Playwright test failed: {e}")

        finally:
            browser.close()

    print("✅ AsiaXPAT Playwright test finished")


if __name__ == "__main__":
    main()
