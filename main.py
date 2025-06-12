import os
import json
import logging
import random
import difflib
import datetime
from flask import Flask, request
from fuzzywuzzy import process
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = os.environ['ADMIN_ID']  # numeric ID as string
bot = Bot(token=TOKEN)

app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# Load game index from the static URL
import requests
INDEX_URL = 'https://glitchify.space/search-index.json'
game_index = []

def load_games():
    global game_index
    res = requests.get(INDEX_URL)
    if res.ok:
        game_index = res.json()

load_games()

# Analytics log
analytics = []

# === COMMAND HANDLERS ===

def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🎲 Random", callback_data='random')],
        [InlineKeyboardButton("🕒 Latest", callback_data='latest')],
        [InlineKeyboardButton("ℹ️ Info", callback_data='info')],
    ]
    update.message.reply_text("🎮 *Welcome to Glitchify Bot!*", parse_mode=ParseMode.MARKDOWN,
                              reply_markup=InlineKeyboardMarkup(keyboard))

def info(update: Update, context: CallbackContext):
    text = (
        "📖 *Available Commands:*\n\n"
        "`/search <query>` – Search games\n"
        "`/random` – Show a random game\n"
        "`/latest` – Most recently added game\n"
        "`/submit <title> | <desc> | <tags>` – Suggest a new game\n"
        "`/info` – Show this help message\n"
    )
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

def search(update: Update, context: CallbackContext):
    query = ' '.join(context.args).strip().lower()
    if not query:
        update.message.reply_text("❌ Please type a search query.\nExample: `/search assassin creed`", parse_mode=ParseMode.MARKDOWN)
        return

    analytics.append(f"🔍 {update.effective_user.username or update.effective_user.id}: {query}")
    
    titles = [game['title'] for game in game_index]
    matches = process.extract(query, titles, limit=5)

    if not matches:
        update.message.reply_text("🚫 No games found.")
        return

    for match, score in matches:
        game = next(g for g in game_index if g['title'] == match)
        send_game_result(update, game)

    update.message.reply_text("👉 [View all results](https://glitchify.space/search-results.html?q={})".format(query),
                              parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

def random_game(update: Update, context: CallbackContext):
    game = random.choice(game_index)
    send_game_result(update, game)

def latest_game(update: Update, context: CallbackContext):
    latest = sorted(game_index, key=lambda g: g['modified'], reverse=True)[0]
    send_game_result(update, latest)

def submit(update: Update, context: CallbackContext):
    text = ' '.join(context.args)
    if "|" not in text:
        update.message.reply_text("❗ Use the format: `/submit Game Title | Description | tag1, tag2`", parse_mode=ParseMode.MARKDOWN)
        return

    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        update.message.reply_text("❗ Please include all fields: title, desc, tags.")
        return

    username = update.effective_user.username or "Unknown"
    submission = f"📥 *New Game Submission:*\n\n👤 User: @{username}\n\n🎮 Title: {parts[0]}\n📝 Desc: {parts[1]}\n🏷️ Tags: {parts[2]}"
    bot.send_message(chat_id=int(ADMIN_ID), text=submission, parse_mode=ParseMode.MARKDOWN)
    update.message.reply_text("✅ Thanks! Your suggestion was sent to admin.")

def send_game_result(update, game):
    url = f"https://glitchify.space/{game['url']}"
    thumb = url.replace("game.html", "screenshot1.jpg")

    buttons = [
        [InlineKeyboardButton("▶️ View Game Page", url=url)]
    ]

    caption = f"*{game['title']}*\n🏷️ Tags: {', '.join(game['tags'])}\n🕓 Modified: {game['modified']}"
    bot.send_photo(chat_id=update.effective_chat.id, photo=thumb, caption=caption,
                   parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(buttons))

def admin_log(update: Update, context: CallbackContext):
    if str(update.effective_user.id) != ADMIN_ID:
        update.message.reply_text("🚫 Not allowed.")
        return
    text = "\n".join(analytics[-20:]) or "No analytics yet."
    update.message.reply_text(f"📊 *Recent Searches:*\n\n{text}", parse_mode=ParseMode.MARKDOWN)

# === ROUTING ===

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("info", info))
dispatcher.add_handler(CommandHandler("search", search))
dispatcher.add_handler(CommandHandler("random", random_game))
dispatcher.add_handler(CommandHandler("latest", latest_game))
dispatcher.add_handler(CommandHandler("submit", submit))
dispatcher.add_handler(CommandHandler("analytics", admin_log))

# === FLASK HOOK ===

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'OK'

@app.route('/')
def index():
    return 'Glitchify Bot is running.'

# === MAIN ===

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
