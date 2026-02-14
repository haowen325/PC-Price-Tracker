import os
import sys
import json
import time
import base64
import requests
import gspread
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
    {"name": "RAM", "model": "LancerBlade"}, 
    {"name": "SSD", "model": "T700 2TB"}, 
    {"name": "Cooler", "model": "TUF GAMING LC III 360 ARGB"},
    {"name": "VGA", "model": "TUF-RTX5070Ti-O16G"},
    {"name": "Case", "model": "GT502 Horizon"},
    {"name": "PSU", "model": "TITAN GOLD 1000W"},
    {"name": "OS", "model": "Windows 11 Pro"}
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

    def send_report(self, date_str, coolpc_total, sinya_total, image_url=None, sheet_url=None):
        if not self.access_token or not self.user_id:
            print("LINE Messaging API credentials not set.")
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }

        title_text = f"[{date_str}] 價格追蹤報告"
        
        # Build Flex Message Content (JSON)
        contents = {
            "type": "bubble",
            "direction": "ltr",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": title_text, "weight": "bold", "size": "xl"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "原價屋:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": f"${coolpc_total:,}", "weight": "bold", "color": "#666666", "size": "sm", "flex": 4}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "欣亞:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": f"${sinya_total:,}", "weight": "bold", "color": "#666666", "size": "sm", "flex": 4}
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        # Add Hero Image
        if image_url:
            contents["hero"] = {
                "type": "image",
                "url": image_url,
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover",
                "action": {"type": "uri", "uri": image_url, "label": "View Chart"}
            }

        # Add Footer Button
        if sheet_url:
            contents["footer"] = {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "查看詳細清單", "uri": sheet_url}
                    }
                ]
            }

        message_payload = {
            "type": "flex",
            "altText": f"今日價格: 原價屋 ${coolpc_total} / 欣亞 ${sinya_total}",
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
                text_msg = f"{title_text}\n原價屋: ${coolpc_total:,}\n欣亞: ${sinya_total:,}"
                if sheet_url:
                    text_msg += f"\n詳細清單: {sheet_url}"
                
                fallback_data = {
                    "to": self.user_id,
                    "messages": [{"type": "text", "text": text_msg}]
                }
                requests.post(self.api_url, headers=headers, json=fallback_data)
                print("Fallback text message sent.")

        except Exception as e:
            print(f"Error sending LINE message: {e}")

class SheetManager:
    def __init__(self, json_key_content, sheet_name):
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
            sheet_url = os.environ.get("GOOGLE_SHEET_URL")
            if sheet_url:
                self.sheet = self.client.open_by_url(sheet_url)
                print(f"Opened spreadsheet by URL: {sheet_url}")
            else:
                self.sheet = self.client.open(sheet_name)
                print(f"Opened spreadsheet by name: {sheet_name}")

            try:
                self.worksheet = self.sheet.worksheet(WORKSHEET_NAME)
            except gspread.WorksheetNotFound:
                print(f"Worksheet '{WORKSHEET_NAME}' not found, creating it...")
                self.worksheet = self.sheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=10)
                self.worksheet.append_row(["Date", "Vendor", "Component", "Model", "Price"])
        except gspread.SpreadsheetNotFound:
            print(f"Spreadsheet '{sheet_name}' not found. Please create it and share with the service account.")
            raise

    def append_data(self, date_str, vendor, component, model, price):
        self.worksheet.append_row([date_str, vendor, component, model, price])

    def get_all_data(self):
        return self.worksheet.get_all_records()

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
                
                # 在所有選項中尋找
                # 為了避免誤判 (例如 "64G" 匹配到 "16G"), 使用簡單的字串包含檢查
                # 改進：優先匹配包含最多關鍵字的選項 -> 這裡簡單處理
                for opt in options:
                    if model_keyword.lower() in opt.lower():
                        # 特別處理 RAM: "64G" vs "16G" (目前依賴 unique model key "LancerBlade")
                        try:
                            if '$' in opt:
                                parts = opt.split('$')
                                price_part = parts[-1].strip()
                                match = re.search(r'(\d+)', price_part)
                                if match:
                                    found_price = int(match.group(1))
                                    break 
                        except:
                            continue
                
                if found_price > 0:
                    prices[target["name"]] = found_price
                    print(f"[Coolpc] Found {target['name']}: ${found_price}")
                else:
                    print(f"[Coolpc] Not found: {target['name']}")
                    prices[target["name"]] = 0 

        except Exception as e:
            print(f"Error scraping Coolpc: {e}")
        finally:
            page.close()
        
        return prices

