
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
    
    # Load Config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stocks.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Config load failed: {e}")
        config = {"stocks": {"2002.TW": "中鋼", "2015.TW": "豐興", "2027.TW": "大成鋼"}}

    stock_tickers = list(config["stocks"].keys())
    base_tickers = ["CPER", "TWD=X", "GC=F", "SI=F"]
    
    tickers = base_tickers + stock_tickers
    # Fetch 5 days to ensure we get a valid close price even on weekends
    data = yf.download(tickers, period="5d")
    
    try:
        if data.empty:
            print("No data fetched.")
            return None

        # Helper to get last valid float
        def get_last_valid(series):
            try:
                valid = series.dropna()
                if valid.empty: return None
                val = float(valid.iloc[-1])
                import math
                if math.isnan(val) or math.isinf(val): return None
                return val
            except:
                return None
            
        hg = get_last_valid(data["Close"]["CPER"])
        twd = get_last_valid(data["Close"]["TWD=X"])
        gold = get_last_valid(data["Close"]["GC=F"])
        silver = get_last_valid(data["Close"]["SI=F"])
        
        # Dynamic Stocks
        stock_prices = {}
        for ticker in stock_tickers:
            stock_prices[ticker] = get_last_valid(data["Close"][ticker])

        if twd == 0: twd = 32.5 # Fallback
        
        copper_twd = hg * twd
        
        result = {
            "copper": round(copper_twd, 2) if copper_twd else None,
            "nickel": 0, 
            "gold": gold,
            "silver": silver,
            "rebar_ref": 16900,
            "scrap_ref": 8600,
            "twd": twd,
            "stocks": stock_prices 
        }
        # Backward compatibility
        result["china_steel"] = stock_prices.get("2002.TW")
        result["feng_hsin"] = stock_prices.get("2015.TW")
        result["da_cheng"] = stock_prices.get("2027.TW")
        
        return result
    except Exception as e:
        print(f"Error parsing yfinance: {e}")
        return None

def update_sheet_and_get_history(market_data):
    sheet = get_google_sheet()
    if not sheet: return None
    
    try:
        ws = sheet.worksheet("Metal_Prices")
        headers = ws.row_values(1)
        expected_headers = ["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price", "Gold_USD", "Silver_USD", "Exchange_Rate_TWD"]
        if  len(headers) < 9:
             ws.update('A1:I1', [expected_headers])
             print("Updated Sheet Headers.")
    except:
        print("Worksheet not found, creating new one...")
        ws = sheet.add_worksheet("Metal_Prices", 1000, 10)
        ws.append_row(["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price", "Gold_USD", "Silver_USD", "Exchange_Rate_TWD"])
        
    all_values = ws.get_all_values()
    last_row = all_values[-1] if len(all_values) > 1 else None
    
    current_rebar = 16900 
    if last_row:
        try:
            current_rebar = float(last_row[2])
        except:
            pass
            
    today = datetime.now().strftime("%Y-%m-%d")
    
    if last_row and last_row[0] == today:
        print("Today already exists in Sheet, skipping append.")
    else:
        new_row = [
            today,
            market_data["copper"],
            current_rebar,         
            market_data["nickel"], 
            market_data["china_steel"], 
            market_data["feng_hsin"],   
            market_data["gold"],
            market_data["silver"],
            market_data["twd"]
        ]
        # Replace None with empty string for Sheet
        final_row = ["" if x is None else x for x in new_row]
        ws.append_row(final_row)
        print(f"Appended to Sheet: {final_row}")
        
    return ws.get_all_records()

def plot_trends(data, filename="metal_trend.png"):
    if not data: return None
    
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Generic numeric conversion for known columns
    cols_to_numeric = ["Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price"]
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    import platform
    if platform.system() == "Windows":
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
        plt.rcParams['axes.unicode_minus'] = False
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    
    # Top: Copper
    ax1.set_title("國際原物料趨勢 (銅 / 鎳指標)", fontsize=14, fontweight="bold")
    ax1.plot(df["Date"], df["Copper_TWD_Kg"], color="#b87333", label="銅價 (TWD/Kg)", linewidth=2)
    ax1.set_ylabel("價格指數", fontsize=12)
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    # Bottom: Stocks & Rebar
    ax2.set_title("國內鋼鐵行情", fontsize=14, fontweight="bold")
    ax2_left = ax2
    ax2_right = ax2.twinx()
    
    if "China_Steel_Price" in df.columns:
        l1 = ax2_left.plot(df["Date"], df["China_Steel_Price"], color="#4682B4", label="中鋼", linewidth=2)
    else:
        l1 = []
        
    if "Feng_Hsin_Price" in df.columns:
        l2 = ax2_left.plot(df["Date"], df["Feng_Hsin_Price"], color="#2E8B57", label="豐興", linewidth=2)
    else:
        l2 = []
        
    ax2_left.set_ylabel("股價 (TWD)", fontsize=12)
    
    l3 = ax2_right.plot(df["Date"], df["Steel_Rebar_TWD_Ton"], color="#708090", label="鋼筋", linewidth=2, linestyle="--")
    ax2_right.set_ylabel("鋼筋盤價", fontsize=12, color="#708090")
    
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
                        {"type": "text", "text": "銅價", "size": "sm", "color": "#888888", "flex": 1},
                        {"type": "text", "text": f"${market_data['copper']}", "size": "md", "color": "#b87333", "weight": "bold", "align": "end"}
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
    
    # Update GSheet (Only basic columns)
    update_sheet_and_get_history(data)
    
    # Update JSON (Dynamic)
    json_path = "docs/metal_data.json"
    existing_data = []
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    record = {
        "Date": today_str,
        "Copper_TWD_Kg": data["copper"],
        "Steel_Rebar_TWD_Ton": data["rebar_ref"],
        "Stainless_Index": data["nickel"],
        "China_Steel_Price": data["china_steel"],
        "Feng_Hsin_Price": data["feng_hsin"],
        "Gold_USD": data["gold"],
        "Silver_USD": data["silver"],
        "Exchange_Rate_TWD": data["twd"]
    }
    # Dynamic Stocks
    for code, price in data["stocks"].items():
        record[f"Stock_{code}"] = price
        
    updated = False
    for i, row in enumerate(existing_data):
        if row["Date"] == today_str:
            existing_data[i] = record
            updated = True
            break
    if not updated:
        existing_data.append(record)
        
    # Export JSON
    # Ensure docs dir exists
    if not os.path.exists("docs"):
        os.makedirs("docs")
        
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    print("Dashboard data exported to docs/metal_data.json")
    
    # Export Config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stocks.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        with open("docs/metal_config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    # Plot & Notify
    # Note: plot_trends reads from DataFrame made of `existing_data` if we passed it,
    # but currently we aren't passing `existing_data` to plot_trends in this clean version?
    # Ah, I missed passing it.
    
    plot_file = plot_trends(existing_data)
    
    load_dotenv()
    imgbb = ImgBBUploader(os.environ.get("IMGBB_API_KEY"))
    url = imgbb.upload(plot_file)
    print(f"Chart uploaded: {url}")
    
    send_line_notify(data, url)

if __name__ == "__main__":
    main()
