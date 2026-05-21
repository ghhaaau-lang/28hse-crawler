import os
import requests
import json
import re
from bs4 import BeautifulSoup

# 🎯 雲端大腦：讀寫 Redis 資料庫
KV_URL = os.environ.get("KV_URL")

def load_processed_ids():
    if not KV_URL:
        return set()
    try:
        response = requests.get(f"{KV_URL}/processed_ids", timeout=10)
        if response.status_code == 200:
            return set(response.json().get("ids", []))
    except Exception:
        pass
    return set()

def save_processed_ids(processed_ids):
    if not KV_URL:
        return
    try:
        payload = {"ids": list(processed_ids)}
        requests.post(f"{KV_URL}/processed_ids", json=payload, timeout=10)
    except Exception:
        pass

def send_discord_message(message_text):
    """🚀 直連 Discord Webhook，一條網址搞定，本機免開機"""
    WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("❌ 找不到 DISCORD_WEBHOOK_URL 環境變數")
        return
    
    payload = {
        "content": message_text
    }
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code in [200, 204]:
            print("✨ [Discord] 訊息發送成功！")
        else:
            print(f"❌ [Discord] 發送失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"❌ [Discord] 連線失敗: {str(e)}")

def crawl_28hse():
    """28hse 業主自讓盤"""
    url = "https://www.28hse.com/rent/apartment?owner_type=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    listings = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return []
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', href=re.compile(r'/rent/apartment/item-\d+'))
        for item in items:
            try:
                title = item.text.strip().split('\n')[0]
                link = item['href']
                if not link.startswith('http'): 
                    link = f"https://www.28hse.com{link}"
                
                id_match = re.search(r'item-(\d+)', link)
                house_id = f"28hse_{id_match.group(1)}" if id_match else f"28hse_{link}"
                listings.append({"id": house_id, "title": f"[28hse] {title}", "link": link})
            except: continue
    except: pass
    return listings

def crawl_house730():
    """House730 業主自讓盤"""
    url = "https://www.house730.com/rent/o1/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    listings = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return []
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', href=re.compile(r'/rent-property-\d+/'))
        for item in items:
            try:
                title_el = item.find('div', class_='title') or item.find('h3')
                title = title_el.text.strip() if title_el else "精選業主自讓盤"
                link = item['href']
                if not link.startswith('http'): 
                    link = f"https://www.house730.com{link}"
                
                id_match = re.search(r'property-(\d+)', link)
                house_id = f"730_{id_match.group(1)}" if id_match else f"730_{link}"
                
                if not any(x['id'] == house_id for x in listings):
                    listings.append({"id": house_id, "title": f"[House730] {title}", "link": link})
            except: continue
    except: pass
    return listings

if __name__ == '__main__':
    processed_ids = load_processed_ids()
    
    all_listings = crawl_28hse() + crawl_house730()
    new_listings = [h for h in all_listings if h['id'] not in processed_ids]
    
    if new_listings:
        # 使用 Discord 粗體語法 **...** 讓手機排版更清晰
        msg_content = f"🏠 **【最新業主盤雙源聯防】(新發現 {len(new_listings)} 筆)**\n-------------------------\n"
        for i, house in enumerate(new_listings, 1):
            msg_content += f"**{i}. {house['title']}**\n🔗 詳情: {house['link']}\n-------------------------\n"
            processed_ids.add(house['id'])
        
        send_discord_message(msg_content)
        save_processed_ids(processed_ids)
        print(f"🎉 成功推送 {len(new_listings)} 筆全新雙源資料至 Discord！")
    else:
        print("雙源均無新樓盤更新。")
