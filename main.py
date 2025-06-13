import os
import json
import random
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Telegram ID of admin
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

# Send a game as photo
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

# Send multiple games
def send_games(chat_id, games, query=None):
    for game in games[:3]:
        send_game(chat_id, game)
    if len(games) > 3 and query:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"🔎 Found {len(games)} results for: *{query}*",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "🔍 View More Results", "url": f"https://glitchify.space/search-results.html?q={query.replace(' ', '%20')}"}
                ]]
            }
        })

# In-memory state tracking for requests
user_request_states = {}

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return "OK"

    chat_id = data["message"]["chat"]["id"]
    user_msg = data["message"].get("text", "").strip()
    lower_msg = user_msg.lower()
    games = load_games()

    # Handle game request flow
    if chat_id in user_request_states:
        step = user_request_states[chat_id]["step"]
        if step == "title":
            user_request_states[chat_id]["title"] = user_msg
            user_request_states[chat_id]["step"] = "platform"
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "🕹️ Enter the platform (e.g., PC, PS4, PS3):"
            })
        elif step == "platform":
            title = user_request_states[chat_id]["title"]
            platform = user_msg
            del user_request_states[chat_id]
            # Send to admin
            msg = f"📥 *New Game Request:*\n\n🎮 *Title:* {title}\n🕹️ *Platform:* {platform}\n👤 From user: `{chat_id}`"
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": ADMIN_ID,
                "text": msg,
                "parse_mode": "Markdown"
            })
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "✅ Your game request has been sent!"
            })
        return "OK"

    # Start command
    if lower_msg.startswith("/start"):
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": (
                "🎮 Welcome to Glitchify Bot!\n\n"
                "Use the following commands:\n"
                "`/search <term>` - Find a game\n"
                "`/random` - Surprise game\n"
                "`/latest` - Recently added games\n"
                "`/request` - Submit a game request"
            ),
            "parse_mode": "Markdown"
        })

    # Random game
    elif lower_msg.startswith("/random"):
        send_game(chat_id, random.choice(games))

    # Latest 3 games
    elif lower_msg.startswith("/latest"):
        sorted_games = sorted(games, key=lambda g: g["modified"], reverse=True)
        send_games(chat_id, sorted_games[:3])

    # Search command
    elif lower_msg.startswith("/search"):
        query = user_msg[7:].strip()
        results = [g for g in games if query.lower() in g["title"].lower()]
        if results:
            send_games(chat_id, results, query=query)
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ No games found matching your search."
            })

    # Request command
    elif lower_msg.startswith("/request"):
        user_request_states[chat_id] = {"step": "title"}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Enter the title of the game you want to request:"
        })

    # Unknown command
    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "❓ Unknown command. Try:\n/search <term>\n/random\n/latest\n/request"
        })

    return "OK"

# Flask entrypoint
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
