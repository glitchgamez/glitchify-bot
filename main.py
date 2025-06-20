import os
import json
import random
import requests
from flask import Flask, request
from collections import defaultdict # For easier counting

# New: Import AI SDK components
from ai_sdk import generateText
from ai_sdk.openai import openai

app = Flask(__app__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Telegram ID of admin (as a string)
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_URL = "https://glitchify.space/search-index.json"
ANALYTICS_FILE = "analytics_data.json" # File to store analytics data
DIALECTS_FILE = "user_dialects.json" # New: File to store user dialect preferences

# Global variables
_games_data = []
_analytics_data = {} # Stores bot usage analytics
_user_dialects = {} # New: Stores user dialect preferences: {chat_id: "slang" | "formal"}

# --- Configuration ---
GAMES_PER_PAGE = 3 # Define how many games to show per page for search results

# --- Message Dictionary (New) ---
MESSAGES = {
"slang": {
    "welcome": """Yo, what's good, gamer! 🎮 Welcome to Glitchify Bot!

I'm here to hook you up with dope games, help you find new faves, or even drop a request for that fire title you're lookin' for.
Just hit me up with a game name or tap those buttons below! 👇""",
    "admin_quick_actions": "⚙️ *Admin Quick Actions:*
",
    "help_intro": "📚 *Glitchify Bot: The Lowdown* 👇

Here's how you can vibe with me:

",
    "help_search": "🔍 *Search for Games:*
   Just type the name of a game (like `Mario` or `Fortnite`) and I'll hit you back with the deets! 🎮",
    "help_random": "🎲 *Random Banger:*
   Tap the `🎲 Random Banger` button or type `/random` to get a surprise banger! 🔥",
    "help_latest": "✨ *Latest Drops:*
   Tap the `✨ Latest Drops` button or type `/latest` to see the freshest games added. 🆕",
    "help_request": "📝 *Request a Game:*
   Tap the `📝 Request a Game` button or type `/request` to tell me about a game you're tryna see added. Spill the tea! ☕",
    "help_feedback": "💬 *Spill the Tea:*
   Tap the `💬 Spill the Tea` button or type `/feedback` to send me a bug report, a fire suggestion, or just general vibes. 🗣️",
    "help_details": "🔗 *Get the Full Scoop:*
   After I send a game, tap the `✨ Get the Full Scoop` button to dive deep into the deets. 📖",
    "help_share": "📤 *Flex on Your Squad:*
   Tap the `📤 Flex on Your Squad` button to share game deets with your pals. 🤝",
    "help_cancel": "❌ *Bail Out:*
   Type `/cancel` or tap the `❌ Bail Out` button to dip out of any ongoing convo. Peace! ✌️",
    "help_vibe": "🗣️ `/vibe`: Switch up how I talk to you! 😎/🎩",
    "help_ai_vibe_check": "🧠 `/vibe_check <game_title>`: Get a quick, slang-style summary of a game's description. It's like a quick vibe check! 🤙", # New help entry
    "help_admin_intro": "--- *Admin Only - For the OGs* ---
",
    "help_admin_menu": "⚙️ `/admin_menu`: Pull up the admin inline buttons. 📲",
    "help_admin_status": "✅ `/admin_status`: Check if the bot's still vibin'. 🟢",
    "help_reload_data": "🔄 `/reload_data`: Refresh the game stash. ♻️",
    "help_analytics": "📊 `/analytics`: Peep the bot's usage stats. 📈",
    "help_outro": "Got it? Let's find some games! 🎮",
    "game_data_load_fail": "❌ My bad, fam. Can't load the game data right now. Try again later, maybe? 😔",
    "no_games_on_page": "Nah, no games on this page, fam. 😔",
    "search_results_intro": "Peep these results for '{query}' (Page {page_num} of {total_pages}):",
    "end_of_results": "You've hit the end of the results, fam. No more pages! 🛑",
    "search_lost_track": "My bad, I lost track of your search. Try searching again, maybe? 🤔",
    "game_details_not_found": "❌ Game deets? Nah, couldn't find 'em. Link might be old or the game dipped. 🤷‍♀️",
    "game_not_found_share": "❌ Game not found for sharing. It might have been removed or the link is old. 😔",
    "feedback_prompt": "Bet! You picked '{feedback_type}'.

Now hit me with the full message, no cap:",
    "feedback_sent": "✅ Preciate the feedback, fam! It's been sent! 🙏",
    "cancel_success": "🚫 Operation canceled. What else you need, G? 🎮",
    "nothing_to_cancel": "Ain't nothing to cancel. You're chillin', not in a flow. 😎",
    "in_middle_of_flow": "Yo, you're in the middle of something! Finish up or hit '❌ Bail Out' to dip. 🏃‍♂️",
    "game_request_title_prompt": "🎮 Drop the title of the game you're tryna request:",
    "game_request_platform_prompt": "🕹️ What platform we talkin'?",
    "game_request_sent": "✅ Your game request is in the bag! Sent it off! 🚀",
    "no_games_found_search": "My bad, couldn't find any games for '{query}'. Try a different vibe, maybe? 🤷‍♀️",
    "admin_status_running": "✅ Bot's vibin'. All good here! 😎",
    "admin_status_games_loaded": "🎮 Game data loaded: {num_games} games. We got the whole stash!",
    "admin_status_games_not_loaded": "❌ Game data not loaded. Check the server logs, fam. Something's off.",
    "admin_status_analytics_loaded": "📊 Analytics on point. Total unique users: {total_users}. Peep the growth!📈",
    "admin_reload_prompt": "🔄 Reloading game data, hold up... This might take a sec. ⏳",
    "admin_reload_success": "✅ Game data reloaded, we good! Fresh data incoming! ✨",
    "admin_reload_fail": "❌ Nah, couldn't reload game data. Check the server logs, fam. Something's buggin'. 🐛",
    "admin_analytics_report_intro": "📊 *Bot Usage Analytics - Peep the Stats, Boss!* 😎

",
    "admin_analytics_total_users": "👥 *Total Unique Users:* {total_users} (Growing the squad!)

",
    "admin_analytics_commands_used_intro": "*Commands Used:*
",
    "admin_analytics_commands_used_item": "  `{cmd}`: {count} times
",
    "admin_analytics_commands_used_none": "  _No commands used yet. Crickets... 🦗_
",
    "admin_analytics_top_searches_intro": "*Top Searches:*
",
    "admin_analytics_top_searches_item": "  `{query}`: {count} hits
",
    "admin_analytics_top_searches_none": "  _No searches yet. Get to typing! ⌨️_
",
    "admin_analytics_game_views_intro": "*Game Details Views:*
",
    "admin_analytics_game_views_item": "  `{game_title}`: {count} peeks
",
    "admin_analytics_game_views_none": "  _No game details viewed yet. What's good? 🤔_
",
    "admin_analytics_game_shares_intro": "*Game Shares:*
",
    "admin_analytics_game_shares_item": "  `{game_title}`: {count} shares
",
    "admin_analytics_game_shares_none": "  _No games shared yet. Spread the word! 🗣️_
",
    "admin_analytics_feedback_intro": "*Feedback Types:*
",
    "admin_analytics_feedback_item": "  `{f_type}`: {count} received
",
    "admin_analytics_feedback_none": "  _No feedback received yet. Don't be shy! 🤫_
",
    "admin_unknown_cmd": "Unknown admin command, fam. What's that even mean? 🧐",
    "admin_unauthorized": "🚫 Nah, you ain't authorized to use admin commands. Stay in your lane, fam. 🙅‍♂️",
    "admin_menu_prompt": "⚙️ *Admin Panel:*
What's the move, boss? 👇",
    "inline_no_results": "My bad, couldn't find any games for '{query_string}'. Try a different vibe, maybe? 🤷‍♀️",
    "inline_view_on_glitchify": "🔗 Peep on Glitchify",
    "inline_get_full_scoop": "✨ Get the Full Scoop",
    "inline_share_game": "📤 Flex on Your Squad",
    "main_random_game": "🎲 Random Banger",
    "main_latest_games": "✨ Latest Drops",
    "main_request_game": "📝 Request a Game",
    "main_send_feedback": "💬 Spill the Tea",
    "main_help": "❓ Help Me Out",
    "main_vibe_check": "🗣️ Vibe Check",
    "cancel_button": "❌ Bail Out",
    "admin_analytics_button": "📊 Peep the Stats",
    "admin_reload_button": "🔄 Reload the Stash",
    "admin_status_button": "✅ Bot's Vibe Check",
    "share_game_button": "Share this game with a friend",
    "feedback_bug_report": "🐛 Bug Report (It's broken!)",
    "feedback_suggestion": "💡 Suggestion (Big Brain Time!)",
    "feedback_general": "💬 General Vibes (Just Chillin')",
    "pagination_previous": "⬅️ Previous Page",
    "pagination_next": "Next Page ➡️",
    "pagination_view_all": "🔍 See All on Glitchify",
    "dialect_prompt": "Yo, what's your vibe? Pick how I should talk to you: 😎",
    "dialect_slang_button": "😎 Slang",
    "dialect_formal_button": "🎩 Formal",
    "dialect_set_slang": "Aight, we're on that slang vibe now! Let's get it! 😎",
    "dialect_set_formal": "Understood. I will now communicate in a more formal manner. 🎩",
    "ai_vibe_check_prompt": "Gimme a game title to get its vibe check, fam! 🎮",
    "ai_vibe_check_generating": "Hold up, fam! I'm getting the AI to cook up that vibe check for '{game_title}'... 🧠",
    "ai_vibe_check_result": "Here's the vibe check for *{game_title}*:

{summary}",
    "ai_vibe_check_no_game": "My bad, couldn't find '{game_title}' to vibe check. Is that even a real game, fam? 🤔",
    "ai_vibe_check_error": "Yo, something glitched while getting the vibe check. Try again later, maybe? 🐛"
},
"formal": {
    "welcome": """🎮 Welcome to Glitchify Bot!

I can assist you in finding games, discovering new titles, or submitting a game request.
Simply type your query or use the provided buttons below!""",
    "admin_quick_actions": "⚙️ *Admin Quick Actions:*
",
    "help_intro": "📚 *Glitchify Bot Help Guide*

Here's how you can use me:

",
    "help_search": "🔍 *Search for Games:*
   Just type the name of a game (e.g., `Mario`, `Fortnite`) and I'll search for it!",
    "help_random": "🎲 *Random Game:*
   Tap the `🎲 Random Game` button or type `/random` to get a surprise game suggestion.",
    "help_latest": "✨ *Latest Games:*
   Tap the `✨ Latest Games` button or type `/latest` to see the most recently added games.",
    "help_request": "📝 *Request a Game:*
   Tap the `📝 Request a Game` button or type `/request` to tell me about a game you'd like to see added.",
    "help_feedback": "💬 *Send Feedback:*
   Tap the `💬 Send Feedback` button or type `/feedback` to send me a bug report, suggestion, or general feedback.",
    "help_details": "🔗 *View Details:*
   After I send a game, tap the `✨ Show More Details` button to get more info about it.",
    "help_share": "📤 *Share Game:*
   Tap the `📤 Share Game` button to share game details with your friends.",
    "help_cancel": "❌ *Cancel:*
   Type `/cancel` or tap the `❌ Cancel` button to stop any ongoing operation (like requesting a game or sending feedback).",
    "help_vibe": "🗣️ `/vibe`: Select your preferred communication style. 😎/🎩",
    "help_ai_vibe_check": "🧠 `/vibe_check <game_title>`: Obtain an AI-generated summary of a game's description.", # New help entry
    "help_admin_intro": "--- *Admin Commands* ---
",
    "help_admin_menu": "⚙️ `/admin_menu`: Show inline buttons for admin actions.",
    "help_admin_status": "✅ `/admin_status`: Check bot status and data load.",
    "help_reload_data": "🔄 `/reload_data`: Reload game data from source.",
    "help_analytics": "📊 `/analytics`: View bot usage statistics.",
    "help_outro": "Got it? Let's find some games! 🎮",
    "game_data_load_fail": "❌ Could not load game data. Please try again later.",
    "no_games_on_page": "No games found for this page.",
    "search_results_intro": "Showing results for '{query}' (Page {page_num} of {total_pages}):",
    "end_of_results": "You've reached the end of the results.",
    "search_lost_track": "Sorry, I lost track of your search. Please try searching again.",
    "game_details_not_found": "❌ Game details not found. The game might have been removed or the link is old.",
    "game_not_found_share": "❌ Game not found for sharing. It might have been removed or the link is old.",
    "feedback_prompt": "Got it! You've chosen '{feedback_type}'.

Please send me your detailed feedback message now:",
    "feedback_sent": "✅ Thank you for your feedback! It has been sent.",
    "cancel_success": "🚫 Operation canceled. What else can I help you with?",
    "nothing_to_cancel": "Nothing to cancel. You're not in an active operation.",
    "in_middle_of_flow": "Please complete the current operation or type '❌ Cancel' to exit.",
    "game_request_title_prompt": "🎮 Enter the title of the game you want to request:",
    "game_request_platform_prompt": "🕹️ Enter the platform (e.g., PC, PS4, PS3):",
    "game_request_sent": "✅ Your game request has been sent!",
    "no_games_found_search": "❌ Sorry, I couldn't find any games matching '{query}'. Try a different term!",
    "admin_status_running": "✅ Bot is running.",
    "admin_status_games_loaded": "🎮 Game data loaded successfully. Total games: {num_games}.",
    "admin_status_games_not_loaded": "❌ Game data not loaded. Check server logs.",
    "admin_status_analytics_loaded": "📊 Analytics loaded. Total unique users: {total_users}.",
    "admin_reload_prompt": "🔄 Attempting to reload game data...",
    "admin_reload_success": "✅ Game data reloaded successfully!",
    "admin_reload_fail": "❌ Failed to reload game data. Check server logs.",
    "admin_analytics_report_intro": "📊 *Bot Usage Analytics*

",
    "admin_analytics_total_users": "👥 *Total Unique Users:* {total_users}

",
    "admin_analytics_commands_used_intro": "*Commands Used:*
",
    "admin_analytics_commands_used_item": "  `{cmd}`: {count} times
",
    "admin_analytics_commands_used_none": "  _No commands used yet._
",
    "admin_analytics_top_searches_intro": "*Top Searches:*
",
    "admin_analytics_top_searches_item": "  `{query}`: {count} hits
",
    "admin_analytics_top_searches_none": "  _No searches yet._
",
    "admin_analytics_game_views_intro": "*Game Details Views:*
",
    "admin_analytics_game_views_item": "  `{game_title}`: {count} views
",
    "admin_analytics_game_views_none": "  _No game details viewed yet._
",
    "admin_analytics_game_shares_intro": "*Game Shares:*
",
    "admin_analytics_game_shares_item": "  `{game_title}`: {count} shares
",
    "admin_analytics_game_shares_none": "  _No games shared yet._
",
    "admin_analytics_feedback_intro": "*Feedback Types:*
",
    "admin_analytics_feedback_item": "  `{f_type}`: {count} received
",
    "admin_analytics_feedback_none": "  _No feedback received yet._
",
    "admin_unknown_cmd": "Unknown admin command.",
    "admin_unauthorized": "🚫 You are not authorized to use admin commands.",
    "admin_menu_prompt": "⚙️ *Admin Panel:*
Select an action:",
    "inline_no_results": "Sorry, I couldn't find any games matching '{query_string}'. Try a different term!",
    "inline_view_on_glitchify": "🔗 View on Glitchify",
    "inline_get_full_scoop": "✨ Show More Details",
    "inline_share_game": "📤 Share Game",
    "main_random_game": "🎲 Random Game",
    "main_latest_games": "✨ Latest Games",
    "main_request_game": "📝 Request a Game",
    "main_send_feedback": "💬 Send Feedback",
    "main_help": "❓ Help",
    "main_vibe_check": "🗣️ Dialect",
    "cancel_button": "❌ Cancel",
    "admin_analytics_button": "📊 Analytics",
    "admin_reload_button": "🔄 Reload Data",
    "admin_status_button": "✅ Bot Status",
    "share_game_button": "Share this game with a friend",
    "feedback_bug_report": "🐛 Bug Report",
    "feedback_suggestion": "💡 Suggestion",
    "feedback_general": "💬 General Feedback",
    "pagination_previous": "⬅️ Previous",
    "pagination_next": "Next ➡️",
    "pagination_view_all": "🔍 View All Results on Glitchify",
    "dialect_prompt": "Please select your preferred communication style: 🎩",
    "dialect_slang_button": "😎 Slang",
    "dialect_formal_button": "🎩 Formal",
    "dialect_set_slang": "Understood. I will now communicate in a more casual and slang-oriented manner. 😎",
    "dialect_set_formal": "Understood. I will now communicate in a more formal manner. 🎩",
    "ai_vibe_check_prompt": "Please provide a game title for the AI vibe check. 🎮",
    "ai_vibe_check_generating": "Generating AI vibe check for '{game_title}'... 🧠",
    "ai_vibe_check_result": "Here is the AI-generated summary for *{game_title}*:

{summary}",
    "ai_vibe_check_no_game": "Could not find '{game_title}' to perform a vibe check. Please ensure the title is correct. 🤔",
    "ai_vibe_check_error": "An error occurred while generating the AI vibe check. Please try again later. 🐛"
}
}

def get_message(chat_id, key, **kwargs):
"""Retrieves a message string based on user's dialect preference."""
str_chat_id = str(chat_id)
dialect = _user_dialects.get(str_chat_id, "slang") # Default to slang
message_template = MESSAGES.get(dialect, MESSAGES["slang"]).get(key, f"Error: Message key '{key}' not found for dialect '{dialect}'")
return message_template.format(**kwargs)

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

def load_user_dialects():
"""
Loads user dialect preferences from the JSON file.
"""
global _user_dialects
if os.path.exists(DIALECTS_FILE):
    try:
        with open(DIALECTS_FILE, 'r') as f:
            _user_dialects = json.load(f)
        print(f"Successfully loaded {len(_user_dialects)} user dialects.")
    except json.JSONDecodeError as e:
        print(f"Error decoding user dialects JSON: {e}. Starting with empty preferences.")
        _user_dialects = {}
else:
    print("User dialects file not found. Starting with empty preferences.")
    _user_dialects = {}

def save_user_dialects():
"""
Saves user dialect preferences to the JSON file.
"""
try:
    with open(DIALECTS_FILE, 'w') as f:
        json.dump(_user_dialects, f, indent=4)
    print("User dialects saved.")
except IOError as e:
    print(f"Error saving user dialects: {e}")

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
load_user_dialects() # New: Load user dialects on startup

# --- Formatting Functions ---
def format_game(game):
page_url = f"https://glitchify.space/{game['url'].lstrip('/')}"
img_url = page_url.rsplit('/', 1)[0] + "/screenshot1.jpg"
return {
    "text": f"*{game['title']}*
🏷️ `{', '.join(game['tags'])}`
🕒 `{game['modified']}`",
    "url": page_url,
    "thumb": img_url
}

def format_game_details(game):
description = game.get('description', 'No description available.')
genre = ', '.join(game.get('tags', []))
release_date = game.get('release_date', 'N/A')

return (
    f"*{game['title']}*

"
    f"📝 *Description:*
{description}

"
    f"🏷️ *Tags/Genre:* `{genre}`
"
    f"🕒 *Last Modified:* `{game['modified']}`
"
    f"🗓️ *Release Date:* `{release_date}`"
)

# --- AI Integration Function (New) ---
async def get_ai_game_summary(game_title, game_description, dialect):
"""
Generates a slang or formal summary of a game description using AI.
"""
model = openai("gpt-4o") # Using GPT-4o model

system_prompt = ""
if dialect == "slang":
    system_prompt = "You are a cool, slang-talking gamer bot. Summarize the following game description in a short, engaging, and slangy way, like you're giving a quick 'vibe check' to your homies. Keep it concise, 2-3 sentences max."
else: # formal
    system_prompt = "You are a helpful and concise bot. Summarize the following game description in a brief and informative manner, 2-3 sentences max."

prompt = f"Game Title: {game_title}
Game Description: {game_description}

Summarize this game's description."

try:
    result = await generateText(
        model=model,
        prompt=prompt,
        system=system_prompt
    )
    return result.text
except Exception as e:
    print(f"Error generating AI summary: {e}")
    return None

# --- Telegram API Interaction Functions ---
def send_game(chat_id, game):
msg = format_game(game)
callback_data_details = f"details:{game['url']}"
callback_data_share = f"share_game:{game['url']}"

inline_keyboard = [
    [{"text": get_message(chat_id, "inline_view_on_glitchify"), "url": msg["url"]}],
    [{"text": get_message(chat_id, "inline_get_full_scoop"), "callback_data": callback_data_details}],
    [{"text": get_message(chat_id, "inline_share_game"), "callback_data": callback_data_share}]
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

def get_main_reply_keyboard(chat_id): # Updated to take chat_id
"""Returns the main reply keyboard markup."""
return {
    "keyboard": [
        [{"text": get_message(chat_id, "main_random_game")}, {"text": get_message(chat_id, "main_latest_games")}],
        [{"text": get_message(chat_id, "main_request_game")}, {"text": get_message(chat_id, "main_send_feedback")}],
        [{"text": get_message(chat_id, "main_vibe_check")}, {"text": get_message(chat_id, "main_help")}] # New vibe check button
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

def get_cancel_reply_keyboard(chat_id): # Updated to take chat_id
"""Returns a reply keyboard with only a cancel button."""
return {
    "keyboard": [
        [{"text": get_message(chat_id, "cancel_button")}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True # Disappear after use
}

def get_admin_inline_keyboard(chat_id): # Updated to take chat_id
"""Returns an inline keyboard markup for admin commands."""
return {
    "inline_keyboard": [
        [{"text": get_message(chat_id, "admin_analytics_button"), "callback_data": "admin_cmd:analytics"}],
        [{"text": get_message(chat_id, "admin_reload_button"), "callback_data": "admin_cmd:reload_data"}],
        [{"text": get_message(chat_id, "admin_status_button"), "callback_data": "admin_cmd:status"}]
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
        "text": get_message(chat_id, "no_games_on_page")
    })
    return

for game in current_page_games:
    send_game(chat_id, game)

pagination_buttons_row = []
if page > 0:
    pagination_buttons_row.append({"text": get_message(chat_id, "pagination_previous"), "callback_data": f"paginate:{page-1}"})

pagination_buttons_row.append({"text": f"Page {page + 1}/{total_pages}", "callback_data": "ignore_page_info"})

if page < total_pages - 1:
    pagination_buttons_row.append({"text": get_message(chat_id, "pagination_next"), "callback_data": f"paginate:{page+1}"})

more_results_button_row = []
if total_games > 0:
    more_results_button_row.append({"text": get_message(chat_id, "pagination_view_all"), "url": f"https://glitchify.space/search-results.html?q={query.replace(' ', '%20')}"})

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
        "text": get_message(chat_id, "search_results_intro", query=query, page_num=page + 1, total_pages=total_pages),
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
        "text": f"Here are the results for '{query}':" # This specific message is kept neutral
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
            [{"text": MESSAGES["slang"]["inline_view_on_glitchify"], "url": formatted_game["url"]}], # Inline query buttons are always slang for consistency
            [{"text": MESSAGES["slang"]["inline_get_full_scoop"], "callback_data": f"details:{game['url']}"}]
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
            "message_text": MESSAGES["slang"]["inline_no_results"].format(query_string=query_string), # Inline query messages are always slang
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
    str_chat_id = str(chat_id) # Define str_chat_id here for use in callbacks

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
                "text": get_message(chat_id, "game_details_not_found"),
                "reply_to_message_id": message_id
            })
    elif callback_data.startswith("share_game:"):
        game_url_path = callback_data[len("share_game:"):]
        track_game_share(game_url_path)
        found_game = next((g for g in _games_data if g["url"] == game_url_path), None)

        if found_game:
            share_text = f"Check out this game: *{found_game['title']}*
🔗 {format_game(found_game)['url']}"
            share_keyboard = {
                "inline_keyboard": [
                    [{"text": get_message(chat_id, "share_game_button"), "switch_inline_query": found_game['title']}]
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
                "text": get_message(chat_id, "game_not_found_share"),
                "reply_to_message_id": message_id
            })
        return "OK"
    elif callback_data.startswith("feedback_type:"):
        feedback_type = callback_data[len("feedback_type:"):]
        user_request_states[chat_id] = {"flow": "feedback", "step": "message", "type": feedback_type}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "feedback_prompt", feedback_type=feedback_type),
            "reply_markup": get_cancel_reply_keyboard(chat_id)
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
                    "text": get_message(chat_id, "end_of_results")
                })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "search_lost_track")
            })
        return "OK"
    elif callback_data == "cancel_feedback_flow" or callback_data == "cancel_settings_flow":
        if chat_id in user_request_states:
            del user_request_states[chat_id]
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "cancel_success"),
                "reply_markup": get_main_reply_keyboard(chat_id)
            })
        return "OK"
    elif callback_data.startswith("admin_cmd:"):
        admin_command = callback_data[len("admin_cmd:"):]
        
        if ADMIN_ID and str_chat_id == ADMIN_ID:
            if admin_command == "status":
                track_command("/admin_status_inline")
                status_text = get_message(chat_id, "admin_status_running") + "
