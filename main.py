import os
import json
import random
import requests
from flask import Flask, request
from collections import defaultdict # For easier counting

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Telegram ID of admin (as a string)
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_URL = "https://glitchify.space/search-index.json"
ANALYTICS_FILE = "analytics_data.json" # File to store analytics data

# Global variables
_games_data = []
_analytics_data = {} # Stores bot usage analytics

# --- Configuration ---
GAMES_PER_PAGE = 3 # Define how many games to show per page for search results

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

def load_analytics():
    """
    Loads analytics data from the JSON file.
    Initializes with default structure if file not found or corrupted.
    """
    global _analytics_data
    default_analytics = {
        "total_users": 0,
        "unique_users": [], # List of chat_ids
        "commands_used": defaultdict(int), # Stores command_name: count
        "game_details_views": defaultdict(int), # Stores game_url: count
        "game_shares": defaultdict(int), # Stores game_url: count
        "feedback_types": defaultdict(int), # Stores feedback_type: count
        "top_searches": defaultdict(int) # Stores query: count
    }
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Convert dicts back to defaultdicts for easier incrementing
                _analytics_data = {
                    "total_users": loaded_data.get("total_users", 0),
                    "unique_users": loaded_data.get("unique_users", []),
                    "commands_used": defaultdict(int, loaded_data.get("commands_used", {})),
                    "game_details_views": defaultdict(int, loaded_data.get("game_details_views", {})),
                    "game_shares": defaultdict(int, loaded_data.get("game_shares", {})),
                    "feedback_types": defaultdict(int, loaded_data.get("feedback_types", {})),
                    "top_searches": defaultdict(int, loaded_data.get("top_searches", {}))
                }
            print(f"Successfully loaded analytics data.")
        except json.JSONDecodeError as e:
            print(f"Error decoding analytics JSON: {e}. Starting with empty analytics.")
            _analytics_data = default_analytics
    else:
        print("Analytics file not found. Starting with empty analytics.")
        _analytics_data = default_analytics

def save_analytics():
    """
    Saves analytics data to the JSON file.
    """
    try:
        # Convert defaultdicts back to regular dicts for JSON serialization
        serializable_analytics = {
            "total_users": _analytics_data["total_users"],
            "unique_users": list(_analytics_data["unique_users"]), # Ensure it's a list
            "commands_used": dict(_analytics_data["commands_used"]),
            "game_details_views": dict(_analytics_data["game_details_views"]),
            "game_shares": dict(_analytics_data["game_shares"]),
            "feedback_types": dict(_analytics_data["feedback_types"]),
            "top_searches": dict(_analytics_data["top_searches"])
        }
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(serializable_analytics, f, indent=4)
        print("Analytics data saved.")
    except IOError as e:
        print(f"Error saving analytics data: {e}")

# --- Analytics Tracking Functions ---
def track_user(chat_id):
    str_chat_id = str(chat_id)
    if str_chat_id not in _analytics_data["unique_users"]:
        _analytics_data["unique_users"].append(str_chat_id)
        _analytics_data["total_users"] = len(_analytics_data["unique_users"])
        save_analytics()

def track_command(command_name):
    _analytics_data["commands_used"][command_name] += 1
    save_analytics()

def track_game_view(game_url):
    _analytics_data["game_details_views"][game_url] += 1
    save_analytics()

def track_game_share(game_url):
    _analytics_data["game_shares"][game_url] += 1
    save_analytics()

def track_feedback(feedback_type):
    _analytics_data["feedback_types"][feedback_type] += 1
    save_analytics()

def track_search(query):
    _analytics_data["top_searches"][query.lower()] += 1
    save_analytics()

# Initial loads when the bot starts
initial_load_success = load_games()
if not initial_load_success:
    print("Initial game data load failed. Bot may not function correctly for game-related commands.")
