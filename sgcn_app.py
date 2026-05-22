import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.shichengbbs.com"
START_URL = "https://www.shichengbbs.com/#new"


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


def debug_page(url):
    print("\n==============================")
    print(f"測試 URL：{url}")
    print("==============================")

    res = requests.get(url, headers=get_headers(), timeout=20)

    print(f"狀態碼：{res.status_code}")
    print(f"Final URL：{res.url}")
    print(f"Content-Type：{res.headers.get('content-type')}")
    print(f"HTML 長度：{len(res.text)}")
    print("前 500 字：")
    print(res.text[:500].replace("\n", " ")[:500])

    if res.status_code != 200:
        return

    soup = BeautifulSoup(res.text, "html.parser")

    print("\n========== 全部 a[href] ==========")
    links = soup.find_all("a", href=True)
    print(f"a[href] 數量：{len(links)}")

    for i, a in enumerate(links[:200], 1):
        href = urljoin(res.url, a.get("href", ""))
        text = clean_text(a.get_text(" ", strip=True))
        print(f"{i}. {text[:60]} | {href}")

    print("\n========== 可疑分類 / 帖子連結 ==========")

    keywords = [
        "rent", "room", "house", "property", "category", "post",
        "ad", "item", "detail", "fang", "zu", "二手", "租房", "出租"
    ]

    candidates = []

    for a in links:
        href = urljoin(res.url, a.get("href", ""))
        text = clean_text(a.get_text(" ", strip=True))
        blob = (href + " " + text).lower()

        if any(k.lower() in blob for k in keywords):
            candidates.append((text, href))

    print(f"可疑連結數量：{len(candidates)}")

    for i, (text, href) in enumerate(candidates[:150], 1):
        print(f"candidate {i}: {text[:80]} | {href}")

    print("\n========== 電話匹配 ==========")
    phones = extract_sg_phones(soup.get_text(" ", strip=True))
    print(f"電話數量：{len(phones)}")
    for p in phones[:50]:
        print("phone:", p)

    print("\n========== script src ==========")
    scripts = soup.find_all("script", src=True)
    print(f"script 數量：{len(scripts)}")
    for i, s in enumerate(scripts[:100], 1):
        print(f"script {i}: {urljoin(res.url, s.get('src', ''))}")

    print("\n========== 可疑 API / endpoint ==========")
    html = res.text
    patterns = [
        r'["\'](https?://[^"\']+)["\']',
        r'["\'](/[^"\']*(?:api|ajax|search|post|ad|category|item|detail|rent|room|house)[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'fetch\(\s*["\']([^"\']+)["\']',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, html, re.IGNORECASE | re.DOTALL):
            if isinstance(m, tuple):
                m = m[0]
            m = m.strip()
            if len(m) <= 250:
                found.add(urljoin(res.url, m))

    print(f"endpoint 數量：{len(found)}")
    for i, item in enumerate(sorted(found)[:150], 1):
        print(f"endpoint {i}: {item}")


if __name__ == "__main__":
    print("🚀 shichengbbs Debug started")
    debug_page(START_URL)
    print("✅ shichengbbs Debug finished")