"
                if _games_data:
                    status_text += get_message(chat_id, "admin_status_games_loaded", num_games=len(_games_data)) + "
"
                else:
                    status_text += get_message(chat_id, "admin_status_games_not_loaded") + "
"
                status_text += get_message(chat_id, "admin_status_analytics_loaded", total_users=_analytics_data['total_users'])
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
                    "text": get_message(chat_id, "admin_reload_prompt"),
                    "reply_to_message_id": message_id
                })
                success = load_games()
                if success:
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": get_message(chat_id, "admin_reload_success"),
                        "reply_to_message_id": message_id
                    })
                else:
                    requests.post(f"{BASE_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": get_message(chat_id, "admin_reload_fail"),
                        "reply_to_message_id": message_id
                    })
            elif admin_command == "analytics":
                track_command("/analytics_inline")
                analytics_report = get_message(chat_id, "admin_analytics_report_intro")
                analytics_report += get_message(chat_id, "admin_analytics_total_users", total_users=_analytics_data['total_users'])
                
                analytics_report += get_message(chat_id, "admin_analytics_commands_used_intro")
                if _analytics_data["commands_used"]:
                    sorted_commands = sorted(_analytics_data["commands_used"].items(), key=lambda item: item[1], reverse=True)
                    for cmd, count in sorted_commands:
                        analytics_report += get_message(chat_id, "admin_analytics_commands_used_item", cmd=cmd, count=count)
                else:
                    analytics_report += get_message(chat_id, "admin_analytics_commands_used_none")
                analytics_report += "
