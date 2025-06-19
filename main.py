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
# PREFERENCES_FILE = "user_preferences.json" # Removed: File to store user preferences

# Global variables
_games_data = []
# _user_preferences = {} # Removed: Stores user preferences

# --- Configuration ---
GAMES_PER_PAGE = 3 # Define how many games to show per page for search results
# PLATFORMS = ["PC", "PS4", "PS3", "Xbox One", "Xbox 360", "Nintendo Switch", "Mobile", "Web"] # Removed: Customize your platforms

# --- Data Loading Functions ---
def load_games():
    """
    Loads game data from the specified DATA_URL and updates the global _games_data.
    Returns True on success, False on failure.
    """
    global _games_data
    try:
        response = requests.get(DATA_URL)
        response.raise_for_status()
        _games_data = response.json()
        print(f"Successfully loaded {len(_games_data)} games.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error loading games data from {DATA_URL}: {e}")
        _games_data = []
        return False

# Removed: load_user_preferences()
# Removed: save_user_preferences()

# Initial loads when the bot starts
initial_load_success = load_games()
if not initial_load_success:
    print("Initial game data load failed. Bot may not function correctly for game-related commands.")
# Removed: load_user_preferences()

# --- Formatting Functions ---
def format_game(game):
    page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
    img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
    return {
        "text": f"*{game['title']}*\n🏷️ `{', '.join(game['tags'])}`\n🕒 `{game['modified']}`",
        "url": page_url,
        "thumb": img_url
    }

def format_game_details(game):
    description = game.get('description', 'No description available.')
    genre = ', '.join(game.get('tags', []))
    release_date = game.get('release_date', 'N/A')

    return (
        f"*{game['title']}*\n\n"
        f"📝 *Description:*\n{description}\n\n"
        f"🏷️ *Tags/Genre:* `{genre}`\n"
        f"🕒 *Last Modified:* `{game['modified']}`\n"
        f"🗓️ *Release Date:* `{release_date}`"
    )

# --- Telegram API Interaction Functions ---
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

# In-memory state tracking for requests
user_request_states = {}

def get_main_reply_keyboard():
    """Returns the main reply keyboard markup."""
    return {
        "keyboard": [
            [{"text": "🎲 Random Game"}, {"text": "✨ Latest Games"}],
            [{"text": "📝 Request a Game"}, {"text": "💬 Send Feedback"}],
            [{"text": "❓ Help"}] # Removed Settings button
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_cancel_reply_keyboard():
    """Returns a reply keyboard with only a cancel button."""
    return {
        "keyboard": [
            [{"text": "❌ Cancel"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True # Disappear after use
    }

def send_search_page(chat_id, all_results, query, page):
    """
    Sends a page of search results, including pagination controls.
    Attempts to delete the previous pagination message.
    """
    total_games = len(all_results)
    total_pages = (total_games + GAMES_PER_PAGE - 1) // GAMES_PER_PAGE

    start_index = page * GAMES_PER_PAGE
    end_index = min(start_index + GAMES_PER_PAGE, total_games)
    current_page_games = all_results[start_index:end_index]

    if not current_page_games:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "No games found for this page."
        })
        return

    for game in current_page_games:
        send_game(chat_id, game)

    pagination_buttons_row = []
    if page > 0:
        pagination_buttons_row.append({"text": "⬅️ Previous", "callback_data": f"paginate:{page-1}"})
    
    pagination_buttons_row.append({"text": f"Page {page + 1}/{total_pages}", "callback_data": "ignore_page_info"})

    if page < total_pages - 1:
        pagination_buttons_row.append({"text": "Next ➡️", "callback_data": f"paginate:{page+1}"})

    more_results_button_row = []
    if total_games > 0:
        more_results_button_row.append({"text": "🔍 View All Results on Glitchify", "url": f"https://glitchify.space/search-results.html?q={query.replace(' ', '%20')}"})

    reply_markup = {}
    keyboard_rows = []
    if pagination_buttons_row:
        keyboard_rows.append(pagination_buttons_row)
    if more_results_button_row:
        keyboard_rows.append(more_results_button_row)
    
    if keyboard_rows:
        reply_markup = {"inline_keyboard": keyboard_rows}

    if chat_id in user_request_states and \
       user_request_states[chat_id].get("flow") == "search_pagination" and \
       user_request_states[chat_id].get("pagination_message_id"):
        prev_message_id = user_request_states[chat_id]["pagination_message_id"]
        print(f"Attempting to delete previous pagination message {prev_message_id} for chat {chat_id}")
        try:
            delete_response = requests.post(f"{BASE_URL}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": prev_message_id
            })
            print(f"Delete message response: {delete_response.status_code} - {delete_response.text}")
        except Exception as e:
            print(f"Error deleting previous pagination message for chat {chat_id}: {e}")

    if reply_markup:
        response = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"Showing results for '{query}' (Page {page + 1} of {total_pages}):",
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        })
        print(f"Send pagination message response: {response.status_code} - {response.text}")
        if response.status_code == 200:
            message_id = response.json().get("result", {}).get("message_id")
            if message_id:
                user_request_states[chat_id]["pagination_message_id"] = message_id
                print(f"Stored new pagination message ID: {message_id}")
            else:
                print(f"No message_id found in response for chat {chat_id}")
        else:
            print(f"Failed to send pagination message for chat {chat_id}: {response.text}")
    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"Here are the results for '{query}':"
        })

