import os
import json
import random
import difflib
import requests
from flask import Flask, request
import telegram
from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

bot = telegram.Bot(token=BOT_TOKEN)
app = Flask(__name__)

# Load search-index.json from Glitchify site
response = requests.get("https://glitchify.space/search-index.json")
GAME_DATA = response.json()

dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)

# --- Command Handlers ---

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🎮 Welcome to Glitchify Bot!\nType /search <title>, /random, /latest or /request to suggest a game.")

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("📜 Commands:\n"
                              "/search <keywords> – Find a game\n"
                              "/random – Get a random game\n"
                              "/latest – Show recently modified games\n"
                              "/request – Suggest a new game")

def search(update: Update, context: CallbackContext):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("❗ Please enter a search term. Example: `/search doom`", parse_mode='Markdown')
        return

    titles = [item["title"] for item in GAME_DATA]
    matches = difflib.get_close_matches(query, titles, n=5, cutoff=0.3)

    if not matches:
        update.message.reply_text("❌ No games found.")
        return

    results = [next(item for item in GAME_DATA if item["title"] == match) for match in matches]
    for game in results:
        url = f"https://glitchify.space/{game['url']}"
        thumb = url.replace("game.html", "screenshot1.jpg")
        caption = f"*{game['title']}*\nTags: {', '.join(game['tags'])}\n[🔗 View Game]({url})"
        update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")

def random_game(update: Update, context: CallbackContext):
    game = random.choice(GAME_DATA)
    url = f"https://glitchify.space/{game['url']}"
    thumb = url.replace("game.html", "screenshot1.jpg")
    caption = f"*{game['title']}*\nTags: {', '.join(game['tags'])}\n[🔗 View Game]({url})"
    update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")

def latest(update: Update, context: CallbackContext):
    latest_games = sorted(GAME_DATA, key=lambda x: x["modified"], reverse=True)[:5]
    for game in latest_games:
        url = f"https://glitchify.space/{game['url']}"
        thumb = url.replace("game.html", "screenshot1.jpg")
        caption = f"*{game['title']}*\nTags: {', '.join(game['tags'])}\n[🔗 View Game]({url})"
        update.message.reply_photo(photo=thumb, caption=caption, parse_mode="Markdown")

# --- Request Submission Flow ---

user_requests = {}

def request_game(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_requests[user_id] = {"step": "title"}
    update.message.reply_text("🎮 What game would you like to request? Please enter the *title*.", parse_mode="Markdown")

def handle_request_flow(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in user_requests:
        return

    step = user_requests[user_id]["step"]
    if step == "title":
        user_requests[user_id]["title"] = update.message.text
        user_requests[user_id]["step"] = "platform"
        update.message.reply_text("🖥️ Great! Now enter the *platform* (e.g., PC, PS3, etc.).", parse_mode="Markdown")
    elif step == "platform":
        title = user_requests[user_id].get("title")
        platform = update.message.text
        username = update.message.from_user.username or "N/A"
        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🆕 Game Request from @{username}:\n\n🎮 *{title}*\n🖥️ Platform: *{platform}*",
            parse_mode="Markdown"
        )
        update.message.reply_text("✅ Your request has been sent. Thank you!")
        del user_requests[user_id]

# --- Dispatcher Bindings ---

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("search", search))
dispatcher.add_handler(CommandHandler("random", random_game))
dispatcher.add_handler(CommandHandler("latest", latest))
dispatcher.add_handler(CommandHandler("request", request_game))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_request_flow))

# --- Webhook Endpoint ---

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Glitchify Bot is live."

# --- Run Flask + Register Webhook ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    url = os.environ.get("WEBHOOK_URL")
    if url:
        webhook_url = f"{url}/{BOT_TOKEN}"
        bot.set_webhook(webhook_url)
        print("🚀 Webhook set to:", webhook_url)
    app.run(host="0.0.0.0", port=port)