"

                analytics_report += get_message(chat_id, "admin_analytics_top_searches_intro")
                if _analytics_data["top_searches"]:
                    sorted_searches = sorted(_analytics_data["top_searches"].items(), key=lambda item: item[1], reverse=True)[:5]
                    for query, count in sorted_searches:
                        analytics_report += get_message(chat_id, "admin_analytics_top_searches_item", query=query, count=count)
                else:
                    analytics_report += get_message(chat_id, "admin_analytics_top_searches_none")
                analytics_report += "
"

                analytics_report += get_message(chat_id, "admin_analytics_game_views_intro")
                if _analytics_data["game_details_views"]:
                    sorted_views = sorted(_analytics_data["game_details_views"].items(), key=lambda item: item[1], reverse=True)[:5]
                    for url, count in sorted_views:
                        game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                        analytics_report += get_message(chat_id, "admin_analytics_game_views_item", game_title=game_title, count=count)
                else:
                    analytics_report += get_message(chat_id, "admin_analytics_game_views_none")
                analytics_report += "
"

                analytics_report += get_message(chat_id, "admin_analytics_game_shares_intro")
                if _analytics_data["game_shares"]:
                    sorted_shares = sorted(_analytics_data["game_shares"].items(), key=lambda item: item[1], reverse=True)[:5]
                    for url, count in sorted_shares:
                        game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                        analytics_report += get_message(chat_id, "admin_analytics_game_shares_item", game_title=game_title, count=count)
                else:
                    analytics_report += get_message(chat_id, "admin_analytics_game_shares_none")
                analytics_report += "
