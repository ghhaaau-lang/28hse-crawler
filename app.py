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
        "Referer": "https://www.28hse.com/rent/apartment?owner_type=1",
    }


def extract_clean_candidates(text):
    patterns = [
        r'["\'](https?://[^"\']+)["\']',
        r'["\'](//[^"\']+)["\']',
        r'["\'](/[^"\']*(?:api|ajax|search|property|listing|rent|estate|item)[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'\$\.ajax\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']',
        r'\$\.get\(\s*["\']([^"\']+)["\']',
        r'\$\.post\(\s*["\']([^"\']+)["\']',
        r'fetch\(\s*["\']([^"\']+)["\']',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, text, re.IGNORECASE | re.DOTALL):
            if isinstance(m, tuple):
                m = m[0]

            m = m.strip()

            if not m:
                continue

            # 過濾掉太長的 JS 片段
            if len(m) > 220:
                continue

            # 過濾掉明顯不是路徑/URL 的東西
            if not (
                m.startswith("/")
                or m.startswith("http")
                or m.startswith("//")
            ):
                continue

            # 過濾圖片 / css / 字型
            lower = m.lower()
            if any(x in lower for x in [".png", ".jpg", ".jpeg", ".gif", ".css", ".woff", ".svg"]):
                continue

            found.add(m)

    return sorted(found)


def print_keyword_lines(text, keyword, limit=30):
    lines = text.splitlines()
    matched = []

    for i, line in enumerate(lines, 1):
        if keyword.lower() in line.lower():
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) > 350:
                line = line[:350] + "..."
            matched.append((i, line))

    print(f"\n========== lines containing: {keyword} / {len(matched)} ==========")

    for line_no, line in matched[:limit]:
        print(f"L{line_no}: {line}")


def main():
    print("🚀 28hse Clean Endpoint Debug started")

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
    for i, url in enumerate(script_urls, 1):
        print(f"script {i}: {url}")

    all_candidates = set()

    print("\n========== PAGE CLEAN CANDIDATES ==========")
    page_candidates = extract_clean_candidates(r.text)

    for c in page_candidates:
        all_candidates.add(c)
        print("page:", c)

    print_keyword_lines(r.text, "autocomplete_action_url")
    print_keyword_lines(r.text, "searchbarAutocompleteCfg")
    print_keyword_lines(r.text, "propertyDoSearchVersion")
    print_keyword_lines(r.text, "item_ids")
    print_keyword_lines(r.text, "owner_type")
    print_keyword_lines(r.text, "ajax")
    print_keyword_lines(r.text, "url:")

    print("\n========== JS CLEAN CANDIDATES ==========")

    for idx, js_url in enumerate(script_urls, 1):
        try:
            jr = session.get(js_url, headers=headers, timeout=20)
            print(f"\n--- JS {idx}: {js_url}")
            print(f"status={jr.status_code}, length={len(jr.text)}")

            if jr.status_code != 200:
                continue

            candidates = extract_clean_candidates(jr.text)

            for c in candidates:
                all_candidates.add(c)
                print("js:", c)

            for keyword in [
                "autocomplete_action_url",
                "searchbarAutocompleteCfg",
                "propertyDoSearchVersion",
                "item_ids",
                "owner_type",
                "ajax",
                "url:",
                "search",
                "property",
                "rent",
            ]:
                print_keyword_lines(jr.text, keyword, limit=15)

        except Exception as e:
            print(f"⚠️ JS fetch failed: {e}")

    print("\n========== ALL UNIQUE CLEAN CANDIDATES ==========")
    print(f"total: {len(all_candidates)}")

    for i, c in enumerate(sorted(all_candidates), 1):
        print(f"{i}. {c}")

    print("\n✅ Clean Endpoint Debug finished")


if __name__ == "__main__":
    main()
