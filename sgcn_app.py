import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.shichengbbs.com/#new"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_sg_phones(text):
    phones = set()

    patterns = [
        r"(?<!\d)([89]\d{3}[\s\-]?\d{4})(?!\d)",
        r"(?<!\d)([89](?:[\s\-]?\d){7})(?!\d)",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text):
            phone = re.sub(r"\D", "", match)
            if re.match(r"^[89]\d{7}$", phone):
                phones.add(phone)

    return sorted(phones)


def main():
    print("🚀 shichengbbs Playwright test started")

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
            locale="zh-HK",
        )

        try:
            response = page.goto(URL, wait_until="networkidle", timeout=60000)

            status = response.status if response else "no response"
            print(f"🔎 status: {status}")
            print(f"🌐 final url: {page.url}")
            print(f"📌 title: {page.title()}")

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

            print("\n========== 文字前 1000 字 ==========")
            print(text[:1000])

            print("\n========== 連結檢查 ==========")
            links = page.locator("a").evaluate_all(
                """els => els.slice(0, 200).map(a => ({
                    text: a.innerText || '',
                    href: a.href || ''
                }))"""
            )

            print(f"a[href] sample count: {len(links)}")

            candidates = []

            for item in links:
                href = item.get("href", "")
                link_text = clean_text(item.get("text", ""))
                blob = (href + " " + link_text).lower()

                if any(k in blob for k in [
                    "rent",
                    "room",
                    "house",
                    "post",
                    "detail",
                    "category",
                    "租房",
                    "出租",
                    "二手",
                    "电话",
                    "電話",
                ]):
                    candidates.append((link_text, href))

            print(f"可疑連結數量：{len(candidates)}")

            for i, (link_text, href) in enumerate(candidates[:80], 1):
                print(f"candidate {i}: {link_text[:80]} | {href}")

            print("\n========== 電話檢查 ==========")
            phones = extract_sg_phones(text)
            print(f"電話數量：{len(phones)}")
            for phone in phones[:50]:
                print(f"phone: {phone}")

            Path("shichengbbs_playwright_debug.html").write_text(html, encoding="utf-8")
            print("✅ saved shichengbbs_playwright_debug.html")

        except Exception as e:
            print(f"❌ Playwright test failed: {e}")

        finally:
            browser.close()

    print("✅ shichengbbs Playwright test finished")


if __name__ == "__main__":
    main()
