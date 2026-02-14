import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
USER_ID = os.environ.get("LINE_USER_ID")

if not TOKEN or not USER_ID:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not found in .env")
    sys.exit(1)

print(f"Token: {TOKEN[:10]}...")
print(f"User ID: {USER_ID}")

url = "https://api.line.me/v2/bot/message/push"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}
data = {
    "to": USER_ID,
    "messages": [
        {
            "type": "text",
            "text": "這是來自 PC-Price-Tracker 的測試訊息！如果您收到這則訊息，代表頻道設定正確。"
        }
    ]
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    if response.status_code == 200:
        print("✅ 測試訊息發送成功！請檢查手機。")
    else:
        print("❌ 發送失敗，請檢查 Token 或 User ID。")
except Exception as e:
    print(f"Error: {e}")
