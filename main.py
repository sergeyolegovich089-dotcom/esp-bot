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
    filters,
    ContextTypes,
)

import gspread
from google.oauth2.service_account import Credentials

# =========================
# 🔐 НАСТРОЙКИ
# =========================

TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_URL"]

# =========================
# 📊 GOOGLE SHEETS
# =========================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SHEET_ID).sheet1

# =========================
# 🧠 ЛОГИ
# =========================

logging.basicConfig(level=logging.INFO)

# =========================
# 📌 СОСТОЯНИЯ
# =========================

user_states = {}

# =========================
# 🎛 КНОПКИ
# =========================

keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Найти сотрудника"],
        ["📅 По месяцу"],
        ["ℹ️ Помощь"],
    ],
    resize_keyboard=True
)

# =========================
# 🚀 КОМАНДЫ
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Функции:\n"
        "🔍 Найти сотрудника — поиск по ФИО\n"
        "📅 По месяцу — кто заканчивается в выбранном месяце"
    )

# =========================
# 🔘 ОБРАБОТКА
# =========================

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # === КНОПКИ ===
    if text == "🔍 Найти сотрудника":
        user_states[user_id] = "waiting_name"
        await update.message.reply_text("Введите ФИО или часть:")
        return

    if text == "📅 По месяцу":
        user_states[user_id] = "waiting_month"
        await update.message.reply_text("Введите месяц (например: июль или 7):")
        return

    if text == "ℹ️ Помощь":
        await help_command(update, context)
        return

    # =========================
    # 🔍 ПОИСК ПО ФИО
    # =========================

    if user_states.get(user_id) == "waiting_name":
        user_states[user_id] = None

        query = text.lower()
        data = sheet.get_all_records()

        results = []

        for row in data:
            fio = str(row.get("ФИО", "")).lower()

            if query in fio:
                results.append((row, 1.0))
                continue

            matches = get_close_matches(query, fio.split(), n=1, cutoff=0.6)
            if matches:
                results.append((row, 0.7))

        results.sort(key=lambda x: x[1], reverse=True)

        if not results:
            await update.message.reply_text("❌ Ничего не найдено")
            return

        for row, _ in results[:5]:
            msg = (
                f"👤 <b>{row.get('ФИО','-')}</b>\n"
                f"🏢 {row.get('Должность','-')}\n"
                f"🌍 {row.get('Город','-')}\n"
                f"📅 {row.get('Дата начала','-')} → {row.get('Дата окончания','-')}\n"
                f"📊 {row.get('Статус','-')}\n"
                "---------------------"
            )
            await update.message.reply_text(msg, parse_mode="HTML")

        return

    # =========================
    # 📅 ПО МЕСЯЦУ (FIX ПОД ТЕБЯ)
    # =========================

    if user_states.get(user_id) == "waiting_month":
        user_states[user_id] = None

        month_input = text.lower()

        months = {
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

        if month_input not in months:
            await update.message.reply_text("❌ Неверный месяц")
            return

        target_month = months[month_input]
        data = sheet.get_all_records()
        results = []

        for row in data:
            try:
                date_str = row.get("Дата окончания", "")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")  # 👈 ВАЖНО

                if date_obj.month == target_month:
                    results.append(row)
            except:
                continue

        if not results:
            await update.message.reply_text("❌ Ничего не найдено")
            return

        for row in results:
            msg = (
                f"👤 {row.get('ФИО','-')}\n"
                f"📅 До: {row.get('Дата окончания','-')}\n"
                f"📊 {row.get('Статус','-')}\n"
                "---------------------"
            )
            await update.message.reply_text(msg)

        return

    # =========================
    # ❓ ЕСЛИ НЕ ПОНЯЛ
    # =========================

    await update.message.reply_text("Выбери действие через кнопки 👇", reply_markup=keyboard)

# =========================
# 🏁 ЗАПУСК
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
