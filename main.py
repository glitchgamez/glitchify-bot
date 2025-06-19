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
    """
    Loads game data from the specified DATA_URL.
    Includes basic error handling for network requests.
    """
    try:
        response = requests.get(DATA_URL)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error loading games data from {DATA_URL}: {e}")
        return [] # Return an empty list if data cannot be loaded

# Format game info for initial display (brief)
def format_game(game):
    page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
    img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
    return {
        "text": f"*{game['title']}*\n🏷️ `{', '.join(game['tags'])}`\n🕒 `{game['modified']}`",
        "url": page_url,
        "thumb": img_url
    }

# Format game info for detailed display
def format_game_details(game):
    """
    Formats a detailed message for a game.
    Assumes 'description' and 'release_date' might be present in the game object.
    Adjust these keys based on your actual search-index.json structure.
    """
    description = game.get('description', 'No description available.')
    # Using 'tags' as a general genre/category for now.
    genre = ', '.join(game.get('tags', []))
    release_date = game.get('release_date', 'N/A')

    return (
        f"*{game['title']}*\n\n"
        f"📝 *Description:*\n{description}\n\n"
        f"🏷️ *Tags/Genre:* `{genre}`\n"
        f"🕒 *Last Modified:* `{game['modified']}`\n"
        f"🗓️ *Release Date:* `{release_date}`"
    )

# Send a game as photo with inline buttons for details and viewing
def send_game(chat_id, game):
    msg = format_game(game)
    # Callback data must be a string and less than 64 bytes.
    # Using the game's relative URL as a unique identifier.
    # If URLs are extremely long, a different strategy (e.g., a short ID) might be needed.
    callback_data_details = f"details:{game['url']}"

    inline_keyboard = [
        [{"text": "🔗 View on Glitchify", "url": msg["url"]}],
        [{"text": "✨ Show More Details", "callback_data": callback_data_details}]
    ]

    payload = {
        "chat_id": chat_id,
        "photo": msg["thumb"],
        "caption": msg["text"],
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": inline_keyboard
        }
    }
    requests.post(f"{BASE_URL}/sendPhoto", json=payload)

# Send multiple games (no change needed here, as send_game is updated)
def send_games(chat_id, games, query=None):
    for game in games[:3]: # Send up to 3 games
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

# In-memory state tracking for game requests (unchanged)
user_request_states = {}

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    # print(f"Received data: {json.dumps(data, indent=2)}") # Uncomment for debugging incoming data

    # --- Handle Callback Queries (for inline buttons) ---
    if "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        callback_data = query["data"]
        message_id = query["message"]["message_id"]

        # Acknowledge the callback query to remove the loading state from the button
        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": query["id"]})

        if callback_data.startswith("details:"):
            game_url_path = callback_data[len("details:"):]
            games = load_games() # Reload games to find the detailed info

            found_game = next((g for g in games if g["url"] == game_url_path), None)

            if found_game:
                detailed_text = format_game_details(found_game)
                # Send the detailed information as a new message, replying to the original
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": detailed_text,
                    "parse_mode": "Markdown",
                    "reply_to_message_id": message_id # Reply to the original message for context
                })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Game details not found. The game might have been removed or the link is old.",
                    "reply_to_message_id": message_id
                })
        return "OK" # Important: return OK after handling callback query

    # --- Handle Regular Messages ---
    if "message" not in data:
        return "OK" # Not a message or callback, ignore

    chat_id = data["message"]["chat"]["id"]
    user_msg = data["message"].get("text", "").strip()
    lower_msg = user_msg.lower()
    games = load_games() # Load games for message handling as well

    # Handle game request flow (unchanged)
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

    # Start command - NOW WITH REPLY KEYBOARD MARKUP!
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
            "parse_mode": "Markdown",
            "reply_markup": {
                "keyboard": [
                    [{"text": "/random"}, {"text": "/latest"}],
                    [{"text": "/request"}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": False # Set to True if you want it to disappear after one use
            }
        })

    # Random game
    elif lower_msg.startswith("/random"):
        if games: # Check if games data was loaded successfully
            send_game(chat_id, random.choice(games))
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    # Latest 3 games
    elif lower_msg.startswith("/latest"):
        if games: # Check if games data was loaded successfully
            sorted_games = sorted(games, key=lambda g: g["modified"], reverse=True)
            send_games(chat_id, sorted_games[:3])
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    # Search command
    elif lower_msg.startswith("/search"):
        query = user_msg[7:].strip()
        if games: # Check if games data was loaded successfully
            results = [g for g in games if query.lower() in g["title"].lower()]
            if results:
                send_games(chat_id, results, query=query)
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ No games found matching your search."
                })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    # Request command (unchanged)
    elif lower_msg.startswith("/request"):
        user_request_states[chat_id] = {"step": "title"}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Enter the title of the game you want to request:"
        })

    # Unknown command (unchanged)
    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "❓ Unknown command. Try:\n/search <term>\n/random\n/latest\n/request"
        })

    return "OK"

# Flask entrypoint (unchanged)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))