# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import asyncio

# Ensure parent directory is in sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

import bot
import script_generator
import database

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Build telegram application
tg_app = Application.builder().token(TOKEN).updater(None).build()

tg_app.add_handler(CommandHandler("start", bot.start_command))
tg_app.add_handler(CommandHandler("new", lambda u, c: bot.generate_and_send_new_script(u, c)))
tg_app.add_handler(CommandHandler("history", bot.history_command))
tg_app.add_handler(CommandHandler("reset", bot.reset_command))
tg_app.add_handler(CommandHandler("help", bot.help_command))
tg_app.add_handler(CallbackQueryHandler(bot.handle_callback_query))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        response_html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8"><title>بوت السكريبتات التاريخية</title></head>
<body style="background:#0f172a;color:#fff;font-family:sans-serif;text-align:center;padding:50px;">
  <h1 style="color:#22c55e;">✅ البوت شغال بنجاح على سيرفرات Vercel 24/7!</h1>
  <p>الويب هوك نشط ومستعد لاستقبال الرسائل في أي وقت والجهاز مقفول.</p>
</body>
</html>"""
        self.wfile.write(response_html.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            raw_json = json.loads(body.decode('utf-8'))
            update = Update.de_json(raw_json, tg_app.bot)
            if update:
                async def run_update():
                    async with tg_app:
                        await tg_app.process_update(update)
                asyncio.run(run_update())
        except Exception as e:
            print(f"Error handling update: {e}")

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
