import os
import random
import json
import datetime
import difflib
import requests
from flask import Flask, request, abort, render_template_string
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler, ConversationHandler
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

app = Flask(__name__)
analytics = {}
submissions = []
user_submissions = {}

JSON_URL = "https://glitchify.space/search-index.json"
search_data = requests.get(JSON_URL).json()

# ========== UTILITIES ==========

def fuzzy_search(query, limit=5):
    titles = [item['title'] for item in search_data]
    matches = difflib.get_close_matches(query, titles, n=limit, cutoff=0.3)
    return [item for item in search_data if item['title'] in matches]

def format_game(item):
    url = f"https://glitchify.space/{item['url']}"
    thumb = url.replace("game.html", "screenshot1.jpg")
    text = f"🎮 <b>{item['title']}</b>\n🏷️ {' | '.join(item['tags'])}\n🕓 {item['modified']}\n🔗 <a href='{url}'>View Game</a>"
    return text, thumb

def track_command(cmd):
    analytics[cmd] = analytics.get(cmd, 0) + 1

# ========== COMMAND HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_command("start")
    menu = [[
        InlineKeyboardButton("🔍 Search", callback_data="search"),
        InlineKeyboardButton("🎲 Random", callback_data="random")
    ], [
        InlineKeyboardButton("🆕 Latest", callback_data="latest"),
        InlineKeyboardButton("📤 Submit Game", callback_data="submit")
    ], [
        InlineKeyboardButton("ℹ️ Info", callback_data="info")
    ]]
    await update.message.reply_text("Welcome to Glitchify Bot! Choose an option:", reply_markup=InlineKeyboardMarkup(menu))

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_command("info")
    await update.message.reply_text(
        "Available commands:\n"
        "/search <title>\n"
        "/random\n"
        "/latest\n"
        "/submit\n"
        "/info"
    )

async def random_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_command("random")
    game = random.choice(search_data)
    text, thumb = format_game(game)
    await update.message.reply_photo(photo=thumb, caption=text, parse_mode="HTML")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_command("latest")
    sorted_data = sorted(search_data, key=lambda x: x['modified'], reverse=True)[:5]
    for game in sorted_data:
        text, thumb = format_game(game)
        await update.message.reply_photo(photo=thumb, caption=text, parse_mode="HTML")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_command("search")
    if not context.args:
        await update.message.reply_text("Usage: /search <game name>")
        return
    query = " ".join(context.args)
    results = fuzzy_search(query)
    if not results:
        await update.message.reply_text("No matches found.")
        return
    for game in results:
        text, thumb = format_game(game)
        await update.message.reply_photo(photo=thumb, caption=text, parse_mode="HTML")
    if len(results) == 5:
        await update.message.reply_text(f"More: https://glitchify.space/search-results.html?q={query}")

# ========== CALLBACK MENU ==========

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "search":
        await query.edit_message_text("Use /search <game name>")
    elif query.data == "random":
        await random_game(query, context)
    elif query.data == "latest":
        await latest(query, context)
    elif query.data == "submit":
        await submit_command(query, context)
    elif query.data == "info":
        await info(query, context)

# ========== SUBMISSION FLOW ==========

TITLE, PLATFORM = range(2)

async def submit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.from_user.id, text="Let's submit a game!\nSend the game title:")
    return TITLE

async def submission_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or "unknown"
    user_submissions[user] = {'title': update.message.text}
    await update.message.reply_text("Now send the platform (e.g., PC, PS4, etc.):")
    return PLATFORM

async def submission_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or "unknown"
    summary = user_submissions[user]
    summary['platform'] = update.message.text
    summary['user'] = user
    summary['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    submissions.append(summary)
    del user_submissions[user]
    await update.message.reply_text("✅ Game submitted! Thank you.")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📤 New Submission:\nTitle: {summary['title']}\nPlatform: {summary['platform']}\nFrom: @{user}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Submission cancelled.")
    return ConversationHandler.END

# ========== ADMIN PAGE ==========

@app.route("/submissions")
def live_page():
    if request.args.get("admin") != str(ADMIN_ID):
        abort(403)
    html = """
    <html><head><title>Submissions</title><style>
    body { background: #111; color: #eee; font-family: sans-serif; padding: 2em; }
    h1 { color: #0f0; }
    .card { background: #222; padding: 1em; margin: 1em 0; border-left: 4px solid #0f0; }
    .user { font-size: 0.9em; color: #ccc; }
    </style></head><body>
    <h1>📥 Game Submissions</h1>
    {% for s in submissions %}
    <div class="card">
        <b>{{ s.title }}</b> ({{ s.platform }})<br>
        <div class="user">Submitted by @{{ s.user }} – {{ s.time }}</div>
    </div>
    {% endfor %}
    </body></html>
    """
    return render_template_string(html, submissions=reversed(submissions))

# ========== INIT & STARTUP ==========

if __name__ == "__main__":
    from telegram.ext import PicklePersistence
    from threading import Thread

    app_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=8080))
    app_thread.start()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("submit", submit_command)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, submission_title)],
            PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, submission_platform)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("random", random_game))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CallbackQueryHandler(menu_handler))

    application.run_polling()
