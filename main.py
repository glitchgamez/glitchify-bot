import os
import json
import random
import requests
from flask import Flask, request
from datetime import datetime
from urllib.parse import quote_plus

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_URL = "https://glitchify.space/search-index.json"

# Load JSON data from Glitchify
def load_games():
    return requests.get(DATA_URL).json()

# Format a game object
def format_game(game):
    page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
    img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
    return {
        "text": f"*{game['title']}*\n🏷️ `{', '.join(game['tags'])}`\n🕒 `{game['modified']}`",
        "url": page_url,
        "thumb": img_url
    }

# Send a single game
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

# Send top 3 results and "More" button
def send_games(chat_id, games, more=False, query=None):
    for game in games[:3]:
        send_game(chat_id, game)

    if more and len(games) > 3:
        search_url = f"https://glitchify.space/search-results.html?q={quote_plus(query)}"
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"🔎 Found {len(games)} results. Showing top 3.",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": f"🔍 View All {len(games)} Results", "url": search_url}
                ]]
            }
        })

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return "OK"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()
    games = load_games()

    if text.lower().startswith("/start"):
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Welcome to *Glitchify Bot*!\n\nUse the buttons below or type /info for help.",
            "parse_mode": "Markdown",
            "reply_markup": {
                "keyboard": [[
                    {"text": "/search doom"},
                    {"text": "/random"},
                    {"text": "/latest"},
                    {"text": "/info"}
                ]],
                "resize_keyboard": True
            }
        })

    elif text.lower().startswith("/info"):
        info_text = (
            "🕹️ *Glitchify Bot Commands:*\n\n"
            "/search `<query>` – Find games by title\n"
            "/random – Get a surprise game\n"
            "/latest – Show the newest uploads\n"
            "/info – Show this help message"
        )
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": info_text,
            "parse_mode": "Markdown",
            "reply_markup": {
                "keyboard": [[
                    {"text": "/search doom"},
                    {"text": "/random"},
                    {"text": "/latest"},
                    {"text": "/info"}
                ]],
                "resize_keyboard": True
            }
        })

    elif text.lower().startswith("/random"):
        send_game(chat_id, random.choice(games))

    elif text.lower().startswith("/latest"):
        sorted_games = sorted(games, key=lambda g: g["modified"], reverse=True)
        send_games(chat_id, sorted_games[:3])

    elif text.lower().startswith("/search"):
        query = text[7:].strip()
        if not query:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❗ Please enter a search term. Example: /search doom"
            })
            return "OK"
        results = [g for g in games if query.lower() in g["title"].lower()]
        if results:
            send_games(chat_id, results, more=True, query=query)
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ No games found matching your search."
            })

    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "❓ Unknown command. Try:\n/search <term>\n/random\n/latest\n/info"
        })

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
