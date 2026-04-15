import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

print("🔥 CITY → MONTH → LIST VERSION")

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
    except:
        return []

# ================== ДАТЫ ==================
def parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except:
            continue
    return None

# ================== ГОРОДА ==================
def get_cities():
    return sorted({
        row.get("Город", "").strip()
        for row in get_data()
        if row.get("Город")
    })

# ================== МЕСЯЦЫ ==================
def get_month_buttons(city):
    months = [
        ("Янв",1),("Фев",2),("Мар",3),("Апр",4),
        ("Май",5),("Июн",6),("Июл",7),("Авг",8),
        ("Сен",9),("Окт",10),("Ноя",11),("Дек",12)
    ]

    buttons = []
    for i in range(0, len(months), 3):
        row = []
        for m in months[i:i+3]:
            row.append(InlineKeyboardButton(m[0], callback_data=f"month:{city}:{m[1]}"))
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🏙 По городу", "📋 Показать всё"],
        ["⚡ Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# ================== ГОРОДА ==================
async def show_cities(update, context):
    cities = get_cities()
    buttons = []

    for i in range(0, len(cities), 2):
        row = [InlineKeyboardButton(cities[i], callback_data=f"city:{cities[i]}")]
        if i + 1 < len(cities):
            row.append(InlineKeyboardButton(cities[i+1], callback_data=f"city:{cities[i+1]}"))
        buttons.append(row)

    await update.message.reply_text(
        "Выбери город:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================== CALLBACK ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # 1. ВЫБРАЛ ГОРОД → ПОКАЗАТЬ МЕСЯЦЫ
    if data.startswith("city:"):
        city = data.split(":")[1]

        await query.message.reply_text(
            f"🏙 {city}\nВыбери месяц:",
            reply_markup=get_month_buttons(city)
        )

    # 2. ВЫБРАЛ МЕСЯЦ → ПОКАЗАТЬ СОТРУДНИКОВ
    elif data.startswith("month:"):
        _, city, month = data.split(":")
        month = int(month)

        res = []

        for row in get_data():
            d = parse_date(row.get("Дата окончания", ""))
            if not d:
                continue

            if city.lower() in row.get("Город", "").lower() and d.month == month:
                res.append(
                    f"🏙 {row.get('Город')}\n"
                    f"👤 {row.get('ФИО')}\n"
                    f"🏢 {row.get('Должность')}\n"
                    f"📅 {row.get('Дата окончания')}"
                )

        await query.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

# ================== ПРОВЕРКА ==================
async def check_now(update, context):
    await update.message.reply_text("Проверка работает 👍")

# ================== ОБРАБОТКА ==================
async def text_handler(update, context):
    text = update.message.text.lower()

    if text == "🏙 по городу":
        await show_cities(update, context)

    elif text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        data = get_data()
        res = [
            f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
            for r in data
        ]
        await update.message.reply_text("\n\n".join(res[:50]) or "Нет данных")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Готов 👍", reply_markup=keyboard)))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