load_analytics() # Load analytics on startup

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
    callback_data_share = f"share_game:{game['url']}"

    inline_keyboard = [
        [{"text": "🔗 View on Glitchify", "url": msg["url"]}],
        [{"text": "✨ Show More Details", "callback_data": callback_data_details}],
        [{"text": "📤 Share Game", "callback_data": callback_data_share}]
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
            [{"text": "❓ Help"}]
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

def get_admin_inline_keyboard():
    """Returns an inline keyboard markup for admin commands."""
    return {
        "inline_keyboard": [
            [{"text": "📊 Analytics", "callback_data": "admin_cmd:analytics"}],
            [{"text": "🔄 Reload Data", "callback_data": "admin_cmd:reload_data"}],
            [{"text": "✅ Bot Status", "callback_data": "admin_cmd:status"}]
        ]
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
            track_game_view(game_url_path)
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
        elif callback_data.startswith("share_game:"):
            game_url_path = callback_data[len("share_game:"):]
            track_game_share(game_url_path)
            found_game = next((g for g in _games_data if g["url"] == game_url_path), None)

            if found_game:
                share_text = f"Check out this game: *{found_game['title']}*\n🔗 {format_game(found_game)['url']}"
                share_keyboard = {
                    "inline_keyboard": [
                        [{"text": "Share this game with a friend", "switch_inline_query": found_game['title']}]
                    ]
                }
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": share_text,
                    "parse_mode": "Markdown",
                    "reply_markup": share_keyboard
                })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Game not found for sharing. It might have been removed or the link is old.",
                    "reply_to_message_id": message_id
                })
            return "OK"
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
        elif callback_data == "cancel_feedback_flow" or callback_data == "cancel_settings_flow":
            if chat_id in user_request_states:
                del user_request_states[chat_id]
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🚫 Operation canceled. What else can I help you with?",
                    "reply_markup": get_main_reply_keyboard()
                })
            return "OK"
        elif callback_data.startswith("admin_cmd:"): # NEW: Handle admin inline commands
            admin_command = callback_data[len("admin_cmd:"):]
            str_chat_id = str(chat_id)

            if ADMIN_ID and str_chat_id == ADMIN_ID:
                if admin_command == "status":
                    track_command("/admin_status_inline")
                    status_text = "✅ Bot is running.\n"
                    if _games_data:
                        status_text += f"🎮 Game data loaded successfully. Total games: {len(_games_data)}\n"
                    else:
                        status_text += "❌ Game data not loaded. Check server logs.\n"
                    status_text += f"📊 Analytics loaded. Total unique users: {_analytics_data['total_users']}."
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": status_text,
                        "parse_mode": "Markdown",
                        "reply_to_message_id": message_id
                    })
                elif admin_command == "reload_data":
                    track_command("/reload_data_inline")
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "🔄 Attempting to reload game data...",
                        "reply_to_message_id": message_id
                    })
                    success = load_games()
                    if success:
                        requests.post(f"{BASE_URL}/sendMessage", json={
                            "chat_id": chat_id,
                            "text": "✅ Game data reloaded successfully!",
                            "reply_to_message_id": message_id
                        })
                    else:
                        requests.post(f"{BASE_URL}/sendMessage", json={
                            "chat_id": chat_id,
                            "text": "❌ Failed to reload game data. Check server logs.",
                            "reply_to_message_id": message_id
                        })
                elif admin_command == "analytics":
                    track_command("/analytics_inline")
                    analytics_report = "📊 *Bot Usage Analytics*\n\n"
                    analytics_report += f"👥 *Total Unique Users:* {_analytics_data['total_users']}\n\n"
                    
                    analytics_report += "*Commands Used:*\n"
                    if _analytics_data["commands_used"]:
                        sorted_commands = sorted(_analytics_data["commands_used"].items(), key=lambda item: item[1], reverse=True)
                        for cmd, count in sorted_commands:
                            analytics_report += f"  `{cmd}`: {count}\n"
                    else:
                        analytics_report += "  _No commands used yet._\n"
                    analytics_report += "\n"

                    analytics_report += "*Top Searches:*\n"
                    if _analytics_data["top_searches"]:
                        sorted_searches = sorted(_analytics_data["top_searches"].items(), key=lambda item: item[1], reverse=True)[:5]
                        for query, count in sorted_searches:
                            analytics_report += f"  `{query}`: {count}\n"
                    else:
                        analytics_report += "  _No searches yet._\n"
                    analytics_report += "\n"

                    analytics_report += "*Game Details Views:*\n"
                    if _analytics_data["game_details_views"]:
                        sorted_views = sorted(_analytics_data["game_details_views"].items(), key=lambda item: item[1], reverse=True)[:5]
                        for url, count in sorted_views:
                            game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                            analytics_report += f"  `{game_title}`: {count}\n"
                    else:
                        analytics_report += "  _No game details viewed yet._\n"
                    analytics_report += "\n"

                    analytics_report += "*Game Shares:*\n"
                    if _analytics_data["game_shares"]:
                        sorted_shares = sorted(_analytics_data["game_shares"].items(), key=lambda item: item[1], reverse=True)[:5]
                        for url, count in sorted_shares:
                            game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                            analytics_report += f"  `{game_title}`: {count}\n"
                    else:
                        analytics_report += "  _No games shared yet._\n"
                    analytics_report += "\n"

                    analytics_report += "*Feedback Types:*\n"
                    if _analytics_data["feedback_types"]:
                        sorted_feedback = sorted(_analytics_data["feedback_types"].items(), key=lambda item: item[1], reverse=True)
                        for f_type, count in sorted_feedback:
                            analytics_report += f"  `{f_type}`: {count}\n"
                    else:
                        analytics_report += "  _No feedback received yet._\n"

                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": analytics_report,
                        "parse_mode": "Markdown",
                        "reply_to_message_id": message_id
                    })
                else:
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "Unknown admin command.",
                        "reply_to_message_id": message_id
                    })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🚫 You are not authorized to use admin commands.",
                    "reply_to_message_id": message_id
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

    track_user(chat_id)

    # --- Admin Commands (Text-based and new /admin_menu) ---
    if ADMIN_ID and str_chat_id == ADMIN_ID:
        if lower_msg == "/admin_status":
            track_command("/admin_status")
            status_text = "✅ Bot is running.\n"
            if _games_data:
                status_text += f"🎮 Game data loaded successfully. Total games: {len(_games_data)}\n"
            else:
                status_text += "❌ Game data not loaded. Check server logs.\n"
            status_text += f"📊 Analytics loaded. Total unique users: {_analytics_data['total_users']}."
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": status_text,
                "parse_mode": "Markdown"
            })
            return "OK"
        elif lower_msg == "/reload_data":
            track_command("/reload_data")
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
        elif lower_msg == "/analytics":
            track_command("/analytics")
            analytics_report = "📊 *Bot Usage Analytics*\n\n"
            analytics_report += f"👥 *Total Unique Users:* {_analytics_data['total_users']}\n\n"
            
            analytics_report += "*Commands Used:*\n"
            if _analytics_data["commands_used"]:
                sorted_commands = sorted(_analytics_data["commands_used"].items(), key=lambda item: item[1], reverse=True)
                for cmd, count in sorted_commands:
                    analytics_report += f"  `{cmd}`: {count}\n"
            else:
                analytics_report += "  _No commands used yet._\n"
            analytics_report += "\n"

            analytics_report += "*Top Searches:*\n"
            if _analytics_data["top_searches"]:
                sorted_searches = sorted(_analytics_data["top_searches"].items(), key=lambda item: item[1], reverse=True)[:5]
                for query, count in sorted_searches:
                    analytics_report += f"  `{query}`: {count}\n"
            else:
                analytics_report += "  _No searches yet._\n"
            analytics_report += "\n"

            analytics_report += "*Game Details Views:*\n"
            if _analytics_data["game_details_views"]:
                sorted_views = sorted(_analytics_data["game_details_views"].items(), key=lambda item: item[1], reverse=True)[:5]
                for url, count in sorted_views:
                    game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                    analytics_report += f"  `{game_title}`: {count}\n"
            else:
                analytics_report += "  _No game details viewed yet._\n"
            analytics_report += "\n"

            analytics_report += "*Game Shares:*\n"
            if _analytics_data["game_shares"]:
                sorted_shares = sorted(_analytics_data["game_shares"].items(), key=lambda item: item[1], reverse=True)[:5]
                for url, count in sorted_shares:
                    game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                    analytics_report += f"  `{game_title}`: {count}\n"
            else:
                analytics_report += "  _No games shared yet._\n"
            analytics_report += "\n"

            analytics_report += "*Feedback Types:*\n"
            if _analytics_data["feedback_types"]:
                sorted_feedback = sorted(_analytics_data["feedback_types"].items(), key=lambda item: item[1], reverse=True)
                for f_type, count in sorted_feedback:
                    analytics_report += f"  `{f_type}`: {count}\n"
            else:
                analytics_report += "  _No feedback received yet._\n"

            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": analytics_report,
                "parse_mode": "Markdown"
            })
            return "OK"
        elif lower_msg == "/admin_menu": # NEW: Command to show admin inline buttons
            track_command("/admin_menu")
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "⚙️ *Admin Panel:*\nSelect an action:",
                "parse_mode": "Markdown",
                "reply_markup": get_admin_inline_keyboard()
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

    # --- Handle Regular Commands and Natural Language Search ---
    if lower_msg.startswith("/start"):
        track_command("/start")
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
        # If admin, also send the admin inline keyboard
        if ADMIN_ID and str_chat_id == ADMIN_ID:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "⚙️ *Admin Quick Actions:*\n",
                "parse_mode": "Markdown",
                "reply_markup": get_admin_inline_keyboard()
            })

    elif lower_msg.startswith("/help") or lower_msg == "❓ help":
        track_command("/help")
        help_text = (
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
            "📤 *Share Game:*\n"
            "   Tap the `📤 Share Game` button to share game details with your friends.\n\n"
            "❌ *Cancel:*\n"
            "   Type `/cancel` or tap the `❌ Cancel` button to stop any ongoing operation (like requesting a game or sending feedback).\n\n"
        )
        if ADMIN_ID and str_chat_id == ADMIN_ID:
            help_text += (
                "--- *Admin Commands* ---\n"
                "⚙️ `/admin_menu`: Show inline buttons for admin actions.\n"
                "✅ `/admin_status`: Check bot status and data load.\n"
                "🔄 `/reload_data`: Reload game data from source.\n"
                "📊 `/analytics`: View bot usage statistics.\n\n"
            )
        help_text += "Got it? Let's find some games! 🎮"

        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": help_text,
            "parse_mode": "Markdown"
        })

    elif lower_msg.startswith("/random") or lower_msg == "🎲 random game":
        track_command("/random")
        if not _games_data:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })
            return "OK"

        send_game(chat_id, random.choice(_games_data))

    elif lower_msg.startswith("/latest") or lower_msg == "✨ latest games":
        track_command("/latest")
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
        track_command("/request")
        user_request_states[chat_id] = {"flow": "game_request", "step": "title"}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🎮 Enter the title of the game you want to request:",
            "reply_markup": get_cancel_reply_keyboard()
        })

    elif lower_msg.startswith("/feedback") or lower_msg == "💬 send feedback":
        track_command("/feedback")
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
    
    # Natural Language Search (Fallback if no other command matches)
    else:
        query = user_msg
        track_command("search")
        track_search(query)
        if not _games_data:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ Could not load game data. Please try again later."
            })
            return "OK"

        initial_results = [g for g in _games_data if query.lower() in g["title"].lower()]
        final_results = initial_results

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