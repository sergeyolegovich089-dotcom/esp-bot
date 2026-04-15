import logging
import os
import json
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials

# === ПЕРЕМЕННЫЕ ===
TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_URL"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SHEET_ID).sheet1

logging.basicConfig(level=logging.INFO)

# === КНОПКИ ===
keyboard = ReplyKeyboardMarkup(
    [
        ["📅 Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот следит за сроками ЭЦП 👇",
        reply_markup=keyboard,
    )

# === ПРОВЕРКА ===
async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    data = sheet.get_all_records()
    today = datetime.today()

    for i, row in enumerate(data, start=2):
        try:
            if row.get("Продлено") == "да":
                continue

            end_date = datetime.strptime(row["Дата окончания"], "%Y-%m-%d")
            days_left = (end_date - today).days

            if days_left in [30, 15, 7] or days_left <= 3:
                msg = (
                    f"⚠️ Срок заканчивается!\n\n"
                    f"👤 {row['ФИО']}\n"
                    f"📅 До: {row['Дата окончания']}\n"
                    f"⏳ Осталось: {days_left} дней"
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Продлена",
                                callback_data=f"done_{i}"
                            )
                        ]
                    ]
                )

                await context.bot.send_message(
                    chat_id=context.job.chat_id,
                    text=msg,
                    reply_markup=keyboard,
                )

        except:
            continue

# === КНОПКА ПРОДЛЕНО ===
async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    row_index = int(query.data.split("_")[1])

    sheet.update_cell(row_index, 6, "да")  # 6 = столбец "Продлено"

    await query.edit_message_text("✅ Отмечено как продлено")

# === РУЧНАЯ ПРОВЕРКА ===
async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Проверяю...")

    context.job = type("obj", (object,), {"chat_id": update.effective_chat.id})
    await check_expirations(context)

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, manual_check))
    app.add_handler(CallbackQueryHandler(mark_done))

    # === АВТОПРОВЕРКА КАЖДЫЙ ДЕНЬ ===
    app.job_queue.run_daily(
        check_expirations,
        time=datetime.strptime("09:00", "%H:%M").time(),
        chat_id=YOUR_CHAT_ID  # 👈 сюда вставь свой Telegram ID
    )

    print("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
