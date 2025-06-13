import os
import json
import logging
import random
import urllib.request
from datetime import datetime
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from difflib import get_close_matches

# --- Environment variables ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-app-name.onrender.com
PORT = int(os.getenv("PORT", "10000"))

# --- Setup ---
bot = Bot(BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)
logging.basicConfig(level=logging.INFO)

# --- Load game index ---
def load_games():
    with urllib.request.urlopen("https://glitchify.space/search-index.json") as response:
        return json.loads(response.read().decode())

GAMES = load_games()

# --- Helpers ---
def send_game_info(update, game):
    title = game["title"]
    tags = ' | '.join(game.get("tags", []))
    date = datetime.fromisoformat(game["modified"]).strftime('%b %d, %Y')
    url = f"https://glitchify.space/{game['url']}"
    image = url.replace("game.html", "screenshot1.jpg")

    caption = f"*{title}*\n🏷️ {tags}\n🕒 {date}"
    buttons = [[InlineKeyboardButton("🔗 Open Game Page", url=url)]]

    bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- Command Handlers ---
def start(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("🕒 Latest")],
        [KeyboardButton("📤 Request Game"), KeyboardButton("ℹ️ Help")]
    ]
    update.message.reply_text(
        "🎮 *Welcome to Glitchify Bot!*\nType a game name or use the menu:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "ℹ️ *Help*\n"
        "`🎲 Random` - Get a random game\n"
        "`🕒 Latest` - Show the latest added game\n"
        "`📤 Request Game` - Submit a game request\n"
        "Just type a game name to search.",
        parse_mode="Markdown"
    )

def random_game(update: Update, context: CallbackContext):
    send_game_info(update, random.choice(GAMES))

def latest_game(update: Update, context: CallbackContext):
    latest = sorted(GAMES, key=lambda g: g["modified"], reverse=True)[0]
    send_game_info(update, latest)

# --- Fuzzy Search ---
def handle_search(update: Update, context: CallbackContext):
    text = update.message.text.lower().strip()

    if text in ["🎲 random", "/random"]:
        return random_game(update, context)
    if text in ["🕒 latest", "/latest"]:
        return latest_game(update, context)
    if text in ["📤 request game", "/request"]:
        return request_start(update, context)
    if text in ["ℹ️ help", "/help"]:
        return help_cmd(update, context)

    matches = get_close_matches(text, [g["title"].lower() for g in GAMES], n=5, cutoff=0.4)
    results = [g for g in GAMES if g["title"].lower() in matches]

    if not results:
        update.message.reply_text("❌ No matching games found.")
        return

    for game in results:
        send_game_info(update, game)

    update.message.reply_text(
        f"🔎 [View all results](https://glitchify.space/search-results.html?q={text})",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# --- Request Game Flow ---
REQUEST_TITLE, REQUEST_PLATFORM = range(2)

def request_start(update: Update, context: CallbackContext):
    update.message.reply_text("🎮 What game do you want to request?")
    return REQUEST_TITLE

def request_title(update: Update, context: CallbackContext):
    context.user_data["title"] = update.message.text
    update.message.reply_text("🖥️ What platform is it for?")
    return REQUEST_PLATFORM

def request_platform(update: Update, context: CallbackContext):
    title = context.user_data["title"]
    platform = update.message.text
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "No username"

    msg = f"📤 *New Game Request*\n👤 {username}\n🎮 {title}\n🖥️ {platform}"
    update.message.reply_text("✅ Request submitted!")

    if ADMIN_ID:
        bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# --- Dispatcher Setup ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_cmd))
dispatcher.add_handler(CommandHandler("random", random_game))
dispatcher.add_handler(CommandHandler("latest", latest_game))

request_conv = ConversationHandler(
    entry_points=[CommandHandler("request", request_start)],
    states={
        REQUEST_TITLE: [MessageHandler(Filters.text & ~Filters.command, request_title)],
        REQUEST_PLATFORM: [MessageHandler(Filters.text & ~Filters.command, request_platform)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
dispatcher.add_handler(request_conv)
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_search))

# --- Webhook Routes ---
@app.route('/webhook', methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.before_first_request
def setup_webhook():
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
