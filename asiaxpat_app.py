import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_asiaxpat_ids.json"

BASE = "https://hongkong.asiaxpat.com"
START_URL = "https://hongkong.asiaxpat.com/classifieds"


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-HK;q=0.8,zh-TW;q=0.7",
        "Referer": BASE,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_hk_phones(text):
    phones = set()

    if not text:
        return []

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


def load_processed_ids():
    if os.path.exists(LOCAL_PROCESSED_FILE):
        try:
            with open(LOCAL_PROCESSED_FILE, "r", encoding="utf-8") as f:
                ids = json.load(f).get("ids", [])
                print(f"✅ 已讀取 {LOCAL_PROCESSED_FILE}：{len(ids)} 筆")
                return set(ids)
        except Exception as e:
            print(f"⚠️ 讀取 {LOCAL_PROCESSED_FILE} 失敗：{e}")

    print(f"ℹ️ 尚無 {LOCAL_PROCESSED_FILE}，將視為第一次執行")
    return set()


def save_processed_ids(processed_ids):
    try:
        with open(LOCAL_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"ids": sorted(list(processed_ids))},
                f,
                ensure_ascii=False,
                indent=2
            )
        print(f"✅ 已保存 {LOCAL_PROCESSED_FILE}：{len(processed_ids)} 筆")
    except Exception as e:
        print(f"❌ 保存 {LOCAL_PROCESSED_FILE} 失敗：{e}")


def send_discord_message(message_text):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL，請檢查 GitHub Secrets")
        return False

    chunks = []
    text = message_text.strip()

    while len(text) > 1800:
        cut = text.rfind("\n", 0, 1800)
        if cut == -1:
            cut = 1800
        chunks.append(text[:cut])
        text = text[cut:].strip()

    if text:
        chunks.append(text)

    success_count = 0

    for index, chunk in enumerate(chunks, 1):
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": chunk},
                timeout=15
            )

            if response.status_code in [200, 204]:
                print(f"✨ [Discord] 第 {index}/{len(chunks)} 段訊息發送成功")
                success_count += 1
            else:
                print(f"❌ [Discord] 發送失敗：{response.status_code}")
                print(response.text[:500])

        except Exception as e:
            print(f"❌ [Discord] 連線失敗：{e}")

    return success_count == len(chunks)


def parse_asiaxpat_listings(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    print(f"🔗 AsiaXPAT a[href] 數量：{len(links)}")

    listings = {}

    for a in links:
        href = urljoin(page_url, a.get("href", ""))
        text = clean_text(a.get_text(" ", strip=True))

        if not text:
            continue

        # 只抓明顯是 classified listing 的「View listing」卡片
        if "View listing" not in text:
            continue

        # 排除導航連結
        lowered = href.lower()
        if any(x in lowered for x in [
            "facebook.com",
            "instagram.com",
            "linkedin.com",
            "wa.me",
            "/login",
            "/signup",
            "/post",
        ]):
            continue

        # 用 href 當 id；若 href 太泛，就用文字 hash
        item_key = re.sub(r"\W+", "_", href)[-120:]
        if not item_key or item_key == "_":
            item_key = re.sub(r"\W+", "_", text)[:120]

        item_id = f"asiaxpat_{item_key}"

        phones = extract_hk_phones(text)
        phone_text = " / ".join(phones) if phones else "公開列表未見電話"

        # 簡單整理標題：取 View listing 前面的內容
        title = text.replace("View listing", "").strip()
        title = title[:180] if title else "AsiaXPAT classified"

        listings[item_id] = {
            "id": item_id,
            "title": f"[AsiaXPAT] {title}",
            "link": href,
            "phones": phone_text,
            "has_phone": bool(phones),
        }

    final = list(listings.values())

    print(f"✅ AsiaXPAT 解析到 classified：{len(final)} 筆")
    print(f"📞 其中公開列表有電話：{sum(1 for x in final if x['has_phone'])} 筆")

    for i, item in enumerate(final[:10], 1):
        print(f"sample {i}: {item['title'][:100]} | phone={item['phones']} | {item['link']}")

    return final


def crawl_asiaxpat():
    print("🚀 AsiaXPAT Classifieds started")

    try:
        response = requests.get(START_URL, headers=get_headers(), timeout=20)

        print(f"🔎 狀態碼：{response.status_code}")
        print(f"📄 HTML 長度：{len(response.text)}")
        print(f"Final URL：{response.url}")

        if response.status_code != 200:
            print(response.text[:1000])
            return []

        return parse_asiaxpat_listings(response.text, response.url)

    except Exception as e:
        print(f"❌ AsiaXPAT 抓取失敗：{e}")
        return []


if __name__ == "__main__":
    print("🚀 AsiaXPAT Phone Radar started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_asiaxpat()

    # 你如果只想通知「有電話」的，保留這行
    filtered_listings = [item for item in all_listings if item["has_phone"]]

    # 如果你想全部 classified 都通知，改成：
    # filtered_listings = all_listings

    new_listings = [
        item for item in filtered_listings
        if item["id"] not in processed_ids
    ]

    print(f"🆕 AsiaXPAT 新電話 listing：{len(new_listings)} 筆")

    if new_listings:
        msg = f"📞 **【AsiaXPAT 電話雷達】新發現 {len(new_listings)} 筆有電話分類廣告**\n"
        msg += "-------------------------\n"

        for i, item in enumerate(new_listings, 1):
            msg += f"**{i}. {item['title']}**\n"
            msg += f"📞 電話：**{item['phones']}**\n"
            msg += f"🔗 連結：{item['link']}\n"
            msg += "-------------------------\n"
            processed_ids.add(item["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆 AsiaXPAT 電話 listing 至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("目前沒有新的 AsiaXPAT 電話 listing。")
