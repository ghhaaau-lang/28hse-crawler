import os
import re
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def print_context(html, keyword, limit=10, window=220):
    print(f"\n========== 關鍵字前後文：{keyword} ==========")

    matches = list(re.finditer(keyword, html, re.IGNORECASE))
    print(f"找到 {len(matches)} 次")

    for i, m in enumerate(matches[:limit], 1):
        start = max(0, m.start() - window)
        end = min(len(html), m.end() + window)
        snippet = html[start:end]
        snippet = re.sub(r"\s+", " ", snippet)
        print(f"\n--- {keyword} context {i} ---")
        print(snippet)


def debug_28hse_deeper():
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

    print("🚀 28hse Deep Debug started")
    print(f"🔎 狀態碼：{res.status_code}")
    print(f"📄 HTML 長度：{len(res.text)}")

    html = res.text
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== 1. Forms ==========")
    forms = soup.find_all("form")
    print(f"form 數量：{len(forms)}")

    for i, form in enumerate(forms[:30], 1):
        action = form.get("action", "")
        method = form.get("method", "")
        print(f"form {i}: method={method}, action={action}")

        inputs = form.find_all(["input", "select", "textarea"])
        for inp in inputs[:40]:
            name = inp.get("name", "")
            value = inp.get("value", "")
            input_type = inp.get("type", "")
            print(f"  - {input_type} name={name} value={value}")

    print("\n========== 2. Meta / JSON-LD ==========")
    scripts = soup.find_all("script")

    json_like_count = 0

    for i, script in enumerate(scripts, 1):
        script_type = script.get("type", "")
        text = script.get_text(" ", strip=True)

        if "json" in script_type.lower() or "application/ld+json" in script_type.lower():
            json_like_count += 1
            print(f"\nJSON script {json_like_count}, type={script_type}")
            print(text[:1500])

    if json_like_count == 0:
        print("沒有找到 JSON-LD / JSON script")

    print("\n========== 3. 搜尋疑似 endpoint ==========")

    patterns = [
        r'https?://[^"\']+',
        r'["\'](/[^"\']*api[^"\']*)["\']',
        r'["\']([^"\']*ajax[^"\']*)["\']',
        r'["\']([^"\']*search[^"\']*)["\']',
        r'["\']([^"\']*property[^"\']*)["\']',
        r'["\']([^"\']*listing[^"\']*)["\']',
        r'["\']([^"\']*rent[^"\']*)["\']',
    ]

    found = set()

    for pattern in patterns:
        for m in re.findall(pattern, html, re.IGNORECASE):
            if isinstance(m, tuple):
                m = m[0]
            found.add(m)

    filtered = []

    for x in found:
        lx = x.lower()
        if any(k in lx for k in ["api", "ajax", "search", "property", "listing", "rent", "estate"]):
            filtered.append(x)

    print(f"可疑 endpoint / link：{len(filtered)} 條")

    for i, x in enumerate(sorted(filtered)[:200], 1):
        print(f"candidate {i}: {x}")

    print_context(html, "api", limit=20)
    print_context(html, "search", limit=20)
    print_context(html, "owner_type", limit=20)
    print_context(html, "property", limit=20)
    print_context(html, "rent", limit=20)
    print_context(html, "turnstile", limit=10)

    print("\n========== 4. 檢查是否有 Cloudflare / Bot Check ==========")

    cf_words = [
        "turnstile",
        "cloudflare",
        "challenge",
        "captcha",
        "cf-chl",
        "cf_clearance",
    ]

    for word in cf_words:
        print(f"{word}: {html.lower().count(word.lower())}")

    print("\n✅ Deep Debug finished")


if __name__ == "__main__":
    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("⚠️ DISCORD_WEBHOOK_URL 未讀取，這版只是 debug")

    debug_28hse_deeper()
