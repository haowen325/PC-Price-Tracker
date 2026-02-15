import os
import sys
import json
import time
import base64
import requests
import gspread
import difflib
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    PLOTTING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Plotting libraries not available ({e}). Charts will be skipped.")
    PLOTTING_AVAILABLE = False
except Exception as e:
    print(f"Warning: Error importing plotting libraries ({e}). Charts will be skipped.")
    PLOTTING_AVAILABLE = False
import re
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LINE Bot SDK removed to avoid compatibility issues.
# Using raw requests instead.
LINE_BOT_AVAILABLE = True

# --- Configuration ---
GSPREAD_JSON = os.environ.get("GSPREAD_JSON")
# LINE Messaging API Secrets
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID") 
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY") # 改用 ImgBB
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets")

SHEET_NAME = "PC_Price_Tracker"
WORKSHEET_NAME = "Price_History"

# --- Target Components (Updated from Screenshot) ---
TARGETS = [
    {"name": "CPU", "model": "Core Ultra 7 265KF"},
    {"name": "MB", "model": "TUF GAMING Z890-PRO WIFI"},
    {"name": "RAM", "model": "LancerBlade 64G"}, # Updated to 64G based on user image
    {"name": "SSD", "model": "T700 2TB"}, 
    {"name": "Cooler", "model": "TUF GAMING LC III 360 ARGB"},
    {"name": "VGA", "model": "TUF-RTX5070Ti-O16G"},
    {"name": "Case", "model": "GT502 Horizon"},
    {"name": "PSU", "model": "TITAN GOLD 1000W"},
    {"name": "OS", "model": "Windows 11 Pro 隨機"}, # Updated to OEM version
]

class ImgBBUploader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.imgbb.com/1/upload"

    def upload(self, image_path):
        if not self.api_key:
            print("ImgBB API Key not set.")
            return None
        
        try:
            with open(image_path, "rb") as file:
                payload = {
                    "key": self.api_key,
                    "image": base64.b64encode(file.read()),
                }
                response = requests.post(self.api_url, data=payload)
                if response.status_code == 200:
                    data = response.json()
                    link = data['data']['url']
                    print(f"Image uploaded to ImgBB: {link}")
                    return link
                else:
                    print(f"ImgBB upload failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Error uploading to ImgBB: {e}")
            return None

class LineBotNotifier:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_report(self, date_str, total_price, image_url=None, sheet_url=None, price_diff=0):
        if not self.access_token or not self.user_id:
            print("LINE Messaging API credentials not set.")
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }

        # Determine title and color based on diff
        if price_diff == 0:
            status_text = "價格持平"
            color = "#1DB446" # Green
            diff_text = "(無變動)"
        elif price_diff > 0:
            status_text = "價格上漲"
            color = "#FF334B" # Red
            diff_text = f"(▲ ${price_diff:,})"
        else:
            status_text = "價格下跌"
            color = "#33A1FF" # Blue
            diff_text = f"(▼ ${abs(price_diff):,})"

        title = f"{status_text} {diff_text}"
        
        contents = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "weight": "bold",
                        "size": "xl",
                        "color": color
                    },
                    {
                        "type": "text",
                        "text": f"Date: {date_str}",
                        "size": "xs",
                        "color": "#aaaaaa"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": f"原價屋: ${total_price:,}",
                        "weight": "bold",
                        "size": "xl",
                        "margin": "md"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    }
                ]
            }
        }
        
        # Add Image if exists
        if image_url:
            hero = {
                "type": "image",
                "url": image_url,
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover",
                "action": {
                    "type": "uri",
                    "uri": image_url
                }
            }
            contents["hero"] = hero

        # Add Details Button
        if sheet_url:
             contents["footer"] = {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "查看詳細清單 (Google Sheet)",
                            "uri": sheet_url
                        }
                    }
                ],
                "flex": 0
            }

        message_payload = {
            "type": "flex",
            "altText": f"今日顯卡價格: ${total_price:,} {diff_text}",
            "contents": contents
        }

        data = {
            "to": self.user_id,
            "messages": [message_payload]
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=data)
            if response.status_code == 200:
                print("LINE Flex Message sent successfully.")
            else:
                print(f"Error sending LINE message: {response.status_code} - {response.text}")
                # Fallback to Text Message
                text_msg = f"{title}\n原價屋: ${total_price:,}\n請查看 Sheet 了解詳情。"
                fallback_data = {
                    "to": self.user_id,
                    "messages": [{"type": "text", "text": text_msg}]
                }
                requests.post(self.api_url, headers=headers, json=fallback_data)
                print("Fallback text message sent.")

        except Exception as e:
            print(f"Error sending LINE message: {e}")

