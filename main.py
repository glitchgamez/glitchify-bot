import os
import logging
import json
import random
import requests
from collections import defaultdict
from fuzzywuzzy import process
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
)

# Environment variables (Render)
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# Game view tracker
analytics = defaultdict(int)

# Submission conversation states
TITLE, PLATFORM = range(2)
user_submission = {}

# Load JSON
SEARCH_URL = "https://glitchify.space/search-index.json"
games_data = []

def load_data():
    global games_data
    try:
        response = requests.get(SEARCH_URL)
        if response.status_code == 200:
            games_data = response.json()
    except Exception as e:
        print("Error loading data:", e)

# Helpers
def format_game(game):
    return f"*{game['title']}*\nTags: `{', '.join(game['tags'])}`\nLast Updated: `{game['modified']}`\n[Visit Page](https://glitchify.space/{game['url']})"

def get_thumbnail(url):
    folder = '/'.join(url.split('/')[:-1])
    return f"https://glitchify.space/{folder}/screenshot1.jpg"

def search_games(query, limit=5):
    titles = [g['title'] for g in games_data]
    results = process.extract(query, titles, limit=limit)
    return [g for score in results if score[1] > 50 for g in games_data if g['title'] == score[0]]

# Commands
def start(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("🔍 Search"), KeyboardButton("🎲 Random")],
        [KeyboardButton("🕒 Latest"), KeyboardButton("📤 Submit Game")],
        [KeyboardButton("ℹ️ Info")]
    ]
    update.message.reply_text("Welcome to Glitchify Bot 🎮", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

def info(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🕹️ *Available Commands:*\n"
        "`/search <query>` – Search for a game\n"
        "`/random` – Get a random game\n"
        "`/latest` – Show the latest games\n"
        "`/submit` – Submit a game request\n"
        "`/analytics` – (Admin only) View stats\n",
        parse_mode="Markdown"
    )

def search(update: Update, context: CallbackContext):
    load_data()
    query = ' '.join(context.args)
    if not query:
        update.message.reply_text("Usage: `/search game title`", parse_mode="Markdown")
        return

    results = search_games(query)
    if not results:
        update.message.reply_text("No matching games found.")
        return

    for game in results[:5]:
        analytics[game['title']] += 1
        update.message.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=get_thumbnail(game['url']),
            caption=format_game(game),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 View All", url=f"https://glitchify.space/search-results.html?q={query}")
            ]])
        )

def random_game(update: Update, context: CallbackContext):
    load_data()
    game = random.choice(games_data)
    analytics[game['title']] += 1
    update.message.bot.send_photo(
        chat_id=update.message.chat_id,
        photo=get_thumbnail(game['url']),
        caption=format_game(game),
        parse_mode="Markdown"
    )

def latest(update: Update, context: CallbackContext):
    load_data()
    sorted_games = sorted(games_data, key=lambda x: x['modified'], reverse=True)
    for game in sorted_games[:5]:
        analytics[game['title']] += 1
        update.message.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=get_thumbnail(game['url']),
            caption=format_game(game),
            parse_mode="Markdown"
        )

# Game Submission
def submit(update: Update, context: CallbackContext):
    update.message.reply_text("📝 Please enter the *game title* you want to submit:", parse_mode="Markdown")
    return TITLE

def receive_title(update: Update, context: CallbackContext):
    user_submission[update.effective_user.id] = {"title": update.message.text}
    update.message.reply_text("🎮 Got it! Now enter the *platform* (e.g., PC, PS4):", parse_mode="Markdown")
    return PLATFORM

def receive_platform(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    user_submission[uid]["platform"] = update.message.text
    username = update.effective_user.username or "N/A"
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📥 *New Game Request!*\n"
            f"👤 From: @{username}\n"
            f"🎮 Title: {user_submission[uid]['title']}\n"
            f"🖥️ Platform: {user_submission[uid]['platform']}"
        ),
        parse_mode="Markdown"
    )
    update.message.reply_text("✅ Submitted successfully! Thank you.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Submission canceled.")
    return ConversationHandler.END

# Admin Analytics
def analytics_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("🚫 Unauthorized")
        return
    if not analytics:
        update.message.reply_text("No game views yet.")
        return
    msg = "📊 *Top Viewed Games:*\n"
    top = sorted(analytics.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (title, views) in enumerate(top, 1):
        msg += f"{i}. {title} – {views} views\n"
    update.message.reply_text(msg, parse_mode="Markdown")

# Handlers
def main():
    load_data()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("info", info))
    dp.add_handler(CommandHandler("search", search))
    dp.add_handler(CommandHandler("random", random_game))
    dp.add_handler(CommandHandler("latest", latest))
    dp.add_handler(CommandHandler("analytics", analytics_cmd))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('submit', submit)],
        states={
            TITLE: [MessageHandler(Filters.text & ~Filters.command, receive_title)],
            PLATFORM: [MessageHandler(Filters.text & ~Filters.command, receive_platform)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(conv_handler)

    # Fallbacks for menu
    dp.add_handler(MessageHandler(Filters.regex("🔍 Search"), lambda u, c: u.message.reply_text("Use /search <game title>")))
    dp.add_handler(MessageHandler(Filters.regex("🎲 Random"), random_game))
    dp.add_handler(MessageHandler(Filters.regex("🕒 Latest"), latest))
    dp.add_handler(MessageHandler(Filters.regex("ℹ️ Info"), info))
    dp.add_handler(MessageHandler(Filters.regex("📤 Submit Game"), lambda u, c: submit(u, c)))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
