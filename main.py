import os
import json
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

# ================== ПЕРЕМЕННЫЕ ==================
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
        sheet = get_sheet()
        return sheet.get_all_records()
    except Exception as e:
        print("❌ Ошибка Google:", e)
        return []

# ================== ПАРСИНГ ДАТ ==================
def parse_date(date_str):
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # защита от кривых дат типа 2026-06-2026
    parts = date_str.split("-")
    if len(parts) == 3 and len(parts[2]) > 2:
        return None

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue

    return None

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
    await update.message.reply_text("Выбери действие 👇", reply_markup=keyboard)

# ================== ПРОВЕРКА ==================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    today = datetime.now()
    result = []

    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")

        d = parse_date(date_str)
        if not d:
            continue

        days = (d - today).days

        if days <= 30:
            result.append(f"⚠️ {name} — {date_str} ({days} дн.)")

    await update.message.reply_text("\n".join(result) or "✅ Всё спокойно")

# ================== ПОКАЗАТЬ ВСЕ ==================
async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()

    result = []
    for r in data:
        result.append(
            f"👤 {r.get('ФИО')}\n📅 До: {r.get('Дата окончания')}\n"
        )

    await update.message.reply_text("\n".join(result[:50]) or "Нет данных")

# ================== ОБРАБОТКА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    # ===== РЕЖИМ МЕСЯЦА =====
    if context.user_data.get("mode") == "month":
        context.user_data["mode"] = None

        months = {
            "январь":1,"февраль":2,"март":3,"апрель":4,
            "май":5,"июнь":6,"июль":7,"август":8,
            "сентябрь":9,"октябрь":10,"ноябрь":11,"декабрь":12
        }

        if text in months:
            month = months[text]
        elif text.isdigit():
            month = int(text)
        else:
            await update.message.reply_text("❌ Неверный месяц")
            return

        data = get_data()
        result = []

        for row in data:
            date_str = row.get("Дата окончания", "")
            d = parse_date(date_str)

            if not d:
                continue

            if d.month == month:
                result.append(
                    f"👤 {row.get('ФИО')}\n📅 До: {date_str}\n"
                )

        await update.message.reply_text("\n".join(result) or "❌ Ничего не найдено")
        return

    # ===== КНОПКИ =====
    if text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        await show_all(update, context)

    elif text == "📅 по месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введи месяц (например: июль или 7)")

    elif text == "🔍 поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введи имя")

    else:
        # ===== ПОИСК =====
        data = get_data()
        result = [
            f"👤 {r.get('ФИО')}\n📅 До: {r.get('Дата окончания')}\n"
            for r in data
            if text in r.get("ФИО", "").lower()
        ]

        await update.message.reply_text("\n".join(result) or "❌ Ничего не найдено")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