"

                analytics_report += get_message(chat_id, "admin_analytics_feedback_intro")
                if _analytics_data["feedback_types"]:
                    sorted_feedback = sorted(_analytics_data["feedback_types"].items(), key=lambda item: item[1], reverse=True)
                    for f_type, count in sorted_feedback:
                        analytics_report += get_message(chat_id, "admin_analytics_feedback_item", f_type=f_type, count=count)
                else:
                    analytics_report += get_message(chat_id, "admin_analytics_feedback_none")
                
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": analytics_report,
                    "parse_mode": "Markdown",
                    "reply_to_message_id": message_id
                })
            else:
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": get_message(chat_id, "admin_unknown_cmd"),
                    "reply_to_message_id": message_id
                })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_unauthorized"),
                "reply_to_message_id": message_id
            })
        return "OK"
    elif callback_data.startswith("set_dialect:"): # New: Handle dialect selection
        dialect = callback_data[len("set_dialect:"):]
        if dialect in ["slang", "formal"]:
            _user_dialects[str_chat_id] = dialect
            save_user_dialects()
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, f"dialect_set_{dialect}"),
                "reply_markup": get_main_reply_keyboard(chat_id) # Update keyboard to reflect new dialect
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_unknown_cmd") # Re-using for unknown dialect
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
        status_text = get_message(chat_id, "admin_status_running") + "