class SinyaScraper:
    def __init__(self, browser):
        self.search_base_url = "https://www.sinya.com.tw/prod/search"
        self.browser = browser

    def scrape(self):
        print("Scraping Sinya...")
        prices = {}
        page = self.browser.new_page()
        
        try:
            for target in TARGETS:
                keyword = target["model"]
                search_link = f"{self.search_base_url}?q={requests.utils.quote(keyword)}"
                
                try:
                    page.goto(search_link)
                    page.wait_for_timeout(1000)
                    
                    price_locator = page.locator(".prod_price, .price").first
                    
                    if price_locator.count() > 0:
                        price_text = price_locator.text_content().strip()
                        match = re.search(r'(\d+)', price_text.replace(',', ''))
                        if match:
                            price_val = int(match.group(1))
                            prices[target["name"]] = price_val
                            print(f"[Sinya] Found {target['name']}: ${price_val}")
                        else:
                            prices[target["name"]] = 0
                    else:
                        print(f"[Sinya] Not found: {target['name']}")
                        prices[target["name"]] = 0
                        
                except Exception as e:
                    print(f"[Sinya] Error scraping {keyword}: {e}")
                    prices[target["name"]] = 0
        finally:
            page.close()
            
        return prices

def plot_trend(data_records, output_file="trend.png"):
    if not PLOTTING_AVAILABLE:
        print("Skipping plot: libraries not available.")
        return

    if not data_records:
        return
    
    df = pd.DataFrame(data_records)
    if 'Date' not in df.columns or 'Price' not in df.columns or 'Vendor' not in df.columns:
        return

    try:
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'])
        
        daily_vendor_sum = df.groupby(['Date', 'Vendor'])['Price'].sum().reset_index()
        
        if daily_vendor_sum.empty:
            return

        plt.figure(figsize=(10, 6))
        pivot_df = daily_vendor_sum.pivot(index='Date', columns='Vendor', values='Price')
        
        for vendor in pivot_df.columns:
            plt.plot(pivot_df.index, pivot_df[vendor], marker='o', label=vendor)
            
        plt.title("PC Price Trend")
        plt.xlabel("Date")
        plt.ylabel("Total Price (TWD)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_file)
        print(f"Plot saved to {output_file}")
    except Exception as e:
        print(f"Error plotting trend: {e}")

def main():
    if not GSPREAD_JSON:
        print("Error: GSPREAD_JSON not set.")
        return

    print(f"Starting job at {datetime.now()}")
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    coolpc_prices = {}
    sinya_prices = {}
    
    # 1. Scrape
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        coolpc_scraper = CoolpcScraper(browser)
        coolpc_prices = coolpc_scraper.scrape()
        
        sinya_scraper = SinyaScraper(browser)
        sinya_prices = sinya_scraper.scrape()
        browser.close()

    # 2. Save
    try:
        sheet = SheetManager(GSPREAD_JSON, SHEET_NAME)
        
        coolpc_total = 0
        for comp_name, price in coolpc_prices.items():
            model = next((t['model'] for t in TARGETS if t['name'] == comp_name), "")
            sheet.append_data(date_str, "Coolpc", comp_name, model, price)
            coolpc_total += price
            
        sinya_total = 0
        for comp_name, price in sinya_prices.items():
            model = next((t['model'] for t in TARGETS if t['name'] == comp_name), "")
            sheet.append_data(date_str, "Sinya", comp_name, model, price)
            sinya_total += price
            
        print("-" * 30)
        print(f"Date: {date_str}")
        print(f"Coolpc Total: ${coolpc_total:,}")
        print(f"Sinya Total: ${sinya_total:,}")
        print("-" * 30)
        print("Coolpc Details:")
        for k, v in coolpc_prices.items():
            print(f"  {k}: ${v:,}")
        print("Sinya Details:")
        for k, v in sinya_prices.items():
            print(f"  {k}: ${v:,}")
        print("-" * 30)
        
        print("Data saved to Google Sheets.")
        
        # 3. Plot & Notify
        history = sheet.get_all_data()
        plot_file = "price_trend.png"
        plot_trend(history, plot_file)
        
        # Image Upload (ImgBB)
        image_url = None
        if IMGBB_API_KEY and os.path.exists(plot_file):
            uploader = ImgBBUploader(IMGBB_API_KEY)
            image_url = uploader.upload(plot_file)
            print(f"Image uploaded: {image_url}")
        
        # LINE Notification
        notifier = LineBotNotifier(LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID)
        notifier.send_report(date_str, coolpc_total, sinya_total, image_url, GOOGLE_SHEET_URL)
        
    except Exception as e:
        print(f"Error in post-processing: {e}")
        # Send error notification
        if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID:
             # Very basic error handler
             pass

if __name__ == "__main__":
    main()
