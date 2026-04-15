import os
import logging
from datetime import datetime
from difflib import get_close_matches

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

# ================= НАСТРОЙКИ =================
TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_ID"]

logging.basicConfig(level=logging.INFO)

# ================= GOOGLE =================
def get_sheet():
    creds_dict = eval(os.environ["GOOGLE_CREDENTIALS"])

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


# ================= КНОПКИ =================
keyboard = [
    ["🔍 Поиск", "📅 По месяцу"],
    ["📋 Показать всё", "⚡ Проверить сейчас"],
]

markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ================= ВСПОМОГАТЕЛЬНОЕ =================
MONTHS = {
    "январь": 1, "февраль": 2, "март": 3,
    "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9,
    "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return None


def normalize_month(text):
    text = text.lower().strip()

    if text.isdigit():
        return int(text)

    matches = get_close_matches(text, MONTHS.keys(), n=1, cutoff=0.6)
    if matches:
        return MONTHS[matches[0]]

    return None


# ================= КОМАНДЫ =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие 👇", reply_markup=markup)


# ================= ПОКАЗАТЬ ВСЁ =================
async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet()
    data = sheet.get_all_values()

    result = ""
    for row in data[1:]:
        name = row[0]
        date = row[1]

        result += f"👤 {name}\n📅 До: {date}\n\n"

    await update.message.reply_text(result or "Нет данных")


# ================= ПОИСК =================
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "search"
    await update.message.reply_text("Введите имя:")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "search":
        return

    query = update.message.text.lower()

    sheet = get_sheet()
    data = sheet.get_all_values()

    result = ""

    for row in data[1:]:
        name = row[0].lower()
        date = row[1]

        if query in name:
            result += f"👤 {row[0]}\n📅 До: {date}\n\n"

    if not result:
        result = "❌ Ничего не найдено"

    await update.message.reply_text(result)
    context.user_data["mode"] = None


# ================= ПО МЕСЯЦУ =================
async def by_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "month"
    await update.message.reply_text("Введите месяц (например: июль или 7):")


async def handle_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "month":
        return

    month = normalize_month(update.message.text)

    if not month:
        await update.message.reply_text("❌ Не понял месяц")
        return

    sheet = get_sheet()
    data = sheet.get_all_values()

    result = ""

    for row in data[1:]:
        name = row[0]
        date_str = row[1]

        date = parse_date(date_str)
        if not date:
            continue

        if date.month == month:
            result += f"👤 {name}\n📅 До: {date_str}\n\n"

    if not result:
        result = "❌ Ничего не найдено"

    await update.message.reply_text(result)
    context.user_data["mode"] = None


# ================= ПРОВЕРКА =================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet()
    data = sheet.get_all_values()

    today = datetime.now()

    result = ""

    for row in data[1:]:
        name = row[0]
        date_str = row[1]

        date = parse_date(date_str)
        if not date:
            continue

        days_left = (date - today).days

        if days_left in [30, 15, 7] or days_left <= 3:
            result += f"⚠️ {name}\n📅 До: {date_str} (осталось {days_left} дн)\n\n"

    if not result:
        result = "✅ Всё спокойно"

    await update.message.reply_text(result)


# ================= ОБЩИЙ ХЕНДЛЕР =================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Поиск":
        await search(update, context)

    elif text == "📅 По месяцу":
        await by_month(update, context)

    elif text == "📋 Показать всё":
        await show_all(update, context)

    elif text == "⚡ Проверить сейчас":
        await check_now(update, context)

    else:
        await handle_search(update, context)
        await handle_month(update, context)


# ================= ЗАПУСК =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Бот запущен 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
