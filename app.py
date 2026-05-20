import os
import json
import subprocess
import requests
import yaml

SIGNAL_PHONE = os.environ.get("SIGNAL_PHONE")
SIGNAL_RECIPIENT = os.environ.get("SIGNAL_RECIPIENT")

def send_signal(message):
    try:
        cmd = [
            "/opt/signal-cli/bin/signal-cli",
            "-u", SIGNAL_PHONE,
            "send",
            "-m", message,
            SIGNAL_RECIPIENT
        ]
        subprocess.run(cmd, check=True)
        print("✅ Signal 訊息已發送")
    except Exception as e:
        print(f"❌ Signal 發送失敗: {e}")

def check_new_listings():
    with open("sites.yaml", "r", encoding="utf-8") as f:
        sites = yaml.safe_load(f)["sites"]

    try:
        with open("seen_listings.json", "r", encoding="utf-8") as f:
            seen = set(json.load(f))
    except:
        seen = set()

    new_count = 0
    for site in sites:
        # 這裡可以加強抓取邏輯
        new_count += 1

    if new_count > 0:
        msg = f"🆕 發現 {new_count} 個新業主樓盤！\n請查看最新訊息。"
        send_signal(msg)

    return f"檢查完成，新增 {new_count} 筆"

if __name__ == "__main__":
    check_new_listings()
