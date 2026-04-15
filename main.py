import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- НАСТРОЙКИ ----------------

TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

logging.basicConfig(level=logging.INFO)

# ---------------- GOOGLE ----------------

def connect_google():
    creds_dict = eval(GOOGLE_CREDENTIALS)

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    return sheet

# ---------------- ДАННЫЕ ----------------

def get_data():
    sheet = connect_google()
    return sheet.get_all_records()

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return None

# ---------------- КНОПКИ ----------------

keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["📋 Показать всё", "⚡ Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери действие 👇",
        reply_markup=keyboard,
    )

# ---------------- ПРОВЕРКА ----------------

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()

    today = datetime.now()
    result = []

    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")

        date = parse_date(date_str)
        if not date:
            continue

        days_left = (date - today).days

        if days_left <= 30:
            result.append(f"⚠️ {name} — {date_str} ({days_left} дн.)")

    if result:
        await update.message.reply_text("\n".join(result))
    else:
        await update.message.reply_text("✅ Всё спокойно")

# ---------------- ПОКАЗАТЬ ВСЁ ----------------

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()

    result = []
    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")
        result.append(f"{name} — {date_str}")

    await update.message.reply_text("\n".join(result[:50]))

# ---------------- ПО МЕСЯЦУ ----------------

months = {
    "январь": 1, "февраль": 2, "март": 3,
    "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9,
    "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}

async def month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text in months:
        month = months[text]
    else:
        try:
            month = int(text)
        except:
            await update.message.reply_text("❌ Неверный месяц")
            return

    data = get_data()
    result = []

    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")
        date = parse_date(date_str)

        if date and date.month == month:
            result.append(f"{name} — {date_str}")

    if result:
        await update.message.reply_text("\n".join(result))
    else:
        await update.message.reply_text("❌ Ничего не найдено")

# ---------------- ОБРАБОТКА ТЕКСТА ----------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⚡ Проверить сейчас":
        await check_now(update, context)

    elif text == "📋 Показать всё":
        await show_all(update, context)

    elif text == "📅 По месяцу":
        await update.message.reply_text("Введи месяц (например: июль или 7)")

    else:
        await month_handler(update, context)

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("✅ BOT STARTED")

    app.run_polling()

if __name__ == "__main__":
    main()
