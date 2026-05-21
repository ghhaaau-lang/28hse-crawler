import os
import requests
import json
import re
from bs4 import BeautifulSoup

# 🎯 雲端大腦：唯讀寫 Redis 資料庫
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

def send_signal_message(message_text):
    NGROK_URL = os.environ.get("SIGNAL_URL")
    API_KEY = os.environ.get("SIGNAL_API_KEY")
    if not NGROK_URL:
        return
    url = f"{NGROK_URL.rstrip('/')}/v2/send"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {
        "message": message_text,
        "number": "+85292906723",
        "recipients": ["+85292906723"]
    }
    try:
        requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
    except Exception:
        pass

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
                if not link.startswith('http'): link = f"https://www.28hse.com{link}"
                house_id = f"28hse_{re.search(r'item-(\d+)', link).group(1)}"
                listings.append({"id": house_id, "title": f"[28hse] {title}", "link": link})
            except: continue
    except: pass
    return listings

def crawl_house730():
    """House730 業主自讓盤 (o1代表業主盤)"""
    url = "https://www.house730.com/rent/o1/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    listings = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return []
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找 House730 的房源卡片區塊
        items = soup.find_all('a', href=re.compile(r'/rent-property-\d+/'))
        for item in items:
            try:
                # 撈取標題
                title_el = item.find('div', class_='title') or item.find('h3')
                title = title_el.text.strip() if title_el else "精選業主自讓盤"
                
                link = item['href']
                if not link.startswith('http'): link = f"https://www.house730.com{link}"
                
                # 提取 House730 唯一的房屋 ID
                house_id = f"730_{re.search(r'property-(\d+)', link).group(1)}"
                
                if not any(x['id'] == house_id for x in listings):
                    listings.append({"id": house_id, "title": f"[House730] {title}", "link": link})
            except: continue
    except: pass
    return listings

if __name__ == '__main__':
    processed_ids = load_processed_ids()
    
    # 同時開火兩邊撈取
    all_listings = crawl_28hse() + crawl_house730()
    new_listings = [h for h in all_listings if h['id'] not in processed_ids]
    
    if new_listings:
        msg_content = f"🏠 【最新業主盤雙源聯防】(新發現 {len(new_listings)} 筆)\n-------------------------\n"
        for i, house in enumerate(new_listings, 1):
            msg_content += f"{i}. {house['title']}\n🔗 詳情: {house['link']}\n-------------------------\n"
            processed_ids.add(house['id'])
        send_signal_message(msg_content)
        save_processed_ids(processed_ids)
        print(f"🎉 成功推送 {len(new_listings)} 筆全新聯防資料！")
    else:
        print("雙源均無新樓盤更新。")
