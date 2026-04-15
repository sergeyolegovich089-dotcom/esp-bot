import logging
import os
import json
from datetime import datetime
from difflib import get_close_matches

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials

# === ПЕРЕМЕННЫЕ ИЗ RAILWAY ===
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
        ["🔍 Поиск по ФИО"],
        ["📅 По месяцу"],
    ],
    resize_keyboard=True,
)

# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери действие 👇",
        reply_markup=keyboard
    )

# === УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text == "🔍 поиск по фио":
        context.user_data["mode"] = "name"
        await update.message.reply_text("Введи фамилию")

    elif text == "📅 по месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введите месяц (например: июль или 7)")

    else:
        mode = context.user_data.get("mode")

        if mode == "name":
            await search_by_name(update, text)

        elif mode == "month":
            await search_by_month(update, text)

        else:
            await update.message.reply_text("Выбери действие через кнопки 👇")

# === ПОИСК ПО ФИО (УЛУЧШЕННЫЙ) ===
async def search_by_name(update, query):
    data = sheet.get_all_records()
    names = [row["ФИО"] for row in data]

    matches = get_close_matches(query, names, n=5, cutoff=0.5)

    for row in data:
        if query in row["ФИО"].lower() or row["ФИО"] in matches:
            msg = (
                f"👤 {row['ФИО']}\n"
                f"🏢 {row['Должность']}\n"
                f"📍 {row['Город']}\n"
                f"📅 Начало: {row['Дата начала']}\n"
                f"📅 Окончание: {row['Дата окончания']}\n"
                f"📊 Статус: {row['Статус']}"
            )
            await update.message.reply_text(msg)
            return

    await update.message.reply_text("❌ Ничего не найдено")

# === ПОИСК ПО МЕСЯЦУ (ИСПРАВЛЕННЫЙ) ===
async def search_by_month(update, query):
    months = {
        "январь": 1, "февраль": 2, "март": 3,
        "апрель": 4, "май": 5, "июнь": 6,
        "июль": 7, "август": 8, "сентябрь": 9,
        "октябрь": 10, "ноябрь": 11, "декабрь": 12
    }

    # Определяем месяц
    if query.isdigit():
        month = int(query)
    else:
        month = months.get(query)

    if not month:
        await update.message.reply_text("❌ Неверный месяц")
        return

    data = sheet.get_all_records()
    results = []

    for row in data:
        try:
            date_str = row["Дата окончания"]

            # 👉 ВАЖНО: правильный парсинг твоего формата
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            if date_obj.month == month:
                results.append(
                    f"{row['ФИО']} — до {date_str}"
                )

        except Exception as e:
            continue

    if results:
        await update.message.reply_text(
            "📅 Найдено:\n\n" + "\n".join(results[:20])
        )
    else:
        await update.message.reply_text("❌ Ничего не найдено")

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
