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

print("✅ FINAL STABLE VERSION")

TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# ================== GOOGLE ==================
def get_sheet():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDENTIALS),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds).open_by_key(SHEET_ID).sheet1

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

        if days == 0:
            msg = f"⚠️ СЕГОДНЯ: {name} — {date_str}"
        elif days < 0:
            msg = f"🚨 ПРОСРОЧЕНО: {name} — {date_str} ({abs(days)} дн.)"
        elif days in [30, 16, 7]:
            msg = f"⚠️ {name} — через {days} дн. ({date_str})"
        else:
            continue

        result.append((days, msg))

    result.sort(key=lambda x: x[0])
    return [r[1] for r in result]

# ================== ПРОДЛЕНИЕ ==================
def mark_extended(name):
    try:
        sheet = get_sheet()
        rows = sheet.get_all_records()

        for i, row in enumerate(rows, start=2):
            if name.lower() in row.get("ФИО", "").lower():
                sheet.update_cell(i, 8, "да")  # колонка H
                return True

        return False

    except Exception as e:
        print("❌ Ошибка продления:", e)
        return False

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["📋 Показать всё", "⚡ Проверить сейчас"],
        ["✅ Продлить"],
    ],
    resize_keyboard=True,
)

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.bot_data["chat_ids"].add(update.effective_chat.id)
    await update.message.reply_text("Выбери действие 👇", reply_markup=keyboard)

# ================== ПРОВЕРКА ==================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = check_logic()
    await update.message.reply_text("\n".join(res) or "😎 Олегыч, всё тихо")

# ================== РЕЖИМ ПРОДЛЕНИЯ ==================
async def extend_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "extend"
    await update.message.reply_text("Введи фамилию для продления")

# ================== ПЛАНИРОВЩИК ==================
last_sent = set()
last_check_day = None
last_send_day = None

async def scheduler(app):
    global last_check_day, last_send_day, last_sent

    await asyncio.sleep(5)

    while True:
        now = datetime.now()

        # Проверка в 9
        if now.hour >= 9 and last_check_day != now.date():
            print("🔍 Проверка выполнена")
            last_check_day = now.date()

        # Отправка в 11
        if now.hour >= 11 and last_send_day != now.date():
            print("📨 Отправка уведомлений")

            result = check_logic()
            new_msgs = [r for r in result if r not in last_sent]

            text = "\n".join(new_msgs) if new_msgs else "😎 Олегыч, всё тихо"

            for chat_id in app.bot_data["chat_ids"]:
                await app.bot.send_message(chat_id, text)

            last_sent = set(result)
            last_send_day = now.date()

        await asyncio.sleep(60)

# ================== ОБРАБОТКА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    context.application.bot_data["chat_ids"].add(update.effective_chat.id)

    # ПРОДЛЕНИЕ
    if context.user_data.get("mode") == "extend":
        context.user_data["mode"] = None

        if mark_extended(text):
            await update.message.reply_text("✅ Отмечено как продлено")
        else:
            await update.message.reply_text("❌ Не найдено")
        return

    # МЕСЯЦ
    if context.user_data.get("mode") == "month":
        context.user_data["mode"] = None

        months = {
            "январь":1,"февраль":2,"март":3,"апрель":4,
            "май":5,"июнь":6,"июль":7,"август":8,
            "сентябрь":9,"октябрь":10,"ноябрь":11,"декабрь":12
        }

        month = months.get(text) or (int(text) if text.isdigit() else None)

        res = []
        for row in get_data():
            d = parse_date(row.get("Дата окончания", ""))
            if d and d.month == month:
                res.append(f"{row.get('ФИО')} — {row.get('Дата окончания')}")

        await update.message.reply_text("\n".join(res) or "❌ Ничего не найдено")
        return

    # КНОПКИ
    if text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        data = get_data()
        res = [f"{r.get('ФИО')} — {r.get('Дата окончания')}" for r in data]
        await update.message.reply_text("\n".join(res[:50]) or "Нет данных")

    elif text == "📅 по месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введи месяц (например: июль или 7)")

    elif text == "🔍 поиск":
        await update.message.reply_text("Введи фамилию или имя")

    elif text == "✅ продлить":
        await extend_mode(update, context)

    else:
        data = get_data()
        res = [
            f"{r.get('ФИО')} — {r.get('Дата окончания')}"
            for r in data
            if text in r.get("ФИО", "").lower()
        ]
        await update.message.reply_text("\n".join(res) or "❌ Ничего не найдено")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.bot_data["chat_ids"] = set()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    async def on_start(app):
        print("📡 Scheduler started")
        asyncio.create_task(scheduler(app))

    app.post_init = on_start

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
