import os
import json
import random
import difflib
from datetime import datetime
from flask import Flask, request
import requests
from fuzzywuzzy import process
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# Load game data
with open("search-index.json", "r") as f:
    GAME_DATA = json.load(f)

analytics = {
    "total_queries": 0,
    "top_queries": {},
    "submissions": []
}

# --- Helper Functions ---
def format_game_result(game):
    title = game["title"]
    url = f"https://glitchify.space/{game['url']}"
    modified = datetime.strptime(game["modified"], "%Y-%m-%dT%H:%M:%S").strftime("%B %d, %Y")
    tags = ", ".join(game["tags"])
    image_url = url.rsplit("/", 1)[0] + "/screenshot1.jpg"

    buttons = [[InlineKeyboardButton("🔗 View Page", url=url)]]
    return title, f"📌 *{title}*\n🏷️ {tags}\n🕓 Last Modified: {modified}", image_url, InlineKeyboardMarkup(buttons)

def search_games(query):
    titles = [game["title"] for game in GAME_DATA]
    matches = process.extract(query, titles, limit=5)
    return [game for game in GAME_DATA if game["title"] in [m[0] for m in matches if m[1] > 60]]

def update_analytics(query):
    analytics["total_queries"] += 1
    analytics["top_queries"][query] = analytics["top_queries"].get(query, 0) + 1

# --- Commands ---
def start(update, context):
    update.message.reply_text("Welcome to Glitchify Bot!")

def info(update, context):
    buttons = [
        [InlineKeyboardButton("/search", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("/random", callback_data="random")],
        [InlineKeyboardButton("/latest", callback_data="latest")],
        [InlineKeyboardButton("/submit", switch_inline_query_current_chat="submit Your Game Title Here")]
    ]
    update.message.reply_text("🎮 Available Commands:", reply_markup=InlineKeyboardMarkup(buttons))

def search(update, context):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("❗ Usage: /search <game name>")
        return

    results = search_games(query)
    update_analytics(query)

    if not results:
        close = difflib.get_close_matches(query, [g["title"] for g in GAME_DATA], n=1)
        if close:
            update.message.reply_text(f"❓ No exact match. Did you mean: /search {close[0]}?")
        else:
            update.message.reply_text("🚫 No results found.")
        return

    for game in results[:5]:
        title, text, img, buttons = format_game_result(game)
        bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, reply_markup=buttons, parse_mode="Markdown")

    if len(results) > 5:
        more_url = f"https://glitchify.space/search-results.html?q={query}"
        update.message.reply_text("🔎 View all results:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View All", url=more_url)]]))

def random_game(update, context):
    game = random.choice(GAME_DATA)
    title, text, img, buttons = format_game_result(game)
    bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, reply_markup=buttons, parse_mode="Markdown")

def latest_game(update, context):
    game = sorted(GAME_DATA, key=lambda g: g["modified"], reverse=True)[0]
    title, text, img, buttons = format_game_result(game)
    bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text, reply_markup=buttons, parse_mode="Markdown")

def analytics_cmd(update, context):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        update.message.reply_text("🚫 Admin only.")
        return

    stats = sorted(analytics["top_queries"].items(), key=lambda x: x[1], reverse=True)[:5]
    message = f"📊 Total Queries: {analytics['total_queries']}\n\n🔝 Top Searches:\n"
    for q, c in stats:
        message += f"• {q} ({c})\n"

    if analytics["submissions"]:
        message += f"\n📤 Submissions:\n" + "\n".join(f"- @{u}: {s}" for u, s in analytics["submissions"])

    update.message.reply_text(message)

def submit(update, context):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("❗ Usage: /submit <game title>")
        return

    username = update.effective_user.username or f"id:{update.effective_user.id}"
    analytics["submissions"].append((username, query))

    bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📥 New Submission from @{username}:\n{query}")
    update.message.reply_text("✅ Thanks! We've received your game suggestion.")

# --- Register Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("info", info))
dispatcher.add_handler(CommandHandler("search", search))
dispatcher.add_handler(CommandHandler("random", random_game))
dispatcher.add_handler(CommandHandler("latest", latest_game))
dispatcher.add_handler(CommandHandler("analytics", analytics_cmd))
dispatcher.add_handler(CommandHandler("submit", submit))

# --- Webhook endpoint for Render ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    dispatcher.process_update(telegram.Update.de_json(update, bot))
    return "OK"

@app.route("/", methods=["GET"])
def root():
    return "Bot is running!"

if __name__ == "__main__":
    bot.set_webhook(f"https://<your-render-service>.onrender.com/{TOKEN}")
