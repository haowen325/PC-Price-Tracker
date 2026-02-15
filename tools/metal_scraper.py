
import os
import requests
import json
import gspread
import yfinance as yf
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv

# Rebar logic: 
# Since daily variations are small and mostly weekly, we can:
# 1. Fetch latest news for "豐興 鋼筋 盤價" to see if there's a new announcement.
# 2. If no new announcement, assume previous price.
# 3. OR just use a fixed source if available.
# For simplicity and reliability in this V1, let's Carry Forward the last available price from the sheet, 
# unless we find a specific keyword "漲" or "跌" in today's news? 
# actually, yfinance is great for Copper/Nickel. Rebar is the tricky one.
# Let's use the last value from Sheet as default, and maybe just log LME daily.
# The user asked for "Taiwan Steel Price". 
# Plan: 
# 1. Get LME Copper & Nickel (Stainless proxy) from yfinance.
# 2. Get last recorded Rebar price from Sheet.
# 3. Append today's data.

def get_google_sheet():
    load_dotenv()
    json_str = os.environ.get("GSPREAD_JSON")
    sheet_url = os.environ.get("GOOGLE_SHEET_URL")
    
    if not json_str or not sheet_url:
        print("Missing secrets")
        return None

    try:
        creds_dict = json.loads(json_str)
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open_by_url(sheet_url)
        return sheet
    except Exception as e:
        print(f"Error connecting to GSheet: {e}")
        return None

def fetch_market_data():
    print("Fetching market data...")
    # Tickers
    # HG=F: Copper
    # TWD=X: USD/TWD
    # CMCU.L? Or just use HG=F (Comex) as proxy. 
    # Stainless: 'Ni=F' (Nickel). 
    
    # Tickers:
    # CPER: Copper ETF
    # TWD=X: USD/TWD
    # 2002.TW: China Steel (中鋼)
    # 2015.TW: Feng Hsin (豐興) - Rebar/Scrap proxy
    # 2027.TW: Da Cheng Steel (大成鋼) - Stainless proxy
    
    tickers = ["CPER", "TWD=X", "2002.TW", "2015.TW", "2027.TW"] 
    # Fetch 5 days to ensure we get a valid close price even on weekends
    data = yf.download(tickers, period="5d")
    
    try:
        if data.empty:
            print("No data fetched.")
            return None

        # Helper to get last valid float
        def get_last_valid(series):
            # dropna and get last
            valid = series.dropna()
            if valid.empty: return 0.0
            val = float(valid.iloc[-1])
            import math
            if math.isnan(val) or math.isinf(val): return 0.0
            return val
            
        hg = get_last_valid(data["Close"]["CPER"])
        twd = get_last_valid(data["Close"]["TWD=X"])
        china_steel = get_last_valid(data["Close"]["2002.TW"])
        feng_hsin = get_last_valid(data["Close"]["2015.TW"])
        da_cheng = get_last_valid(data["Close"]["2027.TW"])
        
        if twd == 0: twd = 32.5 # Fallback
        
        copper_twd = hg * twd
        
        # Manual Reference Prices (updated 2026-02-16 from news)
        # Feng Hsin: Rebar 16,900, Scrap 8,600
        
        return {
            "copper": round(copper_twd, 2),
            "nickel": 0, # Still no reliable source, using Da Cheng as proxy in UI
            "china_steel": china_steel,
            "feng_hsin": feng_hsin,
            "da_cheng": da_cheng, # Stainless Proxy
            "rebar_ref": 16900,
            "scrap_ref": 8600,
            "twd": twd
        }
    except Exception as e:
        print(f"Error parsing yfinance: {e}")
        return None

def update_sheet_and_get_history(market_data):
    sheet = get_google_sheet()
    if not sheet: return None
    
    try:
        ws = sheet.worksheet("Metal_Prices")
    except:
        print("Worksheet not found, run backfill first.")
        return None
        
    # Get last row for Rebar
    all_values = ws.get_all_values()
    last_row = all_values[-1] if len(all_values) > 1 else None
    
    current_rebar = 16900 # Default fallback
    if last_row:
        try:
            # Date, Copper, Rebar, Stainless. Rebar is index 2.
            current_rebar = float(last_row[2])
        except:
            pass
            
    # Append Today
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if today already exists to avoid dupes?
    if last_row and last_row[0] == today:
        print("Today already exists, skipping append.")
    else:
        new_row = [
            today,
            market_data["copper"],
            current_rebar, # Carry forward
            market_data["nickel"]
        ]
        ws.append_row(new_row)
        print(f"Appended: {new_row}")
        
    return ws.get_all_records()

