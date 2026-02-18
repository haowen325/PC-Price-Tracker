import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Open-Meteo API (No Key Required)
# https://open-meteo.com/

LOCATIONS = [
    {"name": "台北", "lat": 25.0330, "lon": 121.5654},
    {"name": "台中", "lat": 24.1477, "lon": 120.6736},
    {"name": "高雄", "lat": 22.6273, "lon": 120.3014}
]

WMO_CODES = {
    0: "☀️ 晴朗",
    1: "🌤️ 多雲",
    2: "☁️ 陰天",
    3: "☁️ 陰天",
    45: "🌫️ 霧",
    48: "🌫️ 霧",
    51: "🌧️ 毛毛雨",
    53: "🌧️ 毛毛雨",
    55: "🌧️ 毛毛雨",
    61: "☔ 小雨",
    63: "☔ 中雨",
    65: "☔ 大雨",
    80: "☔ 陣雨",
    81: "☔ 陣雨",
    82: "☔ 陣雨",
    95: "⚡ 雷雨",
    96: "⚡ 雷雨",
    99: "⚡ 雷雨"
}

def get_weather_desc(code):
    return WMO_CODES.get(code, "❓ 未知")

def fetch_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia%2FTaipei"
    try:
        response = requests.get(url)
        data = response.json()
        
        # Get today's data (index 0)
        daily = data.get("daily", {})
        if not daily: return None
        
        return {
            "code": daily["weather_code"][0],
            "max_temp": daily["temperature_2m_max"][0],
            "min_temp": daily["temperature_2m_min"][0],
            "pop": daily["precipitation_probability_max"][0] # Probability of Precipitation
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

class LineBotNotifier:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_weather_report(self, weather_data):
        if not self.access_token or not self.user_id:
            print("LINE credentials not found.")
            return

        bubbles = []
        
        for loc in LOCATIONS:
            city_name = loc["name"]
            data = weather_data.get(city_name)
            if not data: continue
            
            desc = get_weather_desc(data["code"])
            
            # Color logic
            bg_color = "#87CEEB" # Sky Blue
            if "晴" in desc: bg_color = "#FFD700" # Gold
            if "雨" in desc: bg_color = "#4682B4" # Steel Blue
            if "雷" in desc: bg_color = "#483D8B" # Dark Slate Blue
            if "陰" in desc: bg_color = "#D3D3D3" # Light Grey

            bubble = {
                "type": "bubble",
                "size": "micro",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": bg_color,
                    "contents": [
                        {"type": "text", "text": city_name, "color": "#FFFFFF", "weight": "bold", "size": "lg"}
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": desc,
                            "weight": "bold",
                            "size": "md",
                            "align": "center"
                        },
                        {
                            "type": "separator", "margin": "sm"
                        },
                         {
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": f"{data['min_temp']}°-{data['max_temp']}°", "size": "xs", "flex": 2},
                                {"type": "text", "text": f"☔{data['pop']}%", "size": "xs", "color": "#1E90FF", "align": "end", "flex": 1}
                            ]
                        }
                    ]
                }
            }
            bubbles.append(bubble)

        if not bubbles: return

        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "今日天氣預報",
                    "contents": {
                        "type": "carousel",
                        "contents": bubbles
                    }
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            requests.post(self.api_url, headers=headers, data=json.dumps(payload))
            print("Weather report sent.")
        except Exception as e:
            print(f"Error sending LINE: {e}")

def main():
    print("Fetching weather...")
    results = {}
    for loc in LOCATIONS:
        print(f"Fetching {loc['name']}...")
        data = fetch_weather(loc['lat'], loc['lon'])
        if data:
            results[loc['name']] = data
    
    load_dotenv()
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if results and token and user_id:
        notifier = LineBotNotifier(token, user_id)
        notifier.send_weather_report(results)
    else:
        print("Skipping notification (No data or no token)")

if __name__ == "__main__":
    main()
