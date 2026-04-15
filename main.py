import logging
import os
import json
import asyncio
from datetime import datetime

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

# ================= НАСТРОЙКИ =================

TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_ID"]

MY_CHAT_ID = 568554255

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# ================= GOOGLE =================

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

logging.basicConfig(level=logging.INFO)

# ================= КНОПКИ =================

keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск"],
        ["📅 По месяцу"],
        ["📢 Проверить сейчас"],
    ],
    resize_keyboard=True
)

# ================= СТАРТ =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает 👌", reply_markup=keyboard)

# ================= НАПОМИНАНИЯ =================

async def check_expirations_once():
    data = sheet.get_all_records()
    today = datetime.today()

    for row in data:
        try:
            date_str = str(row.get("Дата окончания", "")).strip()

            date_obj = None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue

            if not date_obj:
                continue

            days_left = (date_obj - today).days

            if days_left in [30, 15, 7] or days_left <= 0:
                msg = (
                    f"⚠️ Срок заканчивается!\n\n"
                    f"👤 {row.get('ФИО')}\n"
                    f"📅 До: {date_str}\n"
                    f"⏳ Осталось: {days_left} дней"
                )

                app.bot.send_message(chat_id=MY_CHAT_ID, text=msg)

        except:
            continue

# 🔁 ФОНОВЫЙ ЦИКЛ
async def background_checker():
    while True:
        await check_expirations_once()
        await asyncio.sleep(3600)  # раз в час

# ================= ПОИСК =================

async def search_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = sheet.get_all_records()

    found = [r for r in data if text in str(r.get("ФИО", "")).lower()]

    if not found:
        await update.message.reply_text("❌ Ничего не найдено")
        return

    for row in found[:5]:
        await update.message.reply_text(
            f"{row.get('ФИО')}\nДо: {row.get('Дата окончания')}"
        )

# ================= МЕСЯЦ =================

MONTHS = {
    "1": 1, "январь": 1,
    "2": 2, "февраль": 2,
    "3": 3, "март": 3,
    "4": 4, "апрель": 4,
    "5": 5, "май": 5,
    "6": 6, "июнь": 6,
    "7": 7, "июль": 7,
    "8": 8, "август": 8,
    "9": 9, "сентябрь": 9,
    "10": 10, "октябрь": 10,
    "11": 11, "ноябрь": 11,
    "12": 12, "декабрь": 12,
}

async def search_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()

    if text not in MONTHS:
        await update.message.reply_text("Введите месяц (например: июль или 7)")
        return

    month = MONTHS[text]
    data = sheet.get_all_records()

    found = []

    for row in data:
        try:
            date_obj = datetime.strptime(row["Дата окончания"], "%Y-%m-%d")
            if date_obj.month == month:
                found.append(row)
        except:
            continue

    if not found:
        await update.message.reply_text("❌ Ничего не найдено")
        return

    for row in found[:10]:
        await update.message.reply_text(
            f"{row['ФИО']}\nДо: {row['Дата окончания']}"
        )

# ================= ОБРАБОТКА =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введите ФИО:")
        return

    if text == "📅 По месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введите месяц:")
        return

    if text == "📢 Проверить сейчас":
        await check_expirations_once()
        await update.message.reply_text("Проверка выполнена ✅")
        return

    mode = context.user_data.get("mode")

    if mode == "search":
        await search_name(update, context)
    elif mode == "month":
        await search_month(update, context)

# ================= ЗАПУСК =================

def main():
    global app
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 🚀 запускаем фон
    app.create_task(background_checker())

    print("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