def plot_trends(data, filename="metal_trend.png"):
    if not data: return None
    
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"])
    
    plt.figure(figsize=(10, 6))
    
    # Plot Copper (Left Axis)
    ax1 = plt.gca()
    ax1.plot(df["Date"], df["Copper_TWD_Kg"], color="#b87333", label="Copper ETF (TWD)", linewidth=2)
    ax1.set_ylabel("Copper ETF Value (TWD)", color="#b87333", fontweight="bold")
    ax1.tick_params(axis='y', labelcolor="#b87333")
    
    # Plot Steel/Rebar (Right Axis)
    ax2 = ax1.twinx()
    ax2.plot(df["Date"], df["Steel_Rebar_TWD_Ton"], color="#708090", label="Steel Rebar (TWD/Ton)", linewidth=2, linestyle="--")
    
    ax1.plot(df["Date"], df["Stainless_Index"], color="#C0C0C0", label="Nickel ETF (Stainless Proxy)", linewidth=2, linestyle="-.")
    
    ax1.set_xlabel("Date")
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    # Combine legends
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left")
    
    plt.title("Metal Price Trends (Copper ETF / Nickel ETF / Steel)")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    return filename

class ImgBBUploader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.upload_url = "https://api.imgbb.com/1/upload"

    def upload(self, image_path):
        if not self.api_key: return None
        try:
            with open(image_path, "rb") as file:
                payload = {"key": self.api_key}
                files = {"image": file}
                response = requests.post(self.upload_url, payload, files=files)
                if response.status_code == 200:
                    return response.json()["data"]["url"]
        except Exception as e:
            print(f"ImgBB Upload failed: {e}")
        return None

def send_line_notify(market_data, image_url):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id: return
    
    # Flex Message
    # Color: Metal Grey
    
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#434b57", 
            "contents": [
                {"type": "text", "text": "金屬原物料行情", "weight": "bold", "color": "#FFFFFF", "size": "xl"}
            ]
        },
        "hero": {
            "type": "image",
            "url": image_url,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "uri": image_url}
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "銅價 (Copper ETF)", "size": "sm", "color": "#888888", "flex": 1},
                        {"type": "text", "text": f"${market_data['copper']}", "size": "md", "color": "#b87333", "weight": "bold", "align": "end"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "中鋼 (2002.TW)", "size": "sm", "color": "#888888", "flex": 1},
                        {"type": "text", "text": f"${market_data['china_steel']}", "size": "md", "color": "#434b57", "weight": "bold", "align": "end"}
                    ]
                },
                 {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "豐興 (2015.TW)", "size": "sm", "color": "#888888", "flex": 1},
                        {"type": "text", "text": f"${market_data['feng_hsin']}", "size": "md", "color": "#434b57", "weight": "bold", "align": "end"}
                    ]
                },
                 {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "大成鋼 (2027.TW)", "size": "sm", "color": "#888888", "flex": 1},
                        {"type": "text", "text": f"${market_data['da_cheng']}", "size": "md", "color": "#C0C0C0", "weight": "bold", "align": "end"}
                    ]
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                 {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "參考: 鋼筋/廢鐵 (盤價)", "size": "xxs", "color": "#aaaaaa", "flex": 1},
                         {"type": "text", "text": f"${market_data['rebar_ref']} / ${market_data['scrap_ref']}", "size": "xs", "color": "#aaaaaa", "align": "end"}
                    ]
                }
            ]
        }
    }
    
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "flex",
                "altText": "今日金屬行情",
                "contents": {"type": "carousel", "contents": [bubble]}
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    requests.post("https://api.line.me/v2/bot/message/push", headers=headers, data=json.dumps(payload))
    print("LINE notification sent.")

def main():
    data = fetch_market_data()
    if not data: return
    
    records = update_sheet_and_get_history(data)
    # Get latest rebar from records for display
    if records:
        data["rebar"] = records[-1]["Steel_Rebar_TWD_Ton"]
    
    plot_file = plot_trends(records)
    
    load_dotenv()
    imgbb = ImgBBUploader(os.environ.get("IMGBB_API_KEY"))
    url = imgbb.upload(plot_file)
    print(f"Chart uploaded: {url}")
    
    send_line_notify(data, url)

if __name__ == "__main__":
    main()
