import os
import requests
import json
import re
from bs4 import BeautifulSoup

def send_signal_message(message_text):
    """
    透過 ngrok 內網穿透，將訊息發送回本機 Docker 的 Signal 機器人
    """
    # 自動從 GitHub Actions 環境變數讀取外網網址與密碼鎖
    NGROK_URL = os.environ.get("SIGNAL_URL")
    API_KEY = os.environ.get("SIGNAL_API_KEY")
    
    # 確保網址格式正確
    if NGROK_URL:
        url = f"{NGROK_URL.rstrip('/')}/v2/send"
    else:
        print("❌ [Signal 錯誤] 找不到 SIGNAL_URL 環境變數，請檢查 GitHub Secrets 設定。")
        return

    # 安全驗證頭：帶著這把鑰匙，家裡的 Docker 才會放行
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "message": message_text,
        "number": "+85292906723",       # 綁定成功的香港主號
        "recipients": ["+85292906723"]  # 接收通知的手機號碼
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        if response.status_code in [200, 201, 204]:
            print("✨ [Signal] 透過本機 Docker 穿透發送成功！")
        else:
            print(f"❌ [Signal] 發送失敗，狀態碼: {response.status_code}, 回應: {response.text}")
    except Exception as e:
        print(f"❌ [Signal] 連線到本機 Docker 失敗，請確認電腦 ngrok 是否在運行。錯誤原因: {str(e)}")


def crawl_28hse():
    """
    28hse 業主自讓盤爬蟲主程式
    """
    print("🔍 開始爬取 28hse 最新業主盤...")
    
    # 28hse 住宅租盤/買盤的業主自讓過濾網址
    url = "https://www.28hse.com/rent/residential/owner"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ 爬取失敗，網頁狀態碼: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 抓取樓盤列表（根據 28hse 最新網頁結構定位）
        items = soup.find_all('div', class_='property_item')
        
        new_listings = []
        for item in items[:5]:  # 每次只取最新的前 5 筆，避免資訊爆炸
            try:
                title_el = item.find('a', class_='title')
                price_el = item.find('div', class_='price')
                
                if title_el:
                    title = title_el.text.strip()
                    link = title_el['href']
                    if not link.startswith('http'):
                        link = f"https://www.28hse.com{link}"
                        
                    price = price_el.text.strip() if price_el else "面議"
                    
                    new_listings.append({
                        "title": title,
                        "price": price,
                        "link": link
                    })
            except Exception as e:
                continue
                
        return new_listings
    except Exception as e:
        print(f"❌ 爬蟲執行期間發生錯誤: {str(e)}")
        return None


# 🎯 主程式執行入口
if __name__ == '__main__':
    # 執行爬蟲
    listings = crawl_28hse()
    
    if listings:
        print(f"🎉 成功抓取到 {len(listings)} 筆最新樓盤！正在發送通知...")
        
        # 組合要發送到手機的訊息內容
        msg_content = "🏠 【28hse 最新業主盤通知】\n"
        msg_content += "-------------------------\n"
        
        for i, house in enumerate(listings, 1):
            msg_content += f"{i}. {house['title']}\n"
            msg_content += f"💰 價格: {house['price']}\n"
            msg_content += f"🔗 詳情: {house['link']}\n"
            msg_content += "-------------------------\n"
            
        # 🎯 真正呼叫發送功能，把資料推回你家電腦 Docker 噴射到手機
        send_signal_message(msg_content)
    else:
        # 💡 防呆保險：如果網頁剛好沒更新，我們依然發送一條健康檢查，確保通訊正常
        print("暫無新樓盤更新，發送通訊健康測試...")
        send_signal_message("🚀 Signal 穿透測試：通訊完美對接！目前 28hse 網頁無新盤變動。")
