import os
import json
import random
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Telegram ID of admin (as a string)
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_URL = "https://glitchify.space/search-index.json"

# Global variable to store game data
_games_data = []

# Load JSON data from Glitchify
def load_games():
    """
    Loads game data from the specified DATA_URL and updates the global _games_data.
    Includes basic error handling for network requests.
    Returns True on success, False on failure.
    """
    global _games_data # Declare intent to modify the global variable
    try:
        response = requests.get(DATA_URL)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        _games_data = response.json()
        print(f"Successfully loaded {len(_games_data)} games.")
        return True # Indicate success
    except requests.exceptions.RequestException as e:
        print(f"Error loading games data from {DATA_URL}: {e}")
        _games_data = [] # Clear data on failure
        return False # Indicate failure

# Initial load of games when the bot starts
initial_load_success = load_games()
if not initial_load_success:
    print("Initial game data load failed. Bot may not function correctly for game-related commands.")

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

# In-memory state tracking for requests
# Example: {chat_id: {"flow": "game_request", "step": "title", "title": "Game Title"}}
# Or: {chat_id: {"flow": "feedback", "step": "type", "type": "Bug Report"}}
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

        # Handle game details callback
        if callback_data.startswith("details:"):
            game_url_path = callback_data[len("details:"):]
            found_game = next((g for g in _games_data if g["url"] == game_url_path), None)

            if found_game:
                detailed_text = format_game_details(found_game)
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": detailed_text,
                    "parse_mode": "Markdown",
                    "reply_to_message_id": message_id
                })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Game details not found. The game might have been removed or the link is old.",
                    "reply_to_message_id": message_id
                })
        # Handle feedback type callback
        elif callback_data.startswith("feedback_type:"):
            feedback_type = callback_data[len("feedback_type:"):]
            user_request_states[chat_id] = {"flow": "feedback", "step": "message", "type": feedback_type}
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"Got it! You've chosen '{feedback_type}'.\n\nPlease send me your detailed feedback message now:"
            })
        return "OK"

    # --- Handle Regular Messages ---
    if "message" not in data:
        return "OK"

    chat_id = data["message"]["chat"]["id"]
    user_msg = data["message"].get("text", "").strip()
    lower_msg = user_msg.lower()

    # --- Admin Commands ---
    if ADMIN_ID and str(chat_id) == ADMIN_ID:
        if lower_msg == "/admin_status":
            status_text = "✅ Bot is running.\n"
            if _games_data:
                status_text += f"🎮 Game data loaded successfully. Total games: {len(_games_data)}"
            else:
                status_text += "❌ Game data not loaded. Check server logs."
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": status_text,
                "parse_mode": "Markdown"
            })
            return "OK"
        elif lower_msg == "/reload_data":
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "🔄 Attempting to reload game data..."
            })
            success = load_games()
            if success:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "✅ Game data reloaded successfully!"
                })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Failed to reload game data. Check server logs."
                })
            return "OK"
    elif lower_msg.startswith("/admin_"):
        if not ADMIN_ID:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Admin commands are not configured. Please set the `ADMIN_ID` environment variable."
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "🚫 You are not authorized to use admin commands."
            })
        return "OK"

    # --- Handle Multi-step Flows (Game Request & Feedback) ---
    if chat_id in user_request_states:
        current_flow = user_request_states[chat_id]["flow"]
        current_step = user_request_states[chat_id]["step"]

        # Game Request Flow
        if current_flow == "game_request":
            if current_step == "title":
                user_request_states[chat_id]["title"] = user_msg
                user_request_states[chat_id]["step"] = "platform"
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🕹️ Enter the platform (e.g., PC, PS4, PS3):"
                })
            elif current_step == "platform":
                title = user_request_states[chat_id]["title"]
                platform = user_msg
                del user_request_states[chat_id] # Clear state after completion
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
            return "OK" # Important: return OK after handling flow step

        # Feedback Flow
        elif current_flow == "feedback":
            if current_step == "message":
                feedback_type = user_request_states[chat_id]["type"]
                feedback_message = user_msg
                del user_request_states[chat_id] # Clear state after completion

                admin_feedback_msg = (
                    f"📧 *New Feedback Received:*\n\n"
                    f"📝 *Type:* {feedback_type}\n"
                    f"💬 *Message:*\n{feedback_message}\n\n"
                    f"👤 From user: `{chat_id}`"
                )
                if ADMIN_ID: # Only send to admin if ADMIN_ID is configured
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": ADMIN_ID,
                        "text": admin_feedback_msg,
                        "parse_mode": "Markdown"
                    })
                else:
                    print(f"Admin ID not set, feedback not sent to admin: {admin_feedback_msg}")

                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "✅ Thank you for your feedback! It has been sent."
                })
            return "OK" # Important: return OK after handling flow step

    # --- Handle Regular Commands and Natural Language Search ---
    if lower_msg.startswith("/start"):
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": (
                "🎮 Welcome to Glitchify Bot!\n\n"
                "I can help you find games, discover new ones, or even request a game!\n"
                "Just type what you're looking for, or use the buttons below!"
            ),
            "parse_mode": "Markdown",
            "reply_markup": {
                "keyboard": [
                    [{"text": "🎲 Random Game"}, {"text": "✨ Latest Games"}],
                    [{"text": "📝 Request a Game"}, {"text": "💬 Send Feedback"}], # Added Feedback button
                    [{"text": "❓ Help"}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": False
            }
        })

    elif lower_msg.startswith("/help") or lower_msg == "❓ help":
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": (
                "📚 *Glitchify Bot Help Guide*\n\n"
                "Here's how you can use me:\n\n"
                "🔍 *Search for Games:*\n"
                "   Just type the name of a game (e.g., `Mario`, `Fortnite`) and I'll search for it!\n\n"
                "🎲 *Random Game:*\n"
                "   Tap the `🎲 Random Game` button or type `/random` to get a surprise game suggestion.\n\n"
                "✨ *Latest Games:*\n"
                "   Tap the `✨ Latest Games` button or type `/latest` to see the most recently added games.\n\n"
                "📝 *Request a Game:*\n"
                "   Tap the `📝 Request a Game` button or type `/request` to tell me about a game you'd like to see added.\n\n"
                "💬 *Send Feedback:*\n"
                "   Tap the `💬 Send Feedback` button or type `/feedback` to send me a bug report, suggestion, or general feedback.\n\n"
                "🔗 *View Details:*\n"
                "   After I send a game, tap the `✨ Show More Details` button to get more info about it.\n\n"
                "Got it? Let's find some games! 🎮"
            ),
            "parse_mode": "Markdown"
        })

    elif lower_msg.startswith("/random") or lower_msg == "🎲 random game":
        if _games_data:
            send_game(chat_id, random.choice(_games_data))
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    elif lower_msg.startswith("/latest") or lower_msg == "✨ latest games":
        if _games_data:
            sorted_games = sorted(_games_data, key=lambda g: g["modified"], reverse=True)
            send_games(chat_id, sorted_games[:3])
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    elif lower_msg.startswith("/request") or lower_msg == "📝 request a game":
        user_request_states[chat_id] = {"flow": "game_request", "step": "title"}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Enter the title of the game you want to request:"
        })

    elif lower_msg.startswith("/feedback") or lower_msg == "💬 send feedback":
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "What kind of feedback do you have?",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🐛 Bug Report", "callback_data": "feedback_type:Bug Report"}],
                    [{"text": "💡 Suggestion", "callback_data": "feedback_type:Suggestion"}],
                    [{"text": "💬 General Feedback", "callback_data": "feedback_type:General Feedback"}]
                ]
            }
        })

    # Natural Language Search (Fallback if no other command matches)
    else:
        query = user_msg
        if _games_data:
            results = [g for g in _games_data if query.lower() in g["title"].lower()]
            if results:
                send_games(chat_id, results, query=query)
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": f"❌ Sorry, I couldn't find any games matching '{query}'. Try a different term!"
                })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })

    return "OK"

# Flask entrypoint (unchanged)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))