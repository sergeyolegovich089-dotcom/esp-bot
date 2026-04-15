import os
import json
import asyncio
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

print("✅ DAILY VERSION CUSTOM")

TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# ================== GOOGLE ==================
def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def get_data():
    try:
        return get_sheet().get_all_records()
    except Exception as e:
        print("❌ Google:", e)
        return []

# ================== ДАТЫ ==================
def parse_date(date_str):
    if not date_str:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except:
            continue
    return None

# ================== ЛОГИКА ==================
def check_logic():
    data = get_data()
    today = datetime.now()
    result = []

    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")
        extended = str(row.get("Продлено", "")).lower()

        if extended == "да":
            continue

        d = parse_date(date_str)
        if not d:
            continue

        days = (d - today).days

        if days in [30, 16, 7] or days <= 0:
            result.append(f"⚠️ {name} — {date_str} ({days} дн.)")

    return result

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["📋 Показать всё", "⚡ Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.chat_ids.add(update.effective_chat.id)
    await update.message.reply_text("Выбери действие 👇", reply_markup=keyboard)

# ================== РУЧНАЯ ПРОВЕРКА ==================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = check_logic()
    await update.message.reply_text("\n".join(result) or "😎 Олегыч, всё тихо")

# ================== ПЛАНИРОВЩИК ==================
last_result = []
last_check_day = None
last_send_day = None

async def scheduler(app):
    global last_result, last_check_day, last_send_day

    await asyncio.sleep(10)

    while True:
        now = datetime.now()

        if now.hour >= 9 and last_check_day != now.date():
            print("🔍 Проверка после 09:00")
            last_result = check_logic()
            last_check_day = now.date()

        if now.hour >= 11 and last_send_day != now.date():
            print("📨 Отправка после 11:00")

            text = "\n".join(last_result) if last_result else "😎 Олегыч, всё тихо"

            for chat_id in app.chat_ids:
                try:
                    await app.bot.send_message(chat_id, text)
                except Exception as e:
                    print("❌ Ошибка отправки:", e)

            last_send_day = now.date()

        await asyncio.sleep(60)

# ================== ОБРАБОТКА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    context.application.chat_ids.add(update.effective_chat.id)

    # ===== МЕСЯЦ =====
    if context.user_data.get("mode") == "month":
        context.user_data["mode"] = None

        months = {
            "январь":1,"февраль":2,"март":3,"апрель":4,
            "май":5,"июнь":6,"июль":7,"август":8,
            "сентябрь":9,"октябрь":10,"ноябрь":11,"декабрь":12
        }

        month = months.get(text) or (int(text) if text.isdigit() else None)

        if not month:
            await update.message.reply_text("❌ Неверный месяц")
            return

        result = []
        for row in get_data():
            d = parse_date(row.get("Дата окончания", ""))
            if d and d.month == month:
                result.append(f"{row.get('ФИО')} — {row.get('Дата окончания')}")

        await update.message.reply_text("\n".join(result) or "❌ Ничего не найдено")
        return

    # ===== КНОПКИ =====
    if text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        data = get_data()
        res = [f"{r.get('ФИО')} — {r.get('Дата окончания')}" for r in data]
        await update.message.reply_text("\n".join(res[:50]) or "Нет данных")

    elif text == "📅 по месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введи месяц")

    elif text == "🔍 поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введи фамилию или имя")

    else:
        data = get_data()
        result = [
            f"{r.get('ФИО')} — {r.get('Дата окончания')}"
            for r in data
            if text in r.get("ФИО", "").lower()
        ]

        await update.message.reply_text("\n".join(result) or "❌ Ничего не найдено")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.chat_ids = set()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    app.create_task(scheduler(app))

    print("🚀 BOT STARTED CUSTOM MODE")
    app.run_polling()

if __name__ == "__main__":
    main()
