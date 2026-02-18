
import os
import json
import gspread
import yfinance as yf
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

def backfill_dynamic():
    # Load Config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stocks.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Config load failed: {e}")
        return

    stock_map = config["stocks"]
    stock_tickers = list(stock_map.keys())
    base_tickers = ["CPER", "TWD=X", "GC=F", "SI=F"]
    all_tickers = base_tickers + stock_tickers
    
    start_date = "2024-01-01"
    print(f"Fetching full history for {len(all_tickers)} tickers since {start_date}...")
    
    df = yf.download(all_tickers, start=start_date)
    
    rows = []
    
    # Iterate by date (index)
    for index, row in df.iterrows():
        try:
            date_str = index.strftime("%Y-%m-%d")
            
            # Helper
            def get_val(ticker_col):
                try:
                    # Handle MultiIndex if multiple tickers
                    if isinstance(row["Close"], pd.Series): 
                         # If only 1 ticker, it's a series? No, yfinance always multi-index if list > 1
                         pass
                    
                    val = row["Close"][ticker_col]
                    if pd.isna(val) or val == 0: return None
                    return float(val)
                except:
                    return None

            cper = get_val("CPER")
            twd = get_val("TWD=X")
            gold = get_val("GC=F")
            silver = get_val("SI=F")
            
            copper_twd = None
            if cper and twd:
                copper_twd = round(cper * twd, 2)
            elif cper:
                copper_twd = round(cper * 32.5, 2)
                
            json_row = {
                "Date": date_str,
                "Copper_TWD_Kg": copper_twd,
                "Steel_Rebar_TWD_Ton": 18800, # Estimated avg for backfill
                "Stainless_Index": None, 
                "Gold_USD": gold,
                "Silver_USD": silver,
                "Exchange_Rate_TWD": twd
            }
            
            # Dynamic Stocks
            for ticker in stock_tickers:
                price = get_val(ticker)
                json_row[f"Stock_{ticker}"] = price
            
            # Legacy fields for compatibility
            json_row["China_Steel_Price"] = json_row.get("Stock_2002.TW")
            json_row["Feng_Hsin_Price"] = json_row.get("Stock_2015.TW")
            
            # Nickel proxy: Use 2027.TW if available (Da Cheng)
            if json_row.get("Stock_2027.TW"):
                json_row["Stainless_Index"] = json_row["Stock_2027.TW"]

            rows.append(json_row)
            
        except Exception as e:
            print(f"Error row: {e}")

    # Save JSON
    if not os.path.exists("docs"): os.makedirs("docs")
    with open("docs/metal_data.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("Backfill complete. docs/metal_data.json updated.")

if __name__ == "__main__":
    backfill_dynamic()
