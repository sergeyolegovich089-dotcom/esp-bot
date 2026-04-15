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

print("🔥 FINAL PRO VERSION")

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

# ================== ЛОГИКА С БЛОКАМИ ==================
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
            "━━━━━━━━━━━━━━\n"
            "🔴🔴🔴 ПРОСРОЧЕНО\n"
            "━━━━━━━━━━━━━━\n"
            + "\n\n".join(expired)
        )

    if urgent:
        blocks.append(
            "━━━━━━━━━━━━━━\n"
            "🟠🟠 СРОЧНО (до 7 дней)\n"
            "━━━━━━━━━━━━━━\n"
            + "\n\n".join(urgent)
        )

    if soon:
        blocks.append(
            "━━━━━━━━━━━━━━\n"
            "🟡 В ТЕЧЕНИЕ 30 ДНЕЙ\n"
            "━━━━━━━━━━━━━━\n"
            + "\n\n".join(soon)
        )

    return blocks

# ================== ПРОДЛЕНИЕ ==================
def mark_extended(name):
    try:
        sheet = get_sheet()
        rows = sheet.get_all_records()

        for i, row in enumerate(rows, start=2):
            if name.lower() in row.get("ФИО", "").lower():
                sheet.update_cell(i, 8, "да")
                return True
        return False

    except Exception as e:
        print("❌ Ошибка продления:", e)
        return False

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["🏙 По городу", "📋 Показать всё"],
        ["⚡ Проверить сейчас", "✅ Продлить"],
    ],
    resize_keyboard=True,
)

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.bot_data["chat_ids"].add(update.effective_chat.id)
    await update.message.reply_text("Выбери действие 👇", reply_markup=keyboard)

# ================== ГОРОДА INLINE ==================
async def show_cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cities = get_cities()

    buttons = []
    row = []

    for i, city in enumerate(cities, 1):
        row.append(InlineKeyboardButton(city, callback_data=f"city:{city}"))
        if i % 2 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await update.message.reply_text(
        "Выбери город:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    city = query.data.split(":")[1].lower()

    res = []
    for row in get_data():
        if city in row.get("Город", "").lower():
            res.append(
                f"🏙 {row.get('Город')}\n👤 {row.get('ФИО')}\n🏢 {row.get('Должность')}\n📅 {row.get('Дата окончания')}"
            )

    await query.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

# ================== ПРОВЕРКА ==================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = check_logic()
    await update.message.reply_text("\n\n".join(res) or "😎 Олегыч, всё тихо")

# ================== SCHEDULER ==================
last_sent = set()
last_day = None

async def scheduler(app):
    global last_sent, last_day

    await asyncio.sleep(5)

    while True:
        now = datetime.now()

        if now.hour >= 11 and last_day != now.date():
            result = check_logic()
            text = "\n\n".join(result) if result else "😎 Олегыч, всё тихо"

            for chat_id in app.bot_data["chat_ids"]:
                await app.bot.send_message(chat_id, text)

            last_sent = set(result)
            last_day = now.date()

        await asyncio.sleep(60)

# ================== ОБРАБОТКА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    context.application.bot_data["chat_ids"].add(update.effective_chat.id)

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

    elif text == "🔍 поиск":
        await update.message.reply_text("Введи фамилию или имя")

    elif text == "📅 по месяцу":
        await update.message.reply_text("Введи месяц")

    elif text == "✅ продлить":
        await update.message.reply_text("Введи фамилию")

    else:
        data = get_data()
        res = [
            f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
            for r in data
            if text in r.get("ФИО", "").lower()
        ]
        await update.message.reply_text("\n\n".join(res) or "❌ Ничего не найдено")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.bot_data["chat_ids"] = set()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(city_callback, pattern="^city:"))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    async def on_start(app):
        asyncio.create_task(scheduler(app))

    app.post_init = on_start

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