"
        if _games_data:
            status_text += get_message(chat_id, "admin_status_games_loaded", num_games=len(_games_data)) + "
"
        else:
            status_text += get_message(chat_id, "admin_status_games_not_loaded") + "
"
        status_text += get_message(chat_id, "admin_status_analytics_loaded", total_users=_analytics_data['total_users'])
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
            "text": get_message(chat_id, "admin_reload_prompt")
        })
        success = load_games()
        if success:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_reload_success")
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_reload_fail")
            })
        return "OK"
    elif lower_msg == "/analytics":
        track_command("/analytics")
        analytics_report = get_message(chat_id, "admin_analytics_report_intro")
        analytics_report += get_message(chat_id, "admin_analytics_total_users", total_users=_analytics_data['total_users'])
        
        analytics_report += get_message(chat_id, "admin_analytics_commands_used_intro")
        if _analytics_data["commands_used"]:
            sorted_commands = sorted(_analytics_data["commands_used"].items(), key=lambda item: item[1], reverse=True)
            for cmd, count in sorted_commands:
                analytics_report += get_message(chat_id, "admin_analytics_commands_used_item", cmd=cmd, count=count)
        else:
            analytics_report += get_message(chat_id, "admin_analytics_commands_used_none")
        analytics_report += "
"

        analytics_report += get_message(chat_id, "admin_analytics_top_searches_intro")
        if _analytics_data["top_searches"]:
            sorted_searches = sorted(_analytics_data["top_searches"].items(), key=lambda item: item[1], reverse=True)[:5]
            for query, count in sorted_searches:
                analytics_report += get_message(chat_id, "admin_analytics_top_searches_item", query=query, count=count)
        else:
            analytics_report += get_message(chat_id, "admin_analytics_top_searches_none")
        analytics_report += "
