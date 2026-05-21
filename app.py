import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.28hse.com"
PAGE_URL = "https://www.28hse.com/rent/apartment?owner_type=1"


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh-TW;q=0.9,en;q=0.7",
        "Referer": "https://www.28hse.com/",
    }


def print_context(text, keyword, limit=20, window=240):
    matches = list(re.finditer(keyword, text, re.IGNORECASE))
    print(f"\n========== keyword: {keyword} / {len(matches)} 次 ==========")

    for i, m in enumerate(matches[:limit], 1):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        snippet = text[start:end]
        snippet = re.sub(r"\s+", " ", snippet)
        print(f"\n--- {keyword} context {i} ---")
        print(snippet)


def extract_candidates(text):
    patterns = [
        r'["\']([^"\']*api[^"\']*)["\']',
        r'["\']([^"\']*ajax[^"\']*)["\']',
        r'["\']([^"\']*search[^"\']*)["\']',
        r'["\']([^"\']*property[^"\']*)["\']',
        r'["\']([^"\']*listing[^"\']*)["\']',
        r'["\']([^"\']*rent[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'\.get\(\s*["\']([^"\']+)["\']',
        r'\.post\(\s*["\']([^"\']+)["\']',
        r'fetch\(\s*["\']([^"\']+)["\']',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, text, re.IGNORECASE):
            if isinstance(m, tuple):
                m = m[0]
            if any(k in m.lower() for k in ["api", "ajax", "search", "property", "listing", "rent", "estate", "item"]):
                found.add(m)

    return sorted(found)


def main():
    print("🚀 28hse JS Endpoint Debug started")

    session = requests.Session()
    headers = get_headers()

    r = session.get(PAGE_URL, headers=headers, timeout=20)
    print(f"🔎 Page status: {r.status_code}")
    print(f"📄 Page HTML length: {len(r.text)}")

    soup = BeautifulSoup(r.text, "html.parser")
    scripts = soup.find_all("script", src=True)

    script_urls = []

    for s in scripts:
        src = s.get("src", "")
        full = urljoin(BASE, src)
        script_urls.append(full)

    print(f"\n📜 script 數量：{len(script_urls)}")
    for i, u in enumerate(script_urls, 1):
        print(f"script {i}: {u}")

    all_candidates = set()

    print("\n========== Page HTML candidates ==========")
    page_candidates = extract_candidates(r.text)
    for c in page_candidates:
        all_candidates.add(c)
        print("page candidate:", c)

    print_context(r.text, "propertyDoSearchVersion", limit=10)
    print_context(r.text, "item_ids", limit=10)
    print_context(r.text, "owner_type", limit=10)
    print_context(r.text, "search_words", limit=10)

    print("\n========== Fetch JS files ==========")

    for idx, js_url in enumerate(script_urls, 1):
        try:
            jr = session.get(js_url, headers={**headers, "Referer": PAGE_URL}, timeout=20)
            print(f"\n--- JS {idx}: {js_url}")
            print(f"status={jr.status_code}, length={len(jr.text)}")

            if jr.status_code != 200:
                continue

            text = jr.text
            candidates = extract_candidates(text)

            print(f"candidate count={len(candidates)}")
            for c in candidates[:120]:
                all_candidates.add(c)
                print("candidate:", c)

            for kw in [
                "propertyDoSearchVersion",
                "item_ids",
                "owner_type",
                "search_words",
                "ajax",
                "api",
                "rent",
                "listing",
                "property",
            ]:
                if kw.lower() in text.lower():
                    print_context(text, kw, limit=8)

        except Exception as e:
            print(f"JS fetch failed: {e}")

    print("\n========== ALL UNIQUE CANDIDATES ==========")
    print(f"total candidates: {len(all_candidates)}")

    for i, c in enumerate(sorted(all_candidates), 1):
        print(f"{i}. {c}")

    print("\n✅ JS Endpoint Debug finished")


if __name__ == "__main__":
    main()
