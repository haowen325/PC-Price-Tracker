
import json
import yfinance as yf
import pandas as pd
from datetime import datetime

def backfill_json():
    json_path = "docs/metal_data.json"
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("docs/metal_data.json not found.")
        return

    # Get date range
    dates = [d["Date"] for d in data]
    start_date = dates[0]
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Backfilling stock data from {start_date} to {end_date}...")
    
    tickers = ["2002.TW", "2015.TW"]
    # Fetch data
    df = yf.download(tickers, start=start_date, end=end_date)
    
    # Fill data
    updated_count = 0
    for entry in data:
        date_str = entry["Date"]
        try:
            # Check if we have data for this date
            # yfinance returns Timestamp index
            ts = pd.Timestamp(date_str)
            
            if ts in df.index:
                # China Steel
                if not entry.get("China_Steel_Price") or entry["China_Steel_Price"] == "":
                     val = df["Close"]["2002.TW"].loc[ts]
                     entry["China_Steel_Price"] = float(val)
                
                # Feng Hsin
                if not entry.get("Feng_Hsin_Price") or entry["Feng_Hsin_Price"] == "":
                     val = df["Close"]["2015.TW"].loc[ts]
                     entry["Feng_Hsin_Price"] = float(val)
                
                updated_count += 1
        except Exception as e:
            # Date might be missing in stock data (weekend/holiday)
            # If missing, we can forward fill from previous or leave as null (plotly handles null)
            # But the JSON currently has "", let's change to null if not found
            if entry.get("China_Steel_Price") == "": entry["China_Steel_Price"] = None
            if entry.get("Feng_Hsin_Price") == "": entry["Feng_Hsin_Price"] = None
            pass

    # Save
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Backfill complete. Updated {updated_count} records.")

if __name__ == "__main__":
    backfill_json()