def handle_inline_query(inline_query_id, query_string):
    """
    Handles incoming inline queries and sends back search results.
    """
    results = []
    if _games_data:
        search_results = [g for g in _games_data if query_string.lower() in g["title"].lower()]

        for i, game in enumerate(search_results[:50]): # Telegram limits to 50 results
            formatted_game = format_game(game)
            
            inline_keyboard_buttons = [
                [{"text": "🔗 View on Glitchify", "url": formatted_game["url"]}],
                [{"text": "✨ Show More Details", "callback_data": f"details:{game['url']}"}]
            ]

            results.append({
                "type": "photo",
                "id": str(i) + "_" + game["url"],
                "photo_url": formatted_game["thumb"],
                "thumb_url": formatted_game["thumb"],
                "caption": formatted_game["text"],
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": inline_keyboard_buttons}
            })
    
    if not results:
        results.append({
            "type": "article",
            "id": "no_results",
            "title": "No Games Found 😔",
            "input_message_content": {
                "message_text": f"Sorry, I couldn't find any games matching '{query_string}'. Try a different term!",
                "parse_mode": "Markdown"
            },
            "description": "Try a different search term."
        })

    payload = {
        "inline_query_id": inline_query_id,
        "results": results,
        "cache_time": 0
    }
    requests.post(f"{BASE_URL}/answerInlineQuery", json=payload)


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    # --- Handle Inline Queries ---
    if "inline_query" in data:
        inline_query_id = data["inline_query"]["id"]
        query_string = data["inline_query"]["query"].strip()
        handle_inline_query(inline_query_id, query_string)
        return "OK"

    # --- Handle Callback Queries (for inline buttons) ---
    if "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        callback_data = query["data"]
        message_id = query["message"]["message_id"]

        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": query["id"]})

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
        elif callback_data.startswith("feedback_type:"):
            feedback_type = callback_data[len("feedback_type:"):]
            user_request_states[chat_id] = {"flow": "feedback", "step": "message", "type": feedback_type}
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"Got it! You've chosen '{feedback_type}'.\n\nPlease send me your detailed feedback message now:",
                "reply_markup": get_cancel_reply_keyboard()
            })
        elif callback_data.startswith("paginate:"):
            requested_page = int(callback_data.split(":")[1])
            
            if chat_id in user_request_states and user_request_states[chat_id].get("flow") == "search_pagination":
                stored_results = user_request_states[chat_id]["results"]
                stored_query = user_request_states[chat_id]["query"]
                
                total_pages = (len(stored_results) + GAMES_PER_PAGE - 1) // GAMES_PER_PAGE
                if 0 <= requested_page < total_pages:
                    send_search_page(chat_id, stored_results, stored_query, requested_page)
                else:
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "You've reached the end of the results."
                    })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "Sorry, I lost track of your search. Please try searching again."
                })
            return "OK"
        # Removed: elif callback_data.startswith("set_platform:"):
        elif callback_data == "cancel_feedback_flow" or callback_data == "cancel_settings_flow":
            if chat_id in user_request_states:
                del user_request_states[chat_id]
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🚫 Operation canceled. What else can I help you with?",
                    "reply_markup": get_main_reply_keyboard()
                })
            return "OK"
        return "OK"

    # --- Handle Regular Messages ---
    if "message" not in data:
        return "OK"

    chat_id = data["message"]["chat"]["id"]
    user_msg = data["message"].get("text", "").strip()
    lower_msg = user_msg.lower()
    str_chat_id = str(chat_id)

    # --- Admin Commands ---
    if ADMIN_ID and str_chat_id == ADMIN_ID:
        if lower_msg == "/admin_status":
            status_text = "✅ Bot is running.\n"
            if _games_data:
                status_text += f"🎮 Game data loaded successfully. Total games: {len(_games_data)}\n"
            else:
                status_text += "❌ Game data not loaded. Check server logs.\n"
            # Removed: status_text += f"👥 User preferences loaded: {len(_user_preferences)} users."
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

    # --- Handle Cancel Command (prioritized) ---
    if lower_msg == "/cancel" or lower_msg == "❌ cancel":
        if chat_id in user_request_states:
            del user_request_states[chat_id]
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "🚫 Operation canceled. What else can I help you with?",
                "reply_markup": get_main_reply_keyboard()
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "Nothing to cancel. You're not in an active operation.",
                "reply_markup": get_main_reply_keyboard()
            })
        return "OK"

    # --- Handle Multi-step Flows (Game Request & Feedback) ---
    if chat_id in user_request_states:
        current_flow = user_request_states[chat_id].get("flow")
        current_step = user_request_states[chat_id].get("step")

        if current_flow == "game_request":
            if current_step == "title":
                user_request_states[chat_id]["title"] = user_msg
                user_request_states[chat_id]["step"] = "platform"
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🕹️ Enter the platform (e.g., PC, PS4, PS3):",
                    "reply_markup": get_cancel_reply_keyboard()
                })
            elif current_step == "platform":
                title = user_request_states[chat_id]["title"]
                platform = user_msg
                del user_request_states[chat_id]
                msg = f"📥 *New Game Request:*\n\n🎮 *Title:* {title}\n🕹️ *Platform:* {platform}\n👤 From user: `{chat_id}`"
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": ADMIN_ID,
                    "text": msg,
                    "parse_mode": "Markdown"
                })
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "✅ Your game request has been sent!",
                    "reply_markup": get_main_reply_keyboard()
                })
            return "OK"

        elif current_flow == "feedback":
            if current_step == "message":
                feedback_type = user_request_states[chat_id]["type"]
                feedback_message = user_msg
                del user_request_states[chat_id]

                admin_feedback_msg = (
                    f"📧 *New Feedback Received:*\n\n"
                    f"📝 *Type:* {feedback_type}\n"
                    f"💬 *Message:*\n{feedback_message}\n\n"
                    f"👤 From user: `{chat_id}`"
                )
                if ADMIN_ID:
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": ADMIN_ID,
                        "text": admin_feedback_msg,
                        "parse_mode": "Markdown"
                    })
                else:
                    print(f"Admin ID not set, feedback not sent to admin: {admin_feedback_msg}")

                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "✅ Thank you for your feedback! It has been sent.",
                    "reply_markup": get_main_reply_keyboard()
                })
            return "OK"
        
        # Removed: if current_flow == "set_platform":
        # This block is no longer needed as platform selection is removed.
        # If a user sends a message while in a flow, but it's not the expected step,
        # we should probably ignore it or prompt them to complete the current flow.
        # For now, we'll just return OK if it's an active flow.
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "Please complete the current operation or type '❌ Cancel' to exit."
        })
        return "OK"


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
            "reply_markup": get_main_reply_keyboard()
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
                # Removed: "⚙️ *Settings:*\n"
                # Removed: "   Tap the `⚙️ Settings` button or type `/settings` to set your preferred gaming platform.\n\n"
                "🔗 *View Details:*\n"
                "   After I send a game, tap the `✨ Show More Details` button to get more info about it.\n\n"
                "❌ *Cancel:*\n"
                "   Type `/cancel` or tap the `❌ Cancel` button to stop any ongoing operation (like requesting a game or sending feedback).\n\n"
                "Got it? Let's find some games! 🎮"
            ),
            "parse_mode": "Markdown"
        })

    elif lower_msg.startswith("/random") or lower_msg == "🎲 random game":
        if not _games_data:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })
            return "OK"

        # Removed: preferred_platform logic
        send_game(chat_id, random.choice(_games_data))

    elif lower_msg.startswith("/latest") or lower_msg == "✨ latest games":
        if not _games_data:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })
            return "OK"

        sorted_games = sorted(_games_data, key=lambda g: g["modified"], reverse=True)
        for game in sorted_games[:3]:
            send_game(chat_id, game)
        if len(sorted_games) > 3:
                requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"🔎 Found {len(sorted_games)} latest games. View more on Glitchify: https://glitchify.space/search-results.html?q=latest",
                "parse_mode": "Markdown"
            })

    elif lower_msg.startswith("/request") or lower_msg == "📝 request a game":
        user_request_states[chat_id] = {"flow": "game_request", "step": "title"}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Enter the title of the game you want to request:",
            "reply_markup": get_cancel_reply_keyboard()
        })

    elif lower_msg.startswith("/feedback") or lower_msg == "💬 send feedback":
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "What kind of feedback do you have?",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🐛 Bug Report", "callback_data": "feedback_type:Bug Report"}],
                    [{"text": "💡 Suggestion", "callback_data": "feedback_type:Suggestion"}],
                    [{"text": "💬 General Feedback", "callback_data": "feedback_type:General Feedback"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_feedback_flow"}]
                ]
            }
        })
    
    # Removed: elif lower_msg.startswith("/settings") or lower_msg == "⚙️ settings":
    # This command and its logic are entirely removed.

    # Natural Language Search (Fallback if no other command matches)
    else:
        query = user_msg
        if not _games_data:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })
            return "OK"

        # Removed: preferred_platform logic
        initial_results = [g for g in _games_data if query.lower() in g["title"].lower()]
        final_results = initial_results # No platform filtering

        if final_results:
            user_request_states[chat_id] = {
                "flow": "search_pagination",
                "query": query,
                "results": final_results,
                "pagination_message_id": None
            }
            send_search_page(chat_id, final_results, query, page=0)
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"❌ Sorry, I couldn't find any games matching '{query}'. Try a different term!"
            })

    return "OK"

# Flask entrypoint (unchanged)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))