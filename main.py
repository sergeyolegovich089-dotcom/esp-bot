import logging
import os
import json
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

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# ================= GOOGLE SHEETS =================

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SHEET_ID).sheet1

# ================= ЛОГИ =================

logging.basicConfig(level=logging.INFO)

# ================= КНОПКИ =================

keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск"],
        ["📅 По месяцу"],
    ],
    resize_keyboard=True
)

# ================= КОМАНДА /start =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот готов к работе 👌\nВыбери действие:",
        reply_markup=keyboard
    )

# ================= ПОИСК ПО ФИО =================

async def search_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = sheet.get_all_records()

    found = []

    for row in data:
        fio = str(row.get("ФИО", "")).lower()

        if text in fio:
            found.append(row)

    if not found:
        await update.message.reply_text("❌ Ничего не найдено")
        return

    for row in found[:5]:
        msg = (
            f"👤 {row.get('ФИО','')}\n"
            f"💼 {row.get('Должность','')}\n"
            f"🏙 {row.get('Город','')}\n"
            f"📅 До: {row.get('Дата окончания','')}\n"
            f"📊 {row.get('Статус','')}"
        )
        await update.message.reply_text(msg)

# ================= МЕСЯЦЫ =================

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

# ================= ПОИСК ПО МЕСЯЦУ =================

async def search_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()

    if text not in MONTHS:
        await update.message.reply_text("Напиши месяц (например: июль или 7)")
        return

    month = MONTHS[text]
    data = sheet.get_all_records()

    found = []

    for row in data:
        date_str = str(row.get("Дата окончания", "")).strip()

        if not date_str:
            continue

        date_obj = None

        # поддержка разных форматов даты
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
            try:
                date_obj = datetime.strptime(date_str, fmt)
                break
            except:
                continue

        if not date_obj:
            continue

        if date_obj.month == month:
            found.append(row)

    if not found:
        await update.message.reply_text("❌ Ничего не найдено")
        return

    await update.message.reply_text(f"Найдено: {len(found)}")

    for row in found[:10]:
        msg = (
            f"👤 {row.get('ФИО','')}\n"
            f"📅 До: {row.get('Дата окончания','')}\n"
            f"📊 {row.get('Статус','')}"
        )
        await update.message.reply_text(msg)

# ================= ОБРАБОТКА КНОПОК =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введите ФИО или часть:")
        return

    if text == "📅 По месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введите месяц (например: июль или 7):")
        return

    mode = context.user_data.get("mode")

    if mode == "search":
        await search_name(update, context)
    elif mode == "month":
        await search_month(update, context)
    else:
        await update.message.reply_text("Выбери действие через кнопки 👇")

# ================= ЗАПУСК =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
