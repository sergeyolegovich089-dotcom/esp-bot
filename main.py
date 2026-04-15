import logging
import os
import json
from datetime import datetime
from difflib import get_close_matches

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials

# === ПЕРЕМЕННЫЕ ===
TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_ID"]

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
        ["🔍 Поиск"],
        ["📅 По месяцу"],
    ],
    resize_keyboard=True,
)

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Выбери действие 👇",
        reply_markup=keyboard
    )

# === ПОИСК ПО ФИО ===
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.lower()
    data = sheet.get_all_records()

    results = []

    for row in data:
        fio = row.get("ФИО", "").lower()
        if name in fio:
            results.append(row)

    # если ничего не нашли — пробуем похожие
    if not results:
        all_names = [row.get("ФИО", "") for row in data]
        matches = get_close_matches(name, all_names, n=3, cutoff=0.5)

        if matches:
            await update.message.reply_text(
                "Возможно ты имел в виду:\n" + "\n".join(matches)
            )
            return

        await update.message.reply_text("❌ Ничего не найдено")
        return

    # вывод результатов
    for row in results[:5]:
        msg = (
            f"👤 {row.get('ФИО')}\n"
            f"🏢 {row.get('Должность')}\n"
            f"📍 {row.get('Город')}\n"
            f"📅 До: {row.get('Дата окончания')}\n"
            f"📊 Статус: {row.get('Статус')}"
        )
        await update.message.reply_text(msg)

# === ПОИСК ПО МЕСЯЦУ ===
async def find_by_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    months = {
        "январь": 1, "февраль": 2, "март": 3,
        "апрель": 4, "май": 5, "июнь": 6,
        "июль": 7, "август": 8, "сентябрь": 9,
        "октябрь": 10, "ноябрь": 11, "декабрь": 12
    }

    # определяем месяц
    if text.isdigit():
        month = int(text)
    else:
        month = months.get(text)

    if not month:
        await update.message.reply_text("❌ Введи месяц (например: июль или 7)")
        return

    data = sheet.get_all_records()
    results = []

    for row in data:
        date_str = row.get("Дата окончания")

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date.month == month:
                results.append(row)
        except:
            continue

    if not results:
        await update.message.reply_text("❌ Ничего не найдено")
        return

    msg = "📅 Найдено:\n\n"

    for row in results[:10]:
        msg += f"{row.get('ФИО')} — {row.get('Дата окончания')}\n"

    await update.message.reply_text(msg)

# === ОБРАБОТКА КНОПОК ===
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Поиск":
        await update.message.reply_text("Введите ФИО:")
        context.user_data["mode"] = "search"

    elif text == "📅 По месяцу":
        await update.message.reply_text("Введите месяц (например: июль или 7):")
        context.user_data["mode"] = "month"

    else:
        mode = context.user_data.get("mode")

        if mode == "search":
            await find(update, context)
        elif mode == "month":
            await find_by_month(update, context)
        else:
            await update.message.reply_text("Выбери действие через кнопки 👇", reply_markup=keyboard)

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