class SheetManager:
    def __init__(self, json_key_content, sheet_url):
        self.scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if os.path.exists(json_key_content):
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(json_key_content, self.scope)
        else:
            try:
                key_dict = json.loads(json_key_content)
                self.creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, self.scope)
            except json.JSONDecodeError:
                try:
                    decoded = base64.b64decode(json_key_content).decode('utf-8')
                    key_dict = json.loads(decoded)
                    self.creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, self.scope)
                except Exception as e:
                    print(f"Error parsing GSPREAD_JSON: {e}")
                    raise

        self.client = gspread.authorize(self.creds)
        
        try:
            self.sheet = self.client.open_by_url(sheet_url)
            print(f"Opened spreadsheet by URL: {sheet_url}")

            try:
                self.worksheet = self.sheet.worksheet(WORKSHEET_NAME)
            except gspread.WorksheetNotFound:
                print(f"Worksheet '{WORKSHEET_NAME}' not found, creating it...")
                self.worksheet = self.sheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=10)
                # Updated header for new data structure
                self.worksheet.append_row(["Date", "Vendor", "Total Price", "Details"])
        except gspread.SpreadsheetNotFound:
            print(f"Spreadsheet '{sheet_url}' not found. Please create it and share with the service account.")
            raise

    def save_to_sheet(self, data_rows):
        """Appends multiple rows of data to the worksheet."""
        self.worksheet.append_rows(data_rows)
        print(f"Appended {len(data_rows)} rows to Google Sheet.")

    def get_last_price(self, vendor):
        """Retrieves the last recorded total price for a given vendor."""
        try:
            # Get all records and convert to DataFrame for easier filtering
            all_records = self.worksheet.get_all_records()
            if not all_records:
                return 0

            df = pd.DataFrame(all_records)
            
            # Ensure 'Date' is datetime and 'Total Price' is numeric
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Total Price'] = pd.to_numeric(df['Total Price'], errors='coerce').fillna(0)
            
            # Filter by vendor and sort by date to get the latest
            vendor_df = df[df['Vendor'] == vendor].sort_values(by='Date', ascending=False)
            
            if not vendor_df.empty:
                return vendor_df.iloc[0]['Total Price']
            else:
                return 0
        except Exception as e:
            print(f"Error getting last price for {vendor}: {e}")
            return 0

class CoolpcScraper:
    def __init__(self, browser):
        self.url = "https://www.coolpc.com.tw/evaluate.php"
        self.browser = browser

    def scrape(self):
        print("Scraping Coolpc...")
        page = self.browser.new_page()
        prices = {}
        
        try:
            page.goto(self.url)
            page.wait_for_load_state('networkidle')
            
            options = page.locator("select option").all_text_contents()
            
            for target in TARGETS:
                model_keyword = target["model"]
                found_price = 0
                
                # Multi-keyword matching logic
                # Split model_keyword by space and require ALL parts to be present
                keywords = model_keyword.lower().split()
                candidates = [opt for opt in options if all(k in opt.lower() for k in keywords)]

                if candidates:
                    print(f"DEBUG: Candidates for {target['name']} ({model_keyword}):")
                    for c in candidates:
                         print(f"  - {c}")
                    
                    # If multiple match, logic depends on component type
                    if target["name"] == "Case":
                         # For cases, prefer higher price to avoid accessories (fans, kits)
                         best_match = max(candidates, key=lambda x: self._extract_price(x))
                    else:
                         # Default: pick shortest match (most precise)
                         best_match = min(candidates, key=len)
                    
                    try:
                        price = self._extract_price(best_match)
                        if price > 0:
                            matched_opt = best_match
                            prices[target["name"]] = (price, matched_opt)
                            print(f"[Coolpc] Found {target['name']}: ${price} ({matched_opt})")
                    except:
                        pass
                
                if prices.get(target["name"], (0, ""))[0] == 0:
                    print(f"[Coolpc] Not found: {target['name']}")
                    prices[target["name"]] = (0, "") 

        except Exception as e:
            print(f"Error scraping Coolpc: {e}")
        finally:
            page.close()
        
        return prices

    def _extract_price(self, text):
        try:
            if '$' in text:
                parts = text.split('$')
                price_part = parts[-1].strip()
                match = re.search(r'(\d+)', price_part)
                if match:
                    return int(match.group(1))
        except:
            pass
        return 0