"

        analytics_report += get_message(chat_id, "admin_analytics_game_views_intro")
        if _analytics_data["game_details_views"]:
            sorted_views = sorted(_analytics_data["game_details_views"].items(), key=lambda item: item[1], reverse=True)[:5]
            for url, count in sorted_views:
                game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                analytics_report += get_message(chat_id, "admin_analytics_game_views_item", game_title=game_title, count=count)
        else:
            analytics_report += get_message(chat_id, "admin_analytics_game_views_none")
        analytics_report += "
"

        analytics_report += get_message(chat_id, "admin_analytics_game_shares_intro")
        if _analytics_data["game_shares"]:
            sorted_shares = sorted(_analytics_data["game_shares"].items(), key=lambda item: item[1], reverse=True)[:5]
            for url, count in sorted_shares:
                game_title = next((g['title'] for g in _games_data if g['url'] == url), url)
                analytics_report += get_message(chat_id, "admin_analytics_game_shares_item", game_title=game_title, count=count)
        else:
            analytics_report += get_message(chat_id, "admin_analytics_game_shares_none")
        analytics_report += "
"

        analytics_report += get_message(chat_id, "admin_analytics_feedback_intro")
        if _analytics_data["feedback_types"]:
            sorted_feedback = sorted(_analytics_data["feedback_types"].items(), key=lambda item: item[1], reverse=True)
            for f_type, count in sorted_feedback:
                analytics_report += get_message(chat_id, "admin_analytics_feedback_item", f_type=f_type, count=count)
        else:
            analytics_report += get_message(chat_id, "admin_analytics_feedback_none")

        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": analytics_report,
            "parse_mode": "Markdown"
        })
        return "OK"
    elif lower_msg == "/admin_menu":
        track_command("/admin_menu")
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "admin_menu_prompt"),
            "parse_mode": "Markdown",
            "reply_markup": get_admin_inline_keyboard(chat_id)
        })
        return "OK"
    elif lower_msg.startswith("/admin_"):
        if not ADMIN_ID:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_unauthorized") # Re-using for not configured
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "admin_unauthorized")
            })
        return "OK"

