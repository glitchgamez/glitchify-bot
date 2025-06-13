import os
import json
import random
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # Default to 0 if not set
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_URL = "https://glitchify.space/search-index.json"

# Load JSON data from Glitchify
def load_games():
    return requests.get(DATA_URL).json()

# Format game info
def format_game(game):
    page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
    img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
    return {
        "text": f"*{game['title']}*\n🏷️ `{', '.join(game['tags'])}`\n🕒 `{game['modified']}`",
        "url": page_url,
        "thumb": img_url
    }

# Send single game
def send_game(chat_id, game):
    msg = format_game(game)
    payload = {
        "chat_id": chat_id,
        "photo": msg["thumb"],
        "caption": msg["text"],
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🔗 View on Glitchify", "url": msg["url"]}
            ]]
        }
    }
    requests.post(f"{BASE_URL}/sendPhoto", json=payload)

# Send multiple games + More link
def send_games(chat_id, games, more=False):
    for game in games[:3]:
        send_game(chat_id, game)
    if more and len(games) > 3:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"🔎 Found {len(games)} results. Showing top 3.",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "🔍 View All Results", "url": "https://glitchify.space"}
                ]]
            }
        })

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return "OK"
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    username = message["from"].get("username", "unknown")
    user_id = message["from"]["id"]

    games = load_games()

    if text.startswith("/start"):
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Welcome to Glitchify Bot!\n\nUse:\n/search <term>\n/random\n/latest\n/request <game name>"
        })

    elif text.startswith("/random"):
        send_game(chat_id, random.choice(games))

    elif text.startswith("/latest"):
        sorted_games = sorted(games, key=lambda g: g["modified"], reverse=True)
        send_games(chat_id, sorted_games[:3])

    elif text.startswith("/search"):
        query = text.replace("/search", "").strip().lower()
        results = [g for g in games if query in g["title"].lower()]
        if results:
            send_games(chat_id, results, more=True)
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ No games found matching your search."
            })

    elif text.startswith("/request"):
        game_title = text.replace("/request", "").strip()
        if not game_title:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "⚠️ Please provide a game title after /request."
            })
        else:
            # Acknowledge user
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"✅ Request for *{game_title}* received!",
                "parse_mode": "Markdown"
            })
            # Notify Admin
            if ADMIN_ID:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": ADMIN_ID,
                    "text": f"📬 *New Game Request*\n\n🎮 Title: *{game_title}*\n👤 User: @{username} (`{user_id}`)\n🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    "parse_mode": "Markdown"
                })

    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "❓ Unknown command. Try:\n/search <term>\n/random\n/latest\n/request <game name>"
        })

    return "OK"

# Flask start
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
