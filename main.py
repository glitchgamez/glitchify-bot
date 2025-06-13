import os
import json
import random
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
bot = Bot(token=TOKEN)

app = Flask(__name__)
dispatcher = Dispatcher(bot, update_queue=None, workers=4, use_context=True)

SEARCH_INDEX_URL = "https://glitchify.space/search-index.json"
GAME_DATA = []

# Load JSON on startup
def load_data():
    global GAME_DATA
    try:
        res = requests.get(SEARCH_INDEX_URL)
        if res.status_code == 200:
            GAME_DATA = res.json()
    except Exception as e:
        print("Failed to load data:", e)

# --- Commands ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Welcome to Glitchify Bot!\nType /help to see available commands.")

def help_command(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🎲 Random", callback_data="random"),
         InlineKeyboardButton("🕑 Latest", callback_data="latest")],
        [InlineKeyboardButton("➕ Request Game", callback_data="request")]
    ]
    update.message.reply_text(
        "*Available Commands:*\n"
        "🔍 `/search <query>` – Search games\n"
        "🎲 `/random` – Get a random game\n"
        "🕑 `/latest` – Show recently added game\n"
        "➕ `/request` – Suggest a new game\n"
        "ℹ️ `/help` – Show this menu",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def search(update: Update, context: CallbackContext):
    query = " ".join(context.args).lower()
    if not query:
        update.message.reply_text("❗ Usage: `/search doom eternal`", parse_mode='Markdown')
        return

    results = [g for g in GAME_DATA if query in g['title'].lower()]
    if not results:
        update.message.reply_text("❌ No games found.")
        return

    for game in results[:5]:
        url = f"https://glitchify.space/{game['url']}"
        thumb = url.replace("game.html", "screenshot1.jpg")
        caption = (
            f"*🎮 {game['title']}*\n"
            f"🏷️ Tags: `{', '.join(game['tags'])}`\n"
            f"[🔗 View Game]({url})"
        )
        try:
            update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")
        except:
            update.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=False)

def random_game(update: Update, context: CallbackContext):
    game = random.choice(GAME_DATA)
    url = f"https://glitchify.space/{game['url']}"
    thumb = url.replace("game.html", "screenshot1.jpg")
    caption = (
        f"*🎮 {game['title']}*\n"
        f"🏷️ Tags: `{', '.join(game['tags'])}`\n"
        f"[🔗 View Game]({url})"
    )
    try:
        update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")
    except:
        update.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=False)

def latest_game(update: Update, context: CallbackContext):
    latest = sorted(GAME_DATA, key=lambda x: x['modified'], reverse=True)[0]
    url = f"https://glitchify.space/{latest['url']}"
    thumb = url.replace("game.html", "screenshot1.jpg")
    caption = (
        f"*🆕 Latest Game:*\n"
        f"*🎮 {latest['title']}*\n"
        f"🏷️ Tags: `{', '.join(latest['tags'])}`\n"
        f"[🔗 View Game]({url})"
    )
    try:
        update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")
    except:
        update.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=False)

# --- Game Request Conversation ---
REQ_TITLE, REQ_PLATFORM = range(2)
user_requests = {}

def request_game(update: Update, context: CallbackContext):
    update.message.reply_text("🎮 What's the title of the game you'd like to request?")
    return REQ_TITLE

def get_title(update: Update, context: CallbackContext):
    context.user_data['request_title'] = update.message.text
    update.message.reply_text("🕹️ What platform is this game for? (PC, PS3, etc)")
    return REQ_PLATFORM

def get_platform(update: Update, context: CallbackContext):
    title = context.user_data['request_title']
    platform = update.message.text
    username = update.message.from_user.username or "NoUsername"
    msg = f"📥 *New Game Request Submitted!*\n\n" \
          f"*Title:* {title}\n" \
          f"*Platform:* {platform}\n" \
          f"*From:* @{username}"
    bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
    update.message.reply_text("✅ Thanks! Your request was sent to the admin.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Request cancelled.")
    return ConversationHandler.END

# --- Flask route for Webhook ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

@app.route("/")
def home():
    return "Glitchify Bot is live!"

# --- Register Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("search", search))
dispatcher.add_handler(CommandHandler("random", random_game))
dispatcher.add_handler(CommandHandler("latest", latest_game))

# Request conversation
request_handler = ConversationHandler(
    entry_points=[CommandHandler("request", request_game)],
    states={
        REQ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
        REQ_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_platform)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
dispatcher.add_handler(request_handler)

# --- Load data once on startup ---
load_data()