# --- Handle Cancel Command (prioritized) ---
if lower_msg == "/cancel" or lower_msg == get_message(chat_id, "cancel_button").lower():
    track_command("/cancel")
    if chat_id in user_request_states:
        del user_request_states[chat_id]
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "cancel_success"),
            "reply_markup": get_main_reply_keyboard(chat_id)
        })
    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "nothing_to_cancel"),
            "reply_markup": get_main_reply_keyboard(chat_id)
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
                "text": get_message(chat_id, "game_request_platform_prompt"),
                "reply_markup": get_cancel_reply_keyboard(chat_id)
            })
        elif current_step == "platform":
            title = user_request_states[chat_id]["title"]
            platform = user_msg
            del user_request_states[chat_id]
            msg = f"📥 *New Game Request:*

🎮 *Title:* {title}
🕹️ *Platform:* {platform}
👤 From user: `{chat_id}`"
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": ADMIN_ID,
                "text": msg,
                "parse_mode": "Markdown"
            })
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "game_request_sent"),
                "reply_markup": get_main_reply_keyboard(chat_id)
            })
        return "OK"

    elif current_flow == "feedback":
        if current_step == "message":
            feedback_type = user_request_states[chat_id]["type"]
            feedback_message = user_msg
            track_feedback(feedback_type)
            del user_request_states[chat_id]

            admin_feedback_msg = (
                f"📧 *New Feedback Received:*

"
                f"📝 *Type:* {feedback_type}
"
                f"💬 *Message:*
{feedback_message}

"
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
                "text": get_message(chat_id, "feedback_sent"),
                "reply_markup": get_main_reply_keyboard(chat_id)
            })
        return "OK"
    
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": get_message(chat_id, "in_middle_of_flow")
    })
    return "OK"


# --- Handle Regular Commands and Natural Language Search ---
if lower_msg.startswith("/start"):
    track_command("/start")
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": get_message(chat_id, "welcome"),
        "parse_mode": "Markdown",
        "reply_markup": get_main_reply_keyboard(chat_id)
    })
    # If admin, also send the admin inline keyboard
    if ADMIN_ID and str_chat_id == ADMIN_ID:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "admin_quick_actions"),
            "parse_mode": "Markdown",
            "reply_markup": get_admin_inline_keyboard(chat_id)
        })

elif lower_msg.startswith("/help") or lower_msg == get_message(chat_id, "main_help").lower():
    track_command("/help")
    help_text = get_message(chat_id, "help_intro")
    help_text += get_message(chat_id, "help_search") + "

