import os
import json
import asyncio
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

print("🔥 FINAL VERSION WITH CITY + MONTH BUTTONS")

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
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except:
            continue
    return None

# ================== ГОРОДА ==================
def get_cities():
    data = get_data()
    return sorted({row.get("Город", "").strip() for row in data if row.get("Город")})

# ================== ЛОГИКА ==================
def check_logic():
    data = get_data()
    today = datetime.now()

    expired, urgent, soon = [], [], []

    for row in data:
        name = row.get("ФИО", "")
        position = row.get("Должность", "")
        city = row.get("Город", "")
        date_str = row.get("Дата окончания", "")
        extended = str(row.get("Продлено", "")).lower()

        if extended == "да":
            continue

        d = parse_date(date_str)
        if not d:
            continue

        days = (d - today).days

        info = (
            f"👤 {name}\n"
            f"🏢 {position}\n"
            f"🏙 {city}\n"
            f"📅 {date_str} ({days} дн.)"
        )

        if days < 0:
            expired.append(info)
        elif days <= 7:
            urgent.append(info)
        elif days <= 30:
            soon.append(info)

    blocks = []

    if expired:
        blocks.append(
            "━━━━━━━━━━━━━━\n🔴🔴🔴 ПРОСРОЧЕНО\n━━━━━━━━━━━━━━\n"
            + "\n\n".join(expired)
        )

    if urgent:
        blocks.append(
            "━━━━━━━━━━━━━━\n🟠🟠 СРОЧНО (до 7 дней)\n━━━━━━━━━━━━━━\n"
            + "\n\n".join(urgent)
        )

    if soon:
        blocks.append(
            "━━━━━━━━━━━━━━\n🟡 В ТЕЧЕНИЕ 30 ДНЕЙ\n━━━━━━━━━━━━━━\n"
            + "\n\n".join(soon)
        )

    return blocks

# ================== INLINE ГОРОДА ==================
async def show_cities(update, context):
    cities = get_cities()
    buttons = []

    for i in range(0, len(cities), 2):
        row = [
            InlineKeyboardButton(cities[i], callback_data=f"city:{cities[i]}")
        ]
        if i + 1 < len(cities):
            row.append(
                InlineKeyboardButton(cities[i + 1], callback_data=f"city:{cities[i+1]}")
            )
        buttons.append(row)

    await update.message.reply_text(
        "Выбери город:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ================== INLINE МЕСЯЦЫ ==================
async def show_months(update, context):
    months = [
        ("Январь", 1), ("Февраль", 2),
        ("Март", 3), ("Апрель", 4),
        ("Май", 5), ("Июнь", 6),
        ("Июль", 7), ("Август", 8),
        ("Сентябрь", 9), ("Октябрь", 10),
        ("Ноябрь", 11), ("Декабрь", 12),
    ]

    buttons = []

    for i in range(0, len(months), 2):
        row = [
            InlineKeyboardButton(months[i][0], callback_data=f"month:{months[i][1]}")
        ]
        if i + 1 < len(months):
            row.append(
                InlineKeyboardButton(months[i + 1][0], callback_data=f"month:{months[i+1][1]}")
            )
        buttons.append(row)

    await update.message.reply_text(
        "Выбери месяц:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ================== CALLBACK ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # ГОРОД
    if data.startswith("city:"):
        city = data.split(":")[1].lower()

        res = []
        for row in get_data():
            if city in row.get("Город", "").lower():
                res.append(
                    f"🏙 {row.get('Город')}\n👤 {row.get('ФИО')}\n🏢 {row.get('Должность')}\n📅 {row.get('Дата окончания')}"
                )

        await query.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

    # МЕСЯЦ
    elif data.startswith("month:"):
        month = int(data.split(":")[1])

        res = []
        for row in get_data():
            d = parse_date(row.get("Дата окончания", ""))
            if d and d.month == month:
                res.append(
                    f"👤 {row.get('ФИО')}\n🏢 {row.get('Должность')}\n🏙 {row.get('Город')}\n📅 {row.get('Дата окончания')}"
                )

        await query.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

# ================== ПРОВЕРКА ==================
async def check_now(update, context):
    res = check_logic()
    await update.message.reply_text("\n\n".join(res) or "😎 Олегыч, всё тихо")

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["🏙 По городу", "📋 Показать всё"],
        ["⚡ Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# ================== ОБРАБОТКА ==================
async def text_handler(update, context):
    text = update.message.text.lower()

    if text == "🏙 по городу":
        await show_cities(update, context)

    elif text == "📅 по месяцу":
        await show_months(update, context)

    elif text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        data = get_data()
        res = [
            f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
            for r in data
        ]
        await update.message.reply_text("\n\n".join(res[:50]) or "Нет данных")

    else:
        data = get_data()
        res = [
            f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}"
            for r in data
            if text in r.get("ФИО", "").lower()
        ]
        await update.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

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
