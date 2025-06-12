import os
import json
import logging
import difflib
import datetime
import requests
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # your Telegram user ID

TG_API = f"https://api.telegram.org/bot{TOKEN}"

# Load JSON once (could be dynamic)
INDEX_URL = "https://glitchify.space/search-index.json"
GAME_INDEX = requests.get(INDEX_URL).json()

# In-memory analytics
analytics = {}

def send_message(chat_id, text, buttons=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if buttons:
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    requests.post(f"{TG_API}/sendMessage", json=data)

def search_games(query):
    results = []
    titles = [game["title"] for game in GAME_INDEX]
    corrected = difflib.get_close_matches(query.lower(), [t.lower() for t in titles], n=1, cutoff=0.6)
    if corrected and corrected[0] != query.lower():
        correction = next(t for t in titles if t.lower() == corrected[0])
    else:
        correction = None

    for game in GAME_INDEX:
        if query.lower() in game["title"].lower() or any(query.lower() in tag.lower() for tag in game.get("tags", [])):
            results.append(game)
    return results, correction

def log_analytics(title):
    if title in analytics:
        analytics[title] += 1
    else:
        analytics[title] = 1

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            send_message(chat_id, "🎮 Welcome to Glitchify Bot!\nUse /search <game>, /random, /latest, /info or /submit")

        elif text.startswith("/info"):
            send_message(chat_id, "📋 <b>Available Commands:</b>\n"
                                  "/search <name>\n"
                                  "/random\n"
                                  "/latest\n"
                                  "/submit <your game request>\n"
                                  "You’ll get titles, tags, and direct links!", buttons=[
                [{"text": "Search", "callback_data": "prompt_search"}],
                [{"text": "Submit Request", "callback_data": "prompt_submit"}]
            ])

        elif text.startswith("/search"):
            query = text[8:].strip()
            if not query:
                send_message(chat_id, "❌ Please enter a game name: /search <name>")
            else:
                results, correction = search_games(query)
                if correction:
                    send_message(chat_id, f"🔍 Did you mean: <b>{correction}</b>?\nShowing matches...")

                top_results = results[:5]
                for game in top_results:
                    thumb = f"https://glitchify.space/{os.path.dirname(game['url'])}/screenshot1.jpg"
                    buttons = [[
                        {"text": "🔗 View Game", "url": f"https://glitchify.space/{game['url']}"},
                        {"text": "📄 View All", "url": f"https://glitchify.space/search-results.html?q={query}"}
                    ]]
                    send_message(chat_id,
                        f"<b>{game['title']}</b>\n🕓 Last Modified: {game['modified']}\n🏷️ Tags: {', '.join(game.get('tags', []))}",
                        buttons)
                    log_analytics(game["title"])

                if not results:
                    send_message(chat_id, "😢 No matches found. Try something else.")

        elif text.startswith("/submit"):
            content = text[8:].strip()
            if not content:
                send_message(chat_id, "❌ Please enter your game request after /submit")
            else:
                user = msg["from"].get("username", "Unknown")
                notify = f"📥 <b>New Game Request</b>\nUser: @{user}\nRequest: {content}"
                requests.post(f"{TG_API}/sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": notify, "parse_mode": "HTML"})
                send_message(chat_id, "✅ Thanks! Your request was sent to the Glitchify team.")

        elif text.startswith("/random"):
            import random
            game = random.choice(GAME_INDEX)
            thumb = f"https://glitchify.space/{os.path.dirname(game['url'])}/screenshot1.jpg"
            buttons = [[
                {"text": "🔗 View Game", "url": f"https://glitchify.space/{game['url']}"},
                {"text": "📄 Search More", "url": "https://glitchify.space"}
            ]]
            send_message(chat_id,
                f"🎲 <b>Random Pick</b>: {game['title']}\n🕓 Modified: {game['modified']}\n🏷️ {', '.join(game.get('tags', []))}",
                buttons)
            log_analytics(game["title"])

        elif text.startswith("/latest"):
            sorted_games = sorted(GAME_INDEX, key=lambda x: x["modified"], reverse=True)[:5]
            for game in sorted_games:
                buttons = [[{"text": "🔗 View Game", "url": f"https://glitchify.space/{game['url']}"}]]
                send_message(chat_id, f"🆕 <b>{game['title']}</b>\n🕓 Modified: {game['modified']}", buttons)
                log_analytics(game["title"])

    return {"ok": True}

@app.route("/")
def home():
    return "Glitchify Telegram Bot Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
