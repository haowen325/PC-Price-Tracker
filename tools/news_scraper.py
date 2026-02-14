
import feedparser
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
        "limit": 3
    },
    {
        "name": "機械板金",
        "query": "機械板金 OR 鈑金 OR 工具機 OR 雷射切割",
        "limit": 3
    },
    {
        "name": "台灣焦點",
        "query": "台灣",
        "limit": 3
    }
]

def fetch_news(query, limit=3):
    """Fetches news from Google News RSS."""
    encoded_query = quote(query)
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
        
        for category, items in all_news.items():
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

            bubble = {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#00B900" if category == "AI 科技" else ("#1E90FF" if category == "機械板金" else "#FF8C00"),
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
        items = fetch_news(cat['query'], cat['limit'])
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
