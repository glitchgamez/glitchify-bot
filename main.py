import json
import random
import requests
import logging
import os
from datetime import datetime
from fuzzywuzzy import process
from telegram import (
    Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
)

# Load environment variables (Render sets them directly)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")  # Set your Telegram @username in Render settings
SEARCH_JSON_URL = "https://glitchify.space/search-index.json"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Analytics tracking
analytics = {"searches": 0, "randoms": 0, "latest": 0, "submissions": []}

# Submission states
SUBMIT_TITLE, SUBMIT_PLATFORM = range(2)
user_submissions = {}

# ========== Helper Functions ==========

def fetch_data():
    try:
        response = requests.get(SEARCH_JSON_URL)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch JSON: {e}")
        return []

def format_game(game):
    return f"🎮 *{game['title']}*\n🏷️ Tags: {', '.join(game['tags'])}\n🕒 Last Modified: {game['modified']}\n🔗 [Open Game Page](https://glitchify.space/{game['url']})"

def send_game_result(update: Update, context: CallbackContext, game):
    image_url = f"https://glitchify.space/{os.path.dirname(game['url'])}/screenshot1.jpg"
    caption = format_game(game)
    button = InlineKeyboardMarkup([[InlineKeyboardButton("Open", url=f"https://glitchify.space/{game['url']}")]])
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=button
    )

# ========== Command Handlers ==========

def start(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("/search"), KeyboardButton("/random")],
        [KeyboardButton("/latest"), KeyboardButton("/submit")],
        [KeyboardButton("/info")]
    ]
    update.message.reply_text("🎮 Welcome to Glitchify Bot!\nPick a command below:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

def info(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🛠️ *Available Commands:*\n"
        "/search <name> - Search for a game\n"
        "/random - Get a random game\n"
        "/latest - Show the most recently modified game\n"
        "/submit - Suggest a new game\n"
        "/info - Show this menu",
        parse_mode="Markdown"
    )

def search(update: Update, context: CallbackContext):
    analytics["searches"] += 1
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("Usage: /search <game name>")
        return

    data = fetch_data()
    titles = [item['title'] for item in data]
    matches = process.extract(query, titles, limit=5)

    found = False
    for match, score in matches:
        if score >= 50:
            game = next(g for g in data if g['title'] == match)
            send_game_result(update, context, game)
            found = True

    if not found:
        update.message.reply_text("❌ No close matches found.")
    else:
        button = [[InlineKeyboardButton("🔍 View All Results", url=f"https://glitchify.space/search-results.html?q={query}")]]
        update.message.reply_text("📄 View the full search results below:", reply_markup=InlineKeyboardMarkup(button))

def random_game(update: Update, context: CallbackContext):
    analytics["randoms"] += 1
    data = fetch_data()
    game = random.choice(data)
    send_game_result(update, context, game)

def latest_game(update: Update, context: CallbackContext):
    analytics["latest"] += 1
    data = fetch_data()
    latest = sorted(data, key=lambda x: x['modified'], reverse=True)[0]
    send_game_result(update, context, latest)

def analytics_view(update: Update, context: CallbackContext):
    if update.effective_user.username != ADMIN_USERNAME:
        update.message.reply_text("⛔ Admins only.")
        return
    text = (
        f"📊 *Analytics:*\n"
        f"🔎 Searches: {analytics['searches']}\n"
        f"🎲 Randoms: {analytics['randoms']}\n"
        f"🆕 Latest Used: {analytics['latest']}\n"
        f"📝 Submissions: {len(analytics['submissions'])}"
    )
    update.message.reply_text(text, parse_mode="Markdown")

# ========== Game Submission Conversation ==========

def submit_start(update: Update, context: CallbackContext):
    update.message.reply_text("🎮 What is the *game title* you'd like to suggest?", parse_mode="Markdown")
    return SUBMIT_TITLE

def receive_title(update: Update, context: CallbackContext):
    user_submissions[update.effective_chat.id] = {"title": update.message.text}
    update.message.reply_text("📦 Great! Now tell me the *platform* (e.g., PC, PS4, Xbox)...", parse_mode="Markdown")
    return SUBMIT_PLATFORM

def receive_platform(update: Update, context: CallbackContext):
    submission = user_submissions.get(update.effective_chat.id, {})
    submission["platform"] = update.message.text
    submission["user"] = update.effective_user.username or "Unknown"
    submission["timestamp"] = datetime.utcnow().isoformat()
    analytics["submissions"].append(submission)
    update.message.reply_text("✅ Thanks! Your game has been submitted for review.")
    return ConversationHandler.END

def cancel_submission(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Submission cancelled.")
    return ConversationHandler.END

# ========== Main Function ==========

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("info", info))
    dp.add_handler(CommandHandler("search", search))
    dp.add_handler(CommandHandler("random", random_game))
    dp.add_handler(CommandHandler("latest", latest_game))
    dp.add_handler(CommandHandler("analytics", analytics_view))

    # Game Submission Conversation
    submit_conv = ConversationHandler(
        entry_points=[CommandHandler("submit", submit_start)],
        states={
            SUBMIT_TITLE: [MessageHandler(Filters.text & ~Filters.command, receive_title)],
            SUBMIT_PLATFORM: [MessageHandler(Filters.text & ~Filters.command, receive_platform)],
        },
        fallbacks=[CommandHandler("cancel", cancel_submission)],
    )
    dp.add_handler(submit_conv)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
