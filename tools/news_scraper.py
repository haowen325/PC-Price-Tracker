
import feedparser
import difflib
import os
import json
import requests
from datetime import datetime
from urllib.parse import quote

# Configuration
RSS_BASE_URL = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

CATEGORIES = [
    {
        "name": "AI 科技",
        "query": "AI OR 人工智慧",
    },
    {
        "name": "AI 工具",
        "query": "AI工具 OR ChatGPT OR Gemini OR Claude",
    },
    {
        "name": "機械板金",
        "query": "機械板金 OR 鈑金 OR 工具機 OR 雷射切割",
    },
    {
        "name": "半導體",
        "query": "半導體 OR TSMC OR 台積電",
    },
    {
        "name": "電動車",
        "query": "電動車 OR EV OR Tesla",
    },
    {
        "name": "體育賽事",
        "query": "體育 OR 運動 OR NBA OR MLB",
    },
    {
        "name": "台灣焦點",
        "query": "台灣",
    }
]

def fetch_news(query, limit=3):
    """Fetches news from Google News RSS."""
    # Use quote_plus to ensure spaces are handled correctly for URLs
    from urllib.parse import quote_plus
    encoded_query = quote_plus(query)
    url = RSS_BASE_URL.format(query=encoded_query)
    feed = feedparser.parse(url)
    
    news_items = []
    for entry in feed.entries[:limit]:
        published_parsed = entry.get("published_parsed")
        date_str = ""
        if published_parsed:
            date_str = datetime(*published_parsed[:6]).strftime("%m/%d %H:%M")
            
        news_items.append({
            "title": entry.title,
            "link": entry.link,
            "date": date_str,
            "source": entry.source.title if hasattr(entry, "source") else ""
        })
    return news_items

    return news_items

def deduplicate_news(items, threshold=0.8):
    unique_items = []
    seen_titles = []
    
    for item in items:
        is_duplicate = False
        for seen in seen_titles:
            # Check similarity
            ratio = difflib.SequenceMatcher(None, item['title'], seen).ratio()
            if ratio > threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_items.append(item)
            seen_titles.append(item['title'])
            
    return unique_items

class LineBotNotifier:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_news_report(self, all_news):
        if not self.access_token or not self.user_id:
            print("LINE Messaging API credentials not set.")
            return

        bubbles = []
        
        from urllib.parse import quote_plus

        for cat_data in CATEGORIES:
            category = cat_data["name"]
            query = cat_data["query"]
            items = all_news.get(category, [])
            
            # Deduplicate news items for the current category
            items = deduplicate_news(items)
            
            if not items:
                continue
                
            # Create content rows for each news item
            content_contents = []
            for item in items:
                content_contents.append({
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "action": {"type": "uri", "uri": item['link']},
                    "contents": [
                        {
                            "type": "text",
                            "text": item['title'],
                            "size": "sm",
                            "color": "#111111",
                            "wrap": True,
                            "maxLines": 3,
                            "weight": "bold"
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": item['source'],
                                    "size": "xs",
                                    "color": "#888888",
                                    "flex": 0
                                },
                                {
                                    "type": "text",
                                    "text": item['date'],
                                    "size": "xs",
                                    "color": "#aaaaaa",
                                    "align": "end"
                                }
                            ]
                        }
                    ]
                })
                # Add separator
                content_contents.append({"type": "separator", "margin": "sm"})

            # Remove last separator
            if content_contents:
                content_contents.pop()
            
            # Category Color Coding
            header_color = "#00B900" # Default Green
            if "AI" in category: header_color = "#00B900"
            elif "板金" in category or "機械" in category: header_color = "#1E90FF" # Blue
            elif "半導體" in category: header_color = "#8A2BE2" # Purple
            elif "電動車" in category: header_color = "#FF4500" # OrangeRed
            elif "體育" in category: header_color = "#FFD700" # Gold
            elif "台灣" in category: header_color = "#FF8C00" # DarkOrange

            # Search URL for "View More"
            search_url = f"https://news.google.com/search?q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

            bubble = {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": header_color,
                    "contents": [
                        {
                            "type": "text",
                            "text": category,
                            "weight": "bold",
                            "color": "#FFFFFF",
                            "size": "lg"
                        }
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": content_contents
                },
                "footer": {
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
                                "label": "查看更多相關新聞 >",
                                "uri": search_url
                            }
                        }
                    ],
                    "flex": 0
                }
            }
            bubbles.append(bubble)

        # Create Carousel wrapper
        flex_message = {
            "type": "carousel",
            "contents": bubbles
        }

        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "今日產業與台灣新聞摘要",
                    "contents": flex_message
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = requests.post(self.api_url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                print("News report sent successfully!")
            else:
                print(f"Failed to send news report: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending news report: {e}")

def main():
    print("Fetching news...")
    all_news = {}
    
    for cat in CATEGORIES:
        print(f"Searching for {cat['name']}...")
        # Default limit 3
        items = fetch_news(cat['query'], 3)
        all_news[cat['name']] = items
        print(f"Found {len(items)} items.")

    # Notify
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if token and user_id:
        print("Sending LINE notification...")
        notifier = LineBotNotifier(token, user_id)
        notifier.send_news_report(all_news)
    else:
        print("LINE credentials not found. Skipping notification.")

if __name__ == "__main__":
    main()