def plot_trend(worksheet, output_file="trend.png"):
    if not PLOTTING_AVAILABLE:
        print("Skipping plot: libraries not available.")
        return None

    try:
        data_records = worksheet.get_all_records()
        if not data_records:
            print("No data to plot.")
            return None
        
        df = pd.DataFrame(data_records)
        
        # Ensure required columns exist
        if 'Date' not in df.columns or 'Total Price' not in df.columns or 'Vendor' not in df.columns:
            print("Missing required columns for plotting (Date, Total Price, Vendor).")
            return None

        df['Total Price'] = pd.to_numeric(df['Total Price'], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Filter for Coolpc data only for this plot
        coolpc_df = df[df['Vendor'] == 'Coolpc'].sort_values(by='Date')
        
        if coolpc_df.empty:
            print("No Coolpc data to plot.")
            return None

        plt.figure(figsize=(10, 6))
        
        plt.plot(coolpc_df['Date'], coolpc_df['Total Price'], marker='o', label='Coolpc Total Price')
            
        plt.title("Coolpc PC Total Price Trend")
        plt.xlabel("Date")
        plt.ylabel("Total Price (TWD)")
        plt.grid(True)
        plt.legend()
        
        # Import mdates locally to ensure it's available
        import matplotlib.dates as mdates
        
        ax = plt.gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1)) # Tick every day
        plt.gcf().autofmt_xdate() # Rotate labels
        
        plt.tight_layout()
        plt.savefig(output_file)
        print(f"Plot saved to {output_file}")
        return output_file
    except Exception as e:
        print(f"Error plotting trend: {e}")
        return None

def main():
    if not GSPREAD_JSON:
        print("Error: GSPREAD_JSON not set.")
        return

    print(f"Starting job at {datetime.now()}")
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    sheet_manager = SheetManager(os.environ["GSPREAD_JSON"], os.environ["GOOGLE_SHEET_URL"])

    # Get previous price BEFORE scraping new one (to compare)
    last_coolpc_price = sheet_manager.get_last_price("Coolpc")
    print(f"Last Coolpc Price: ${last_coolpc_price:,}")
    
    # 1. Scrape
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"]
        )
        coolpc_scraper = CoolpcScraper(browser)
        coolpc_prices = coolpc_scraper.scrape()
        
        # [REMOVED] Sinya scraping
        # sinya_scraper = SinyaScraper(browser)
        # sinya_prices = sinya_scraper.scrape()
        browser.close()

    # 2. Process
    coolpc_total = sum(item[0] for item in coolpc_prices.values())
    
    # 3. Save
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Format details for sheet
    coolpc_detail_str = "\n".join([f"{k}: ${v[0]} ({v[1]})" for k, v in coolpc_prices.items()])
    
    sheet_manager.save_to_sheet([
        [today, "Coolpc", coolpc_total, coolpc_detail_str],
    ])
    
    # 4. Plot
    image_url = None
    try:
        plot_file = plot_trend(sheet_manager.worksheet)
        if plot_file:
            print(f"Plot saved to {plot_file}")
            uploader = ImgBBUploader(os.environ["IMGBB_API_KEY"])
            image_url = uploader.upload(plot_file)
            print(f"Image uploaded: {image_url}")
    except Exception as e:
        print(f"Error in plotting/uploading: {e}")

    # 5. Notify
    try:
        notifier = LineBotNotifier(os.environ["LINE_CHANNEL_ACCESS_TOKEN"], os.environ["LINE_USER_ID"])
        
        # Calculate diff
        diff = coolpc_total - last_coolpc_price
        
        # Send report with diff
        notifier.send_report(today, coolpc_total, image_url, os.environ["GOOGLE_SHEET_URL"], price_diff=diff)
        print("LINE Flex Message sent successfully.")
        
        print("-" * 30)
        print(f"Date: {today}")
        print(f"Coolpc Total: ${coolpc_total:,}")
        print(f"Diff: ${diff:,}")
        print("-" * 30)
        print("Coolpc Details:")
        for k, v in coolpc_prices.items():
            print(f"  {k}: ${v[0]:,} ({v[1]})")
        print("-" * 30)
        
        print("Data saved to Google Sheets.")
    except Exception as e:
        print(f"Error sending LINE notification: {e}")

if __name__ == "__main__":
    main()
