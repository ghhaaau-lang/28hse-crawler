import re
from playwright.sync_api import sync_playwright

URL = "https://www.shichengbbs.com/#new"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def main():
    print("🚀 shichengbbs Playwright quick test started")

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

            print("\n========== 文字前 1500 字 ==========")
            print(text[:1500])

            links = page.locator("a").evaluate_all(
                """els => els.slice(0, 100).map(a => ({
                    text: a.innerText || '',
                    href: a.href || ''
                }))"""
            )

            print("\n========== 連結 sample ==========")
            print(f"a[href] sample count: {len(links)}")

            for i, item in enumerate(links[:50], 1):
                link_text = clean_text(item.get("text", ""))
                href = item.get("href", "")
                print(f"{i}. {link_text[:80]} | {href}")

        except Exception as e:
            print(f"❌ Playwright quick test failed: {e}")

        finally:
            browser.close()

    print("✅ shichengbbs Playwright quick test finished")


if __name__ == "__main__":
    main()
