import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LOCAL_PROCESSED_FILE = "processed_sgcn_ids.json"

BASE = "https://bbs.sgcn.com"

# 10: 房屋出租
# 11: 二手跳蚤
# 13: 二手車買賣
# 138: 生活服務 / 搬家
SG_FIDS = [10, 11]

FEMALE_WORDS = ["小姐", "miss", "mrs", "太太", "女士", "媽咪", "c9"]
MALE_WORDS = ["先生", "mr", "男", "巴打", "brother", "帥哥"]


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


def detect_gender(text):
    text_lower = text.lower()

    for word in FEMALE_WORDS:
        if word.lower() in text_lower:
            return "♀️ 女性"

    for word in MALE_WORDS:
        if word.lower() in text_lower:
            return "♂️ 男性"

    return "❓ 未知"


def extract_sg_phones(text):
    """
    新加坡常見手機：8 或 9 開頭，8 位數。
    會處理：
    91234567
    9123 4567
    9123-4567
    9 1 2 3 4 5 6 7
    """
    phones = set()

    if not text:
        return []

    # 常見格式：91234567 / 9123 4567 / 9123-4567
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


def fetch_post_detail_text(link, headers):
    """
    進入帖子詳情頁，抓正文文字。
    Discuz 常見正文 class 是 t_f。
    """
    try:
        response = requests.get(link, headers=headers, timeout=15)

        print(f"📄 詳情頁狀態碼：{response.status_code} | {link}")

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Discuz 正文常見位置
        contents = soup.find_all(["td", "div"], class_=re.compile(r"(t_f|pcb|pct)", re.I))

        if contents:
            text = " ".join(c.get_text(" ", strip=True) for c in contents)
            return clean_text(text)

        # 備援：抓整頁文字
        return clean_text(soup.get_text(" ", strip=True))

    except Exception as e:
        print(f"⚠️ 詳情頁抓取失敗：{e}")
        return ""


def crawl_shicheng():
    """
    新加坡獅城論壇：
    1. 抓 fid 最新帖子
    2. 進詳情頁
    3. 標題 + 內文一起匹配電話
    4. 只回傳有電話的帖子
    """
    listings = []
    headers = get_headers()

    for fid in SG_FIDS:
        url = f"{BASE}/forum.php?mod=forumdisplay&fid={fid}&filter=author&orderby=dateline"

        print("\n==============================")
        print(f"🚀 抓取獅城論壇分類 fid={fid}")
        print(f"URL：{url}")
        print("==============================")

        try:
            response = requests.get(url, headers=headers, timeout=15)

            print(f"🔎 分類頁狀態碼：{response.status_code}")
            print(f"📄 分類頁 HTML 長度：{len(response.text)}")

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            posts = soup.find_all("a", href=re.compile(r"mod=viewthread&tid=\d+"))

            print(f"🔗 找到帖子連結：{len(posts)} 條")

            seen_in_page = set()

            for post in posts[:40]:
                try:
                    title = clean_text(post.get_text(" ", strip=True))

                    if not title or len(title) < 5:
                        continue

                    link = post.get("href", "")

                    if not link:
                        continue

                    link = urljoin(BASE + "/", link)

                    tid_match = re.search(r"tid=(\d+)", link)

                    if not tid_match:
                        continue

                    tid = tid_match.group(1)
                    item_id = f"sgcn_{tid}"

                    if item_id in seen_in_page:
                        continue

                    seen_in_page.add(item_id)

                    # 先抓標題電話
                    detail_text = fetch_post_detail_text(link, headers)

                    combined_text = f"{title} {detail_text}"

                    phones = extract_sg_phones(combined_text)

                    if not phones:
                        print(f"⚠️ 無電話，跳過：{title[:60]}")
                        continue

                    gender = detect_gender(combined_text)

                    phone_text = " / ".join(phones)

                    listings.append({
                        "id": item_id,
                        "title": f"[獅城論壇-分類{fid}] {title}",
                        "link": link,
                        "phones": phone_text,
                        "gender": gender,
                    })

                    print(f"✅ 找到電話：{phone_text} | {title[:60]}")

                except Exception as e:
                    print(f"⚠️ 單篇解析失敗：{e}")
                    continue

        except Exception as e:
            print(f"❌ 分類 fid={fid} 抓取失敗：{e}")
            continue

    # 去重
    unique = {}
    for item in listings:
        unique[item["id"]] = item

    final = list(unique.values())[:15]

    print(f"\n✅ 獅城論壇最終有電話帖子：{len(final)} 筆")
    return final


if __name__ == "__main__":
    print("🚀 SGCN Phone Radar started")

    if DISCORD_WEBHOOK_URL:
        print("✅ DISCORD_WEBHOOK_URL 已讀取")
    else:
        print("❌ DISCORD_WEBHOOK_URL 未讀取")

    processed_ids = load_processed_ids()

    all_listings = crawl_shicheng()

    new_listings = [
        item for item in all_listings
        if item["id"] not in processed_ids
    ]

    print(f"🆕 新電話帖子：{len(new_listings)} 筆")

    if new_listings:
        msg = f"🇸🇬 **【獅城論壇電話雷達】新發現 {len(new_listings)} 筆有電話帖子**\n"
        msg += "-------------------------\n"

        for i, item in enumerate(new_listings, 1):
            msg += f"**{i}. {item['title']}**\n"
            msg += f"📞 電話：**{item['phones']}**\n"
            msg += f"👤 性別判斷：{item['gender']}\n"
            msg += f"🔗 帖子：{item['link']}\n"
            msg += "-------------------------\n"

            processed_ids.add(item["id"])

        ok = send_discord_message(msg)

        if ok:
            save_processed_ids(processed_ids)
            print(f"🎉 成功推送 {len(new_listings)} 筆至 Discord")
        else:
            print("⚠️ Discord 發送失敗，暫不保存 processed ids")

    else:
        print("目前沒有新的有電話帖子。")
