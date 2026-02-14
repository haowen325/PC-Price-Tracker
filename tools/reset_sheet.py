
import os
import gspread
import json
from dotenv import load_dotenv

# Works even if run from tools/ or root
load_dotenv()

# Hardcoded or imported from main.py if possible, but safer to re-define here to be standalone
WORKSHEET_NAME = "Price_History" 

def reset_sheet():
    json_val = os.environ.get("GSPREAD_JSON")
    sheet_url = os.environ.get("GOOGLE_SHEET_URL")
    
    if not json_val or not sheet_url:
        print("Error: GSPREAD_JSON or GOOGLE_SHEET_URL not set in .env")
        return

    # Handle file path or content
    if os.path.exists(json_val):
        gc = gspread.service_account(filename=json_val)
    else:
        try:
            creds = json.loads(json_val)
            gc = gspread.service_account_from_dict(creds)
        except json.JSONDecodeError:
             print("Error: GSPREAD_JSON is not a file and not valid JSON.")
             return

    try:
        sh = gc.open_by_url(sheet_url)
        print(f"Opened sheet: {sh.title}")
        
        try:
            ws = sh.worksheet(WORKSHEET_NAME)
            print(f"Clearing worksheet '{WORKSHEET_NAME}'...")
            ws.clear()
        except gspread.WorksheetNotFound:
            print(f"Worksheet '{WORKSHEET_NAME}' not found, creating...")
            ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=10)
        
        print("Adding headers...")
        # New Header Format: Date, Vendor, Total Price, Details
        ws.append_row(["Date", "Vendor", "Total Price", "Details"])
        print("Sheet reset complete.")
        
    except Exception as e:
        print(f"Error resetting sheet: {e}")

if __name__ == "__main__":
    reset_sheet()
