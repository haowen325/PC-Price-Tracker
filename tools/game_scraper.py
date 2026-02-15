
import requests
import json
import os
from datetime import datetime
from urllib.parse import quote

def fetch_epic_free_games():
    """Fetches current free games from Epic Games Store."""
    url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
    params = {"locale": "zh-Hant", "country": "TW", "allowCountries": "TW"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games = []
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        
        for item in elements:
            # Check for promotions
            promotions = item.get("promotions")
            if not promotions:
                continue
                
            promotional_offers = promotions.get("promotionalOffers")
            if not promotional_offers:
                continue
            
            # Check active offers
            offers = promotional_offers[0].get("promotionalOffers", [])
            for offer in offers:
                start_date_str = offer.get("startDate")
                end_date_str = offer.get("endDate")
                
                # Check directly if it's 0 cost now (free)
                price_info = item.get("price", {}).get("totalPrice", {})
                discount_price = price_info.get("discountPrice", -1)
                
                # Sometimes legacy games have different structure, 
                # but standard freebies usually have discountPrice == 0
                if discount_price == 0:
                    # Get image
                    image_url = ""
                    for img in item.get("keyImages", []):
                        if img.get("type") == "Thumbnail" or img.get("type") == "OfferImageWide":
                            image_url = img.get("url")
                            break
                    
                    # Convert dates for display
                    try:
                        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        end_str = end_date.strftime("%m/%d %H:%M")
                    except:
                        end_str = end_date_str

                    games.append({
                        "platform": "Epic",
                        "title": item.get("title"),
                        "original_price": price_info.get("originalPrice", 0),
                        "price": 0,
                        "discount": "-100%",
                        "image": image_url,
                        "link": f"https://store.epicgames.com/zh-Hant/p/{item.get('productSlug', '')}",
                        "desc": f"免費領取至 {end_str}"
                    })
                    break # Found the active free offer for this item
        return games
    except Exception as e:
        print(f"Error fetching Epic games: {e}")
        return []

def fetch_steam_specials():
    """Fetches top specials from Steam."""
    url = "https://store.steampowered.com/api/featuredcategories"
    params = {"cc": "TW", "l": "tchinese"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games = []
        # Find 'specials' category
        specials = data.get("specials", {}).get("items", [])
        
        # Top 3 specials
        for item in specials[:3]:
            original_price = item.get("original_price", 0) / 100 # Steam API is in cents
            final_price = item.get("final_price", 0) / 100
            discount = item.get("discount_percent", 0)
            
            games.append({
                "platform": "Steam",
                "title": item.get("name"),
                "original_price": int(original_price),
                "price": int(final_price),
                "discount": f"-{discount}%",
                "image": item.get("large_capsule_image"),
                "link": f"https://store.steampowered.com/app/{item.get('id')}/",
                "desc": "特價中"
            })
            
        return games
    except Exception as e:
        print(f"Error fetching Steam games: {e}")
        return []

class LineBotNotifier:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_game_deals(self, games):
        if not self.access_token or not self.user_id:
            print("LINE Messaging API credentials not set.")
            return
        
        if not games:
            print("No games to send.")
            return

        bubbles = []
        for game in games:
            # Color coding
            color = "#111111"
            if game['platform'] == 'Epic':
                header_bg = "#333333" # Dark Gray/Black for Epic
                platform_color = "#FFFFFF"
                pass
            else:
                header_bg = "#1b2838" # Steam Blue
                platform_color = "#66c0f4"

            bubble = {
                "type": "bubble",
                "hero": {
                    "type": "image",
                    "url": game['image'] if game['image'] else "https://via.placeholder.com/300x150?text=No+Image",
                    "size": "full",
                    "aspectRatio": "20:13",
                    "aspectMode": "cover",
                    "action": {"type": "uri", "uri": game['link']}
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": game['title'],
                            "weight": "bold",
                            "size": "md", 
                            "wrap": True
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "margin": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": game['platform'],
                                    "weight": "bold",
                                    "size": "xs",
                                    "color": "#999999",
                                    "flex": 0,
                                    "margin": "sm"
                                },
                                {
                                    "type": "text",
                                    "text": game['discount'],
                                    "weight": "bold",
                                    "size": "sm",
                                    "color": "#ff334b", # Red for discount
                                    "margin": "md",
                                    "flex": 0
                                },
                                {
                                    "type": "text",
                                    "text": f"NT${game['original_price']}",
                                    "decoration": "line-through",
                                    "color": "#aaaaaa",
                                    "size": "xs",
                                    "align": "end",
                                    "margin": "md"
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "NT$" + str(game['price']) if game['price'] > 0 else "FREE",
                                    "weight": "bold",
                                    "size": "xl",
                                    "color": "#111111" if game['price'] > 0 else "#e03e3e" # Red if free or paid.. wait, make FREE red? Yes.
                                }
                            ]
                        },
                        {
                            "type": "text",
                            "text": game['desc'],
                            "size": "xs",
                            "color": "#aaaaaa",
                            "wrap": True,
                            "margin": "sm"
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "color": header_bg,
                            "action": {
                                "type": "uri",
                                "label": "立即查看",
                                "uri": game['link']
                            }
                        }
                    ],
                    "flex": 0
                }
            }
            bubbles.append(bubble)

        # Flex Message wrapper
        flex_message = {
            "type": "carousel",
            "contents": bubbles
        }

        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "今日遊戲限免與特價快訊",
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
                print("Game deals sent successfully!")
            else:
                print(f"Failed to send game deals: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending game deals: {e}")

def main():
    print("Fetching Epic Games...")
    epic_games = fetch_epic_free_games()
    print(f"Found {len(epic_games)} Epic free games.")
    
    print("Fetching Steam Specials...")
    steam_games = fetch_steam_specials()
    print(f"Found {len(steam_games)} Steam specials.")
    
    all_games = epic_games + steam_games
    
    if not all_games:
        print("No interesting games found today.")
        return

    # Notify
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if token and user_id:
        print("Sending LINE notification...")
        notifier = LineBotNotifier(token, user_id)
        notifier.send_game_deals(all_games)
    else:
        print("LINE credentials not found. Skipping notification.")

if __name__ == "__main__":
    main()
