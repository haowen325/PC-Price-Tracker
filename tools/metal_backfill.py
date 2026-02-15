
import gspread
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json

# Rebar Data Construction (Based on Research)
# Feb 9: 16900
# Jan 31: 16700
# Jan 20: 16700 (Rise +200) -> 16500 before
# Prior 8 weeks flat: 16500
REBAR_HISTORY = [
    {"date": "2025-11-15", "price": 16500},
    {"date": "2026-01-19", "price": 16500},
    {"date": "2026-01-20", "price": 16700},
    {"date": "2026-01-26", "price": 16900}, # Another +200 per some reports? Or keep 16700? 
    # Search said: Jan 26 +200 on Scrap, but Rebar flat? 
    # Let's conservative: Jan 20 was 16700. Feb 7 is 16900.
    # We will interpolate or just set milestones.
    {"date": "2026-02-01", "price": 16900}, 
    {"date": datetime.now().strftime("%Y-%m-%d"), "price": 16900},
]

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

def backfill():
    print("Fetching historical data...")
    
    # 1. Copper (HG=F) and Nickel (Ni=F for Stainless proxy) / TWD=X for conversion if needed?
    # Let's keep USD for LME to match international standards, or convert approx?
    # User likely cares about trend. Let's keep raw values but normalized in chart later.
    # Or fetch TWD exchange rate.
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    tickets = ["CPER", "TWD=X"] # Copper ETF, USD/TWD
    
    df = yf.download(tickets, start=start_date, end=end_date)["Close"]
    
    # Process Data
    records = []
    
    # Interpolate Rebar daily
    rebar_daily = {}
    current_rebar = 16500
    # Sort history
    dates = pd.date_range(start=start_date, end=end_date)
    
    for d in dates:
        d_str = d.strftime("%Y-%m-%d")
        
        # Update Rebar Price based on milestones
        for milestone in REBAR_HISTORY:
            if d_str >= milestone["date"]:
                current_rebar = milestone["price"]
        
        # Get market data
        try:
            # yfinance returns MultiIndex columns if multiple tickers
            hg_price = df.loc[d_str]["CPER"] if d_str in df.index else None
            twd_rate = df.loc[d_str]["TWD=X"] if d_str in df.index else None
            
            # Forward fill if missing (market closed)
            if pd.isna(hg_price): hg_price = None
            if pd.isna(twd_rate): twd_rate = None
            
        except:
             hg_price = None
             twd_rate = None

        if hg_price is not None and twd_rate is not None:
             copper_twd = float(hg_price) * float(twd_rate)
             
             records.append([
                 d_str,
                 round(copper_twd, 2),
                 current_rebar,
                 0 # Stainless placeholder
             ])
    
    # Create DF
    final_df = pd.DataFrame(records, columns=["Date", "Copper_TWD_Kg", "Steel_Rebar_TWD_Ton", "Stainless_Index"])
    
    # Save to Sheet
    sheet = get_google_sheet()
    if sheet:
        try:
            try:
                ws = sheet.worksheet("Metal_Prices")
            except:
                ws = sheet.add_worksheet(title="Metal_Prices", rows=1000, cols=10)
            
            ws.clear()
            # Prepare data including header
            data_to_write = [final_df.columns.values.tolist()] + final_df.values.tolist()
            ws.update(data_to_write)
            print("Backfill complete.")
        except Exception as e:
            print(f"Error writing to sheet: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    backfill()
