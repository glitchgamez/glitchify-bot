import os
import random
import requests
from flask import Flask, request
from telegram import Bot, Update, ParseMode
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

TOKEN = os.environ['BOT_TOKEN']
bot = Bot(token=TOKEN)
app = Flask(__name__)

def format_game(game):
    return (
        f"🎮 *{game['title']}*\n"
        f"🏷️ Tags: {', '.join(game['tags'])}\n"
        f"🗓️ Last Updated: {game['modified']}\n"
        f"🔗 [View Game](https://glitchify.space{game['url']})"
    )

def start(update, context):
    update.message.reply_text("👋 Welcome to Glitchify Bot!\n\nUse:\n• `/random`\n• `/latest`\n• Or type a game name!", parse_mode=ParseMode.MARKDOWN)

def random_game(update, context):
    try:
        games = requests.get("https://glitchify.space/search-index.json").json()
        game = random.choice(games)
        update.message.reply_text(format_game(game), parse_mode=ParseMode.MARKDOWN)
    except:
        update.message.reply_text("⚠️ Could not fetch games.")

def latest_games(update, context):
    try:
        games = requests.get("https://glitchify.space/search-index.json").json()
        latest = sorted(games, key=lambda g: g['modified'], reverse=True)[:3]
        for game in latest:
            update.message.reply_text(format_game(game), parse_mode=ParseMode.MARKDOWN)
    except:
        update.message.reply_text("⚠️ Could not fetch latest games.")

def search(update, context):
    query = update.message.text.lower()
    try:
        games = requests.get("https://glitchify.space/search-index.json").json()
    except:
        update.message.reply_text("⚠️ Could not load games.")
        return

    results = [
        g for g in games
        if query in g['title'].lower() or any(query in tag.lower() for tag in g['tags'])
    ]

    if not results:
        update.message.reply_text("❌ No results found.")
        return

    for game in results[:3]:
        update.message.reply_text(format_game(game), parse_mode=ParseMode.MARKDOWN)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp = Dispatcher(bot, None, workers=0)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("random", random_game))
    dp.add_handler(CommandHandler("latest", latest_games))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, search))
    dp.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "✅ Glitchify Bot Running!"

if __name__ == "__main__":
    app.run(port=5000)
