import logging
import os
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import gspread
from google.oauth2.service_account import Credentials

# === ПЕРЕМЕННЫЕ ===
TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_URL"]

# === GOOGLE SHEETS ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SHEET_ID).sheet1

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === КНОПКИ ===
keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Найти сотрудника"],
        ["ℹ️ Помощь"],
    ],
    resize_keyboard=True
)

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=keyboard
    )

# === ПОМОЩЬ ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Просто нажми «Найти сотрудника» и введи фамилию"
    )

# === ОБРАБОТКА КНОПОК ===
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Найти сотрудника":
        await update.message.reply_text("Введите фамилию:")
        return

    if text == "ℹ️ Помощь":
        await help_command(update, context)
        return

    # === ПОИСК ===
    name = text.lower()
    data = sheet.get_all_records()

    for row in data:
        if name in row["ФИО"].lower():
            msg = (
                f"👤 <b>{row['ФИО']}</b>\n\n"
                f"🏢 Должность: {row['Должность']}\n"
                f"🌍 Город: {row['Город']}\n"
                f"📅 Начало: {row['Дата начала']}\n"
                f"📅 Окончание: {row['Дата окончания']}\n"
                f"📊 Статус: {row['Статус']}"
            )

            await update.message.reply_text(msg, parse_mode="HTML")
            return

    await update.message.reply_text("❌ Ничего не найдено")

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
