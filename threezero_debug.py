import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.threezero.com.hk"

URLS = [
    "https://www.threezero.com.hk/",
    "https://www.threezero.com.hk/search",
    "https://www.threezero.com.hk/rent",
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
        "Referer": BASE,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def find_candidates(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== HTML 基本檢查 ==========")
    print(f"HTML 長度：{len(html)}")

    text_lower = html.lower()

    for word in [
        "cloudflare",
        "captcha",
        "403",
        "forbidden",
        "rent",
        "property",
        "singleproperty",
        "api",
        "json",
        "登入",
        "會員",
        "業主",
        "免佣",
        "whatsapp",
        "電話",
    ]:
        print(f"{word}: {text_lower.count(word.lower())}")

    print("\n========== script src ==========")
    scripts = soup.find_all("script", src=True)
    print(f"script 數量：{len(scripts)}")

    for i, s in enumerate(scripts[:100], 1):
        src = urljoin(page_url, s.get("src", ""))
        print(f"script {i}: {src}")

    print("\n========== 可疑 href ==========")
    links = soup.find_all("a", href=True)
    print(f"a[href] 數量：{len(links)}")

    matched = []

    for a in links:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        full = urljoin(page_url, href)

        if any(k in full.lower() for k in [
            "rent",
            "property",
            "singleproperty",
            "flat",
            "house",
            "apartment",
        ]):
            matched.append((full, text))

    print(f"可疑 href 數量：{len(matched)}")

    for i, (href, text) in enumerate(matched[:150], 1):
        print(f"href {i}: {href} | text={text[:100]}")

    print("\n========== 可疑 API / endpoint ==========")

    patterns = [
        r'["\'](https?://[^"\']+)["\']',
        r'["\'](/[^"\']*(?:api|ajax|search|property|listing|rent|estate|singleproperty)[^"\']*)["\']',
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

            if any(k in m.lower() for k in [
                "api",
                "ajax",
                "search",
                "property",
                "listing",
                "rent",
                "estate",
                "singleproperty",
            ]):
                found.add(urljoin(page_url, m))

    print(f"可疑 endpoint 數量：{len(found)}")

    for i, item in enumerate(sorted(found)[:150], 1):
        print(f"candidate {i}: {item}")

    print("\n========== 可能電話 / WhatsApp ==========")

    phone_patterns = [
        r"(?:\+852\s*)?[569]\d{3}\s*\d{4}",
        r"(?:\+852\s*)?[569]\d{7}",
        r"wa\.me/\d+",
        r"api\.whatsapp\.com/send\?phone=\d+",
    ]

    phones = set()

    for pattern in phone_patterns:
        for m in re.findall(pattern, html, re.IGNORECASE):
            phones.add(m)

    print(f"電話 / WhatsApp 疑似數量：{len(phones)}")

    for i, phone in enumerate(sorted(phones)[:80], 1):
        print(f"phone {i}: {phone}")


def test_threezero():
    print("🚀 threezero Debug started")

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
                find_candidates(response.text, response.url)
            else:
                print("⚠️ 非 200，可能被擋或網址不對。")

        except Exception as e:
            print(f"❌ 請求失敗：{e}")

    print("\n✅ threezero Debug finished")


if __name__ == "__main__":
    test_threezero()
