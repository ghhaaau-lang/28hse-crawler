import re
import requests
from bs4 import BeautifulSoup

URLS = [
    "https://www.house730.com/rent/o1/",
    "https://www.house730.com/rent/",
]


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,zh-CN;q=0.8,en;q=0.7",
        "Referer": "https://www.house730.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def find_candidates(html):
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== HTML 基本檢查 ==========")
    print(f"HTML 長度：{len(html)}")

    text_lower = html.lower()
    for word in ["cloudflare", "captcha", "403", "forbidden", "property", "rent", "api", "json"]:
        print(f"{word}: {text_lower.count(word)}")

    print("\n========== script src ==========")
    scripts = soup.find_all("script", src=True)
    print(f"script 數量：{len(scripts)}")
    for i, s in enumerate(scripts[:80], 1):
        print(f"script {i}: {s.get('src')}")

    print("\n========== 可疑 href ==========")
    links = soup.find_all("a", href=True)
    print(f"a[href] 數量：{len(links)}")

    matched = []
    for a in links:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        if any(k in href.lower() for k in ["rent", "property", "house", "estate"]):
            matched.append((href, text))

    print(f"可疑 href 數量：{len(matched)}")
    for i, (href, text) in enumerate(matched[:120], 1):
        print(f"href {i}: {href} | text={text[:80]}")

    print("\n========== 可疑 API / endpoint ==========")

    patterns = [
        r'["\'](https?://[^"\']+)["\']',
        r'["\'](/[^"\']*(?:api|ajax|search|property|listing|rent|estate)[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'fetch\(\s*["\']([^"\']+)["\']',
        r'\$\.get\(\s*["\']([^"\']+)["\']',
        r'\$\.post\(\s*["\']([^"\']+)["\']',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, html, re.IGNORECASE | re.DOTALL):
            if isinstance(m, tuple):
                m = m[0]

            m = m.strip()

            if len(m) > 250:
                continue

            if any(k in m.lower() for k in ["api", "ajax", "search", "property", "listing", "rent", "estate"]):
                found.add(m)

    print(f"可疑 endpoint 數量：{len(found)}")
    for i, item in enumerate(sorted(found)[:150], 1):
        print(f"candidate {i}: {item}")


def test_house730():
    print("🚀 House730 Debug started")

    session = requests.Session()
    headers = get_headers()

    for url in URLS:
        print("\n\n==============================")
        print(f"測試 URL：{url}")
        print("==============================")

        try:
            response = session.get(url, headers=headers, timeout=20)

            print(f"狀態碼：{response.status_code}")
            print(f"Final URL：{response.url}")
            print(f"Content-Type：{response.headers.get('content-type')}")
            print(f"回應長度：{len(response.text)}")
            print("回應前 500 字：")
            print(response.text[:500].replace("\n", " ")[:500])

            if response.status_code == 200:
                find_candidates(response.text)
            else:
                print("⚠️ 非 200，可能被擋或需要其他 headers/cookies。")

        except Exception as e:
            print(f"❌ 請求失敗：{e}")

    print("\n✅ House730 Debug finished")


if __name__ == "__main__":
    test_house730()
