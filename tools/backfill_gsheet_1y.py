
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
    tickers = ["CPER", "TWD=X", "2002.TW", "2015.TW", "2027.TW", "GC=F", "SI=F"]
    df = yf.download(tickers, start=start_date)
    
    # Process
    rows = []
    
    for date, row in df.iterrows():
        try:
            date_str = date.strftime("%Y-%m-%d")
            
            # Extract values (handle NaNs and 0s)
            def get_val(ticker):
                try:
                    val = row["Close"][ticker]
                    # Check for NaN or 0
                    if pd.isna(val) or val == 0:
                        return None
                    return float(val)
                except:
                    return None

            cper = get_val("CPER")
            twd = get_val("TWD=X")
            china_steel = get_val("2002.TW")
            feng_hsin = get_val("2015.TW")
            stainless = get_val("2027.TW")
            gold = get_val("GC=F")
            silver = get_val("SI=F")
            
            # Copper in TWD
            copper_twd = None
            if cper and twd:
                copper_twd = round(cper * twd, 2)
            elif cper:
                # Fallback TWD if missing
                copper_twd = round(cper * 32.5, 2)
            
            # Rebar: Leave empty/null
            
            json_row = {
                "Date": date_str,
                "Copper_TWD_Kg": copper_twd,
                "Steel_Rebar_TWD_Ton": None, 
                "Stainless_Index": stainless,
                "China_Steel_Price": china_steel,
                "Feng_Hsin_Price": feng_hsin,
                "Gold_USD": gold,
                "Silver_USD": silver,
                "Exchange_Rate_TWD": twd
            }
            
            # Additional logic: If all main values are None, skip the Saturday/Sunday entirely
            # yfinance usually excludes them, but just in case.
            if copper_twd is None and china_steel is None and gold is None:
                continue
                
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
    
    # 2. Update JSON
    if not os.path.exists("docs"): os.makedirs("docs")
    with open("docs/metal_data.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print("Updated docs/metal_data.json")

    # 3. Update Google Sheet (Overwrite)
    print("Updating Google Sheet...")
    
    headers = ["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index", "China_Steel_Price", "Feng_Hsin_Price", "Gold_USD", "Silver_USD", "Exchange_Rate_TWD"]
    values = [headers]
    
    for r in history_data:
        # Convert None to "" for GSheet
        row = [
            r["Date"], 
            r["Copper_TWD_Kg"] if r["Copper_TWD_Kg"] is not None else "",
            r["Steel_Rebar_TWD_Ton"] if r["Steel_Rebar_TWD_Ton"] is not None else "",
            r["Stainless_Index"] if r["Stainless_Index"] is not None else "",
            r["China_Steel_Price"] if r["China_Steel_Price"] is not None else "",
            r["Feng_Hsin_Price"] if r["Feng_Hsin_Price"] is not None else "",
            r["Gold_USD"] if r["Gold_USD"] is not None else "",
            r["Silver_USD"] if r["Silver_USD"] is not None else "",
            r["Exchange_Rate_TWD"] if r["Exchange_Rate_TWD"] is not None else ""
        ]
        values.append(row)
    
    ws.clear()
    ws.update(values)
    print("Google Sheet updated successfully.")

if __name__ == "__main__":
    backfill_main()
