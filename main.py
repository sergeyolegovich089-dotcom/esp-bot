import logging
import os
import json
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# === НАСТРОЙКИ ===
TOKEN = os.environ["BOT_TOKEN"]  # бери из Railway
SHEET_ID = os.environ["SHEET_URL"]  # тут теперь ТОЛЬКО ID таблицы

# === GOOGLE SHEETS ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

# ❗ ВАЖНО: используем open_by_key вместо open_by_url
sheet = client.open_by_key(SHEET_ID).sheet1

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === КОМАНДА /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает. Используй /find Иванов")

# === КОМАНДА /find ===
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши: /find Иванов")
        return

    name = context.args[0].lower()
    data = sheet.get_all_records()

    for row in data:
        if name in row["ФИО"].lower():
            msg = (
                f"ФИО: {row['ФИО']}\n"
                f"Должность: {row['Должность']}\n"
                f"Город: {row['Город']}\n"
                f"Начало: {row['Дата начала']}\n"
                f"Окончание: {row['Дата окончания']}\n"
                f"Статус: {row['Статус']}"
            )
            await update.message.reply_text(msg)
            return

    await update.message.reply_text("Не найдено")

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
