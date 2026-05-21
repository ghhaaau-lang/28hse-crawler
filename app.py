import os
import requests
import json

def send_signal_message(message_text):
    # 自動從 GitHub 保險箱讀取外網網址與密碼鎖
    NGROK_URL = os.environ.get("SIGNAL_URL")
    API_KEY = os.environ.get("SIGNAL_API_KEY")
    
    # 確保網址末端格式正確
    if NGROK_URL:
        url = f"{NGROK_URL.rstrip('/')}/v2/send"
    else:
        print("❌ 錯誤：找不到 SIGNAL_URL 環境變數")
        return

    # 安全驗證頭：帶著這把鑰匙，家裡的 Docker 才會放行
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "message": message_text,
        "number": "+85292906723",       # 你綁定成功的香港主號
        "recipients": ["+85292906723"]  # 接收通知的手機號碼
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        if response.status_code in [200, 201, 204]:
            print("✨ [Signal] 透過本機 Docker 穿透發送成功！")
        else:
            print(f"❌ [Signal] 發送失敗，狀態碼: {response.status_code}, 回應: {response.text}")
    except Exception as e:
        print(f"❌ [Signal] 連線到本機 Docker 失敗: {str(e)}")
