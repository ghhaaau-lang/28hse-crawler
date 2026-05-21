import os
import re
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def crawl_28hse_debug():
    url = "https://www.28hse.com/rent/apartment?owner_type=1"

    headers = {
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

    res = requests.get(url, headers=headers, timeout=20)

    print(f"🔎 28hse 狀態碼：{res.status_code}")
    print(f"📄 HTML 長度：{len(res.text)}")

    html = res.text
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== 1. 檢查 script src ==========")
    scripts = soup.find_all("script", src=True)
    print(f"📜 script 數量：{len(scripts)}")

    for i, s in enumerate(scripts[:80], 1):
        src = s.get("src", "")
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = "https://www.28hse.com" + src

        print(f"script {i}: {src}")

    print("\n========== 2. 搜尋 HTML 內可疑 API 字眼 ==========")
    keywords = [
        "api",
        "search",
        "listing",
        "property",
        "rent",
        "estate",
        "owner",
        "__NEXT_DATA__",
        "apollo",
        "graphql",
        "nuxt",
        "json",
        "pageProps",
        "initialState",
    ]

    lower_html = html.lower()

    for kw in keywords:
        count = lower_html.count(kw.lower())
        print(f"{kw}: {count}")

    print("\n========== 3. 搜尋可能的 API URL ==========")
    patterns = [
        r'https?://[^"\']+/api/[^"\']+',
        r'https?://[^"\']+/[^"\']*api[^"\']*',
        r'"/api/[^"\']+',
        r"'/api/[^'\"]+",
        r'https?://[^"\']+\.json[^"\']*',
        r'/_next/data/[^"\']+',
        r'__NEXT_DATA__',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, html):
            found.add(m)

    print(f"🔗 找到可疑 URL / pattern：{len(found)} 條")

    for i, item in enumerate(sorted(found)[:120], 1):
        print(f"candidate {i}: {item}")

    print("\n========== 4. 搜尋含 rent / property / apartment 的 href ==========")
    links = soup.find_all("a", href=True)

    matched_links = []

    for a in links:
        href = a.get("href", "")
        if any(x in href.lower() for x in ["rent", "property", "apartment", "estate"]):
            matched_links.append(href)

    print(f"🏠 可疑 href 數量：{len(matched_links)}")

    for i, href in enumerate(matched_links[:120], 1):
        print(f"href {i}: {href}")

    print("\n========== 5. HTML 前 1000 字 ==========")
    print(html[:1000])


if __name__ == "__main__":
    print("🚀 28hse API Debug started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("⚠️ DISCORD_WEBHOOK_URL 未讀取，但這版只是 debug，不影響")

    crawl_28hse_debug()
