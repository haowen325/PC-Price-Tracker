
import os
import json
import gspread
import yfinance as yf
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

def get_google_sheet():
    load_dotenv()
    json_path = os.environ.get("GSPREAD_JSON")
    sheet_url = os.environ.get("GOOGLE_SHEET_URL")
    
    if not json_path or not sheet_url:
        print("Missing secrets in .env")
        return None

    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                creds_dict = json.load(f)
        else:
            creds_dict = json.loads(json_path)
            
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open_by_url(sheet_url)
        return sheet
    except Exception as e:
        print(f"Error connecting to GSheet: {e}")
        return None

def fetch_history_data(start_date="2024-01-01"):
    print(f"Fetching yfinance data from {start_date}...")
    tickers = ["CPER", "TWD=X", "2002.TW", "2015.TW", "2027.TW"]
    df = yf.download(tickers, start=start_date)
    
    # Process
    rows = []
    # yfinance multi-index columns: ('Close', '2002.TW')
    # We need to iterate by date
    
    for date, row in df.iterrows():
        try:
            date_str = date.strftime("%Y-%m-%d")
            
            # Extract values (handle NaNs)
            def get_val(ticker):
                try:
                    val = row["Close"][ticker]
                    return float(val) if pd.notnull(val) else 0.0
                except:
                    return 0.0

            cper = get_val("CPER")
            twd = get_val("TWD=X")
            china_steel = get_val("2002.TW")
            feng_hsin = get_val("2015.TW")
            stainless = get_val("2027.TW") # Using Da Cheng as proxy for Stainless Index
            
            if twd == 0: twd = 32.0 # Fallback
            
            copper_twd = round(cper * twd, 2)
            
            # Rebar: No historical data, leave empty or use 0
            # We will generate a list compatible with GSheet
            # Header: Date, Copper, Rebar, Stainless, ChinaSteel, FengHsin
            
            json_row = {
                "Date": date_str,
                "Copper_TWD_Kg": copper_twd,
                "Steel_Rebar_TWD_Ton": "", # Missing
                "Stainless_Index": stainless,
                "China_Steel_Price": china_steel,
                "Feng_Hsin_Price": feng_hsin
            }
            rows.append(json_row)
        except Exception as e:
            print(f"Error processing {date}: {e}")
            
    print(f"Processed {len(rows)} days of data.")
    return rows

def backfill_main():
    sheet = get_google_sheet()
    if not sheet: return

    try:
        ws = sheet.worksheet("Metal_Prices")
    except:
        ws = sheet.add_worksheet("Metal_Prices", 1000, 10)

    # 1. Fetch Data
    history_data = fetch_history_data(start_date="2024-01-01")
    
    # 2. Update JSON immediately (for user gratification)
    if not os.path.exists("docs"): os.makedirs("docs")
    with open("docs/metal_data.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print("Updated docs/metal_data.json")

    # 3. Update Google Sheet (Overwrite)
    print("Updating Google Sheet (this may take a moment)...")
    
    # Prepare list of lists
    headers = ["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price"]
    values = [headers]
    
    for r in history_data:
        values.append([
            r["Date"], 
            r["Copper_TWD_Kg"], 
            r["Steel_Rebar_TWD_Ton"], 
            r["Stainless_Index"], 
            r["China_Steel_Price"], 
            r["Feng_Hsin_Price"]
        ])
    
    ws.clear()
    ws.update(values)
    print("Google Sheet updated successfully.")

if __name__ == "__main__":
    backfill_main()
