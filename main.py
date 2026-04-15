import logging
import os
import json
from datetime import datetime, time

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

MY_CHAT_ID = 568554255  # 👈 ТВОЙ ID

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
    await update.message.reply_text(
        "Бот работает 👌\nВыбери действие:",
        reply_markup=keyboard
    )

# ================= НАПОМИНАНИЯ =================

async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    data = sheet.get_all_records()
    today = datetime.today()

    for row in data:
        try:
            date_str = str(row.get("Дата окончания", "")).strip()

            date_obj = None
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
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

                await context.bot.send_message(
                    chat_id=MY_CHAT_ID,
                    text=msg
                )

        except:
            continue

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

        date_obj = None
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
        await check_expirations(context)
        await update.message.reply_text("Проверка выполнена ✅")
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

    # ⏰ КАЖДЫЙ ДЕНЬ В 09:00
    app.job_queue.run_daily(
        check_expirations,
        time=time(hour=9, minute=0),
    )

    print("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
