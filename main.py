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
RESULTS_PER_PAGE = 3

# Load JSON data from Glitchify
def load_games():
    return requests.get(DATA_URL).json()

# Format a game
def format_game(game):
    page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
    img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
    return {
        "text": f"*{game['title']}*\n🏷️ `{', '.join(game['tags'])}`\n🕒 `{game['modified']}`",
        "url": page_url,
        "thumb": img_url
    }

# Send one game
def send_game(chat_id, game):
    msg = format_game(game)
    requests.post(f"{BASE_URL}/sendPhoto", json={
        "chat_id": chat_id,
        "photo": msg["thumb"],
        "caption": msg["text"],
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🔗 View on Glitchify", "url": msg["url"]}
            ]]
        }
    })

# Send multiple games with optional pagination
def send_games(chat_id, results, page, query):
    start = (page - 1) * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    for game in results[start:end]:
        send_game(chat_id, game)

    buttons = []
    if end < len(results):
        buttons.append({"text": "▶️ Next Page", "callback_data": f"page:{query}:{page+1}"})
    if start > 0:
        buttons.append({"text": "◀️ Prev Page", "callback_data": f"page:{query}:{page-1}"})

    if buttons:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"📄 Page {page} of {((len(results)-1)//RESULTS_PER_PAGE)+1}",
            "reply_markup": {"inline_keyboard": [buttons]}
        })

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    chat_id = None
    text = None

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").strip()

    elif "callback_query" in data:
        query_data = data["callback_query"]["data"]
        chat_id = data["callback_query"]["message"]["chat"]["id"]
        if query_data.startswith("page:"):
            _, query, page = query_data.split(":")
            page = int(page)
            games = load_games()
            results = [g for g in games if query.lower() in g["title"].lower() or any(query.lower() in t.lower() for t in g["tags"])]
            send_games(chat_id, results, page, query)
            return "OK"

    if not text or not chat_id:
        return "OK"

    games = load_games()

    if text.lower().startswith("/start"):
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Welcome to *Glitchify Bot*!\nType /info to see all commands.",
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
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": (
                "🕹️ *Glitchify Bot Commands:*\n\n"
                "/search `<query>` – Fuzzy search games (title or tags)\n"
                "/random – Get a surprise game\n"
                "/latest – Show newest games\n"
                "/info – Show this help message\n\n"
                "_Use next/prev page buttons to navigate results._"
            ),
            "parse_mode": "Markdown"
        })

    elif text.lower().startswith("/random"):
        send_game(chat_id, random.choice(games))

    elif text.lower().startswith("/latest"):
        sorted_games = sorted(games, key=lambda g: g["modified"], reverse=True)
        send_games(chat_id, sorted_games, page=1, query="latest")

    elif text.lower().startswith("/search"):
        parts = text[7:].strip().split("page=")
        query = parts[0].strip()
        page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        if not query:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❗ Please enter a search term. Example: /search doom"
            })
            return "OK"

        results = [g for g in games if query.lower() in g["title"].lower() or any(query.lower() in t.lower() for t in g["tags"])]
        if results:
            send_games(chat_id, results, page=page, query=query)
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ No matching games found."
            })

    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "❓ Unknown command. Type /info to see available commands."
        })

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
