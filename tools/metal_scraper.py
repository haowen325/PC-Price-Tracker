
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
        if not json_str.strip():
             print("GSPREAD_JSON is empty.")
             return None
        
        # Check if it's a file path
        if os.path.exists(json_str):
            with open(json_str, "r", encoding="utf-8") as f:
                creds_dict = json.load(f)
        else:
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
        # Check/Update Headers
        headers = ws.row_values(1)
        expected_headers = ["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price"]
        if  len(headers) < 6:
             ws.update('A1:F1', [expected_headers])
             print("Updated Sheet Headers to include stock prices.")
    except:
        print("Worksheet not found, creating new one...")
        ws = sheet.add_worksheet("Metal_Prices", 1000, 10)
        ws.append_row(["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price"])
        
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
            market_data["copper"], # Copper_TWD_Kg
            current_rebar,         # Steel_Rebar_TWD_Ton
            market_data["nickel"], # Stainless_Index
            market_data["china_steel"], # China_Steel_Price
            market_data["feng_hsin"]    # Feng_Hsin_Price
        ]
        ws.append_row(new_row)
        print(f"Appended: {new_row}")
        
    return ws.get_all_records()

def plot_trends(data, filename="metal_trend.png"):
    if not data: return None
    
    
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Force convert to numeric, coercing errors to NaN
    cols_to_numeric = ["Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price"]
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Drop rows where critical data is NaN if needed, or just fillna?
    # Matplotlib handles NaN gracefully (breaks line), which is what we want.

    
    # Enable Chinese Font (Windows)
    import platform
    if platform.system() == "Windows":
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
        plt.rcParams['axes.unicode_minus'] = False
    
    # Create 2 Subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    
    # Plot 1: International/ETF (Copper, Stainless Proxy)
    ax1.set_title("國際原物料趨勢 (銅 / 鎳指標)", fontsize=14, fontweight="bold")
    ax1.plot(df["Date"], df["Copper_TWD_Kg"], color="#b87333", label="銅價 (TWD/Kg)", linewidth=2)
    ax1.plot(df["Date"], df["Stainless_Index"], color="#C0C0C0", label="鎳ETF (不鏽鋼指標)", linewidth=2, linestyle="-.")
    ax1.set_ylabel("價格指數", fontsize=12)
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    # Plot 2: Domestic Steel (China Steel, Feng Hsin, Rebar)
    ax2.set_title("國內鋼鐵行情 (中鋼 / 豐興 / 鋼筋)", fontsize=14, fontweight="bold")
    
    # Rebar (High value ~17000) - use secondary axis on subplot 2? 
    # Actually China Steel is ~20, Rebar is ~17000. Still huge difference.
    # Let's put Stock Prices (20-100) on Left, Rebar (17000) on Right.
    
    ax2_left = ax2
    ax2_right = ax2.twinx()
    
    # Left Axis: Stocks
    l1 = ax2_left.plot(df["Date"], df["China_Steel_Price"], color="#4682B4", label="中鋼 (2002)", linewidth=2)
    l2 = ax2_left.plot(df["Date"], df["Feng_Hsin_Price"], color="#2E8B57", label="豐興 (2015)", linewidth=2)
    ax2_left.set_ylabel("股價 (TWD)", fontsize=12)
    
    # Right Axis: Rebar
    l3 = ax2_right.plot(df["Date"], df["Steel_Rebar_TWD_Ton"], color="#708090", label="鋼筋盤價 (TWD/噸)", linewidth=2, linestyle="--")
    ax2_right.set_ylabel("鋼筋盤價 (TWD/噸)", fontsize=12, color="#708090")
    
    # Combine Legends
    lines = l1 + l2 + l3
    labels = [l.get_label() for l in lines]
    ax2_left.legend(lines, labels, loc="upper left")
    
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.set_xlabel("日期", fontsize=12)
    
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
            "url": image_url if image_url else "https://img.icons8.com/color/48/average-2.png",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "uri": "https://haowen325.github.io/PC-Price-Tracker/"}
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
                },

                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "中鋼股價",
                                "uri": "https://tw.stock.yahoo.com/quote/2002.TW"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "豐興股價",
                                "uri": "https://tw.stock.yahoo.com/quote/2015.TW"
                            }
                        }
                    ]
                },
                 {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "margin": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📊 查看互動儀表板",
                        "uri": "https://haowen325.github.io/PC-Price-Tracker/"
                    }
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
    
    # Export for Dashboard
    # Ensure docs dir exists
    if not os.path.exists("docs"):
        os.makedirs("docs")
        
    with open("docs/metal_data.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print("Dashboard data exported to docs/metal_data.json")
    
    send_line_notify(data, url)

if __name__ == "__main__":
    main()
