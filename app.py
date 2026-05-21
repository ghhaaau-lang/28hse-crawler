import os
import requests
import json
import re
from bs4 import BeautifulSoup

HISTORY_FILE = "processed_ids.txt"

def load_processed_ids():
    """讀取已經發送過的樓盤 ID 帳本"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_ids(processed_ids):
    """把新的樓盤 ID 寫入帳本"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for pid in sorted(processed_ids):
            f.write(f"{pid}\n")

def send_signal_message(message_text):
    """透過 ngrok 內網穿透發送 Signal 訊息"""
    NGROK_URL = os.environ.get("SIGNAL_URL")
    API_KEY = os.environ.get("SIGNAL_API_KEY")
    
    if not NGROK_URL:
        print("❌ [Signal 錯誤] 找不到 SIGNAL_URL 環境變數。")
        return

    url = f"{NGROK_URL.rstrip('/')}/v2/send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "message": message_text,
        "number": "+85292906723",
        "recipients": ["+85292906723"]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        if response.status_code in [200, 201, 204]:
            print("✨ [Signal] 訊息穿透發送成功！")
        else:
            print(f"❌ [Signal] 發送失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"❌ [Signal] 連線失敗: {str(e)}")


def crawl_28hse():
    """28hse 業主自讓盤爬蟲（最新網址與結構校正版）"""
    print("🔍 開始爬取 28hse 最新業主盤...")
    
    # 🎯 這裡替換成你找出來的最新正確網址
    url = "https://www.28hse.com/rent/apartment?owner_type=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ 爬取失敗，網頁狀態碼: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 兼容新舊版結構：同時捕捉 property_item 或以 item-開頭的列表中物件
        items = soup.find_all('div', class_=lambda x: x and ('property_item' in x or 'item' in x))
        
        # 如果上面沒抓到，嘗試抓取常見的 a 標籤外層
        if not items:
            items = soup.find_all('a', href=re.compile(r'/rent/apartment/item-\d+'))
            
        listings = []
        for item in items:
            try:
                # 尋找標題與連結
                title_el = item.find('a', class_='title') if hasattr(item, 'find') else None
                if not title_el and item.name == 'a':
                    title_el = item
                    
                if title_el:
                    title = title_el.text.strip()
                    link = title_el['href']
                    if not link.startswith('http'):
                        link = f"https://www.28hse.com{link}"
                    
                    # 提取樓盤唯一 ID
                    id_match = re.search(r'item-(\d+)', link)
                    house_id = id_match.group(1) if id_match else link
                    
                    # 尋找價格
                    price_el = item.find('div', class_='price') if hasattr(item, 'find') else None
                    if not price_el and hasattr(item, 'find_next'):
                        price_el = item.find_next('div', class_='price')
                        
                    price = price_el.text.strip() if price_el else "面議"
                    
                    # 簡單過濾掉重複抓取的 ID
                    if not any(h['id'] == house_id for h in listings):
                        listings.append({
                            "id": house_id,
                            "title": title,
                            "price": price,
                            "link": link
                        })
            except Exception:
                continue
                
        return listings
    except Exception as e:
        print(f"❌ 爬蟲出錯: {str(e)}")
        return []


if __name__ == '__main__':
    # 1. 載入舊帳本
    processed_ids = load_processed_ids()
    
    # 2. 爬取最新樓盤
    all_listings = crawl_28hse()
    
    # 3. 🧠 核心比對：過濾出「帳本裡沒有」的全新樓盤
    new_listings = [h for h in all_listings if h['id'] not in processed_ids]
    
    if new_listings:
        print(f"🎉 發現 {len(new_listings)} 個全新未看過的業主盤！正在發送通知...")
        
        msg_content = f"🏠 【28hse 最新業主盤通知】(新發現 {len(new_listings)} 筆)\n"
        msg_content += "-------------------------\n"
        
        for i, house in enumerate(new_listings, 1):
            msg_content += f"{i}. {house['title']}\n"
            msg_content += f"💰 價格: {house['price']}\n"
            msg_content += f"🔗 詳情: {house['link']}\n"
            msg_content += "-------------------------\n"
            
            # 將新樓盤 ID 紀錄到記憶體中
            processed_ids.add(house['id'])
            
        # 發送精準通知
        send_signal_message(msg_content)
        
        # 4. 寫回帳本存檔
        save_processed_ids(processed_ids)
    else:
        print("查無新樓盤更新，本次不發送 Signal 通知（保持安靜）。")