"
    help_text += get_message(chat_id, "help_random") + "

"
    help_text += get_message(chat_id, "help_latest") + "

"
    help_text += get_message(chat_id, "help_request") + "

"
    help_text += get_message(chat_id, "help_feedback") + "

"
    help_text += get_message(chat_id, "help_details") + "

"
    help_text += get_message(chat_id, "help_share") + "

"
    help_text += get_message(chat_id, "help_cancel") + "

"
    help_text += get_message(chat_id, "help_vibe") + "

"
    help_text += get_message(chat_id, "help_ai_vibe_check") + "

" # New help entry
    
    if ADMIN_ID and str_chat_id == ADMIN_ID:
        help_text += get_message(chat_id, "help_admin_intro")
        help_text += get_message(chat_id, "help_admin_menu") + "
"
        help_text += get_message(chat_id, "help_admin_status") + "
"
        help_text += get_message(chat_id, "help_reload_data") + "
"
        help_text += get_message(chat_id, "help_analytics") + "

"
    help_text += get_message(chat_id, "help_outro")

    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": help_text,
        "parse_mode": "Markdown"
    })

elif lower_msg.startswith("/random") or lower_msg == get_message(chat_id, "main_random_game").lower():
    track_command("/random")
    if not _games_data:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "game_data_load_fail")
        })
        return "OK"

    send_game(chat_id, random.choice(_games_data))

elif lower_msg.startswith("/latest") or lower_msg == get_message(chat_id, "main_latest_games").lower():
    track_command("/latest")
    if not _games_data:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "game_data_load_fail")
        })
        return "OK"

    sorted_games = sorted(_games_data, key=lambda g: g["modified"], reverse=True)
    for game in sorted_games[:3]:
        send_game(chat_id, game)
    if len(sorted_games) > 3:
            requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"🔎 Found {len(sorted_games)} latest drops. View more on Glitchify: https://glitchify.space/search-results.html?q=latest", # This specific message is kept neutral
            "parse_mode": "Markdown"
        })

elif lower_msg.startswith("/request") or lower_msg == get_message(chat_id, "main_request_game").lower():
    track_command("/request")
    user_request_states[chat_id] = {"flow": "game_request", "step": "title"}
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": get_message(chat_id, "game_request_title_prompt"),
        "reply_markup": get_cancel_reply_keyboard(chat_id)
    })

elif lower_msg.startswith("/feedback") or lower_msg == get_message(chat_id, "main_send_feedback").lower():
    track_command("/feedback")
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": get_message(chat_id, "feedback_prompt", feedback_type=""), # Feedback prompt is generic here
        "reply_markup": {
            "inline_keyboard": [
                [{"text": get_message(chat_id, "feedback_bug_report"), "callback_data": "feedback_type:Bug Report"}],
                [{"text": get_message(chat_id, "feedback_suggestion"), "callback_data": "feedback_type:Suggestion"}],
                [{"text": get_message(chat_id, "feedback_general"), "callback_data": "feedback_type:General Feedback"}],
                [{"text": get_message(chat_id, "cancel_button"), "callback_data": "cancel_feedback_flow"}]
            ]
        }
    })
elif lower_msg.startswith("/vibe") or lower_msg == get_message(chat_id, "main_vibe_check").lower():
    track_command("/vibe")
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": get_message(chat_id, "dialect_prompt"),
        "reply_markup": {
            "inline_keyboard": [
                [{"text": get_message(chat_id, "dialect_slang_button"), "callback_data": "set_dialect:slang"}],
                [{"text": get_message(chat_id, "dialect_formal_button"), "callback_data": "set_dialect:formal"}]
            ]
        }
    })
elif lower_msg.startswith("/vibe_check"): # New: AI Vibe Check command
    track_command("/vibe_check")
    game_title_query = user_msg[len("/vibe_check"):].strip()
    if not game_title_query:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "ai_vibe_check_prompt")
        })
        return "OK"
    
    found_game = next((g for g in _games_data if game_title_query.lower() in g["title"].lower()), None)

    if found_game:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "ai_vibe_check_generating", game_title=found_game['title'])
        })
        
        # Get the user's current dialect for the AI summary
        user_dialect = _user_dialects.get(str_chat_id, "slang")
        
        # Call the AI function (note: this needs to be awaited in an async context)
        # For simplicity in this Flask example, we'll simulate or use a blocking call if possible.
        # For now, we'll make a blocking call.
        summary = get_ai_game_summary(found_game['title'], found_game.get('description', 'No description available.'), user_dialect)
        
        if summary:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "ai_vibe_check_result", game_title=found_game['title'], summary=summary),
                "parse_mode": "Markdown"
            })
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": get_message(chat_id, "ai_vibe_check_error")
            })
    else:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "ai_vibe_check_no_game", game_title=game_title_query)
        })
    return "OK"

# Natural Language Search (Fallback if no other command matches)
else:
    query = user_msg
    track_command("search")
    track_search(query)
    if not _games_data:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": get_message(chat_id, "game_data_load_fail")
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
            "text": get_message(chat_id, "no_games_found_search", query=query)
        })

return "OK"

# Flask entrypoint (unchanged)
if __name__ == "__main__":
app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
