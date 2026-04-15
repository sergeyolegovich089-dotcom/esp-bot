import os
import json
from datetime import datetime, time

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

print("✅ STABLE VERSION WITH JOB QUEUE")

TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

CHAT_ID = None

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
    return sorted({
        row.get("Город", "").strip()
        for row in get_data()
        if row.get("Город")
    })

# ================== МЕСЯЦЫ ==================
def get_month_buttons():
    months = [
        ("Янв",1),("Фев",2),("Мар",3),("Апр",4),
        ("Май",5),("Июн",6),("Июл",7),("Авг",8),
        ("Сен",9),("Окт",10),("Ноя",11),("Дек",12)
    ]

    buttons = []
    for i in range(0, len(months), 3):
        row = []
        for m in months[i:i+3]:
            row.append(InlineKeyboardButton(m[0], callback_data=f"month:{m[1]}"))
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)

# ================== КНОПКИ ==================
keyboard = ReplyKeyboardMarkup(
    [
        ["🏙 По городу", "📅 По месяцу"],
        ["🔍 Поиск", "📋 Показать всё"],
        ["⚡ Проверить сейчас"],
    ],
    resize_keyboard=True,
)

# ================== СТАТУСЫ ==================
def build_status_text():
    data = get_data()
    today = datetime.now()

    red, orange, yellow = [], [], []

    for row in data:
        d = parse_date(row.get("Дата окончания", ""))
        if not d:
            continue

        days = (d - today).days

        info = (
            f"👤 {row.get('ФИО')}\n"
            f"🏢 {row.get('Должность')}\n"
            f"🏙 {row.get('Город')}\n"
            f"📅 {row.get('Дата окончания')} ({days} дн.)"
        )

        if days < 0:
            red.append(info)
        elif days <= 7:
            orange.append(info)
        elif days <= 30:
            yellow.append(info)

    text = ""

    if red:
        text += "🔴🔴🔴 ПРОСРОЧЕНО 🚨\n" + "\n\n".join(red) + "\n\n"
    if orange:
        text += "🟠🟠 СРОЧНО ⚠️\n" + "\n\n".join(orange) + "\n\n"
    if yellow:
        text += "🟡 ВНИМАНИЕ\n" + "\n\n".join(yellow)

    return text.strip()

# ================== CALLBACK ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("city:"):
        city = data.split(":")[1].lower()

        result = [
            f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
            for r in get_data()
            if city in r.get("Город", "").lower()
        ]

        await query.message.reply_text("\n\n".join(result) or "❌ Ничего не найдено")

    elif data.startswith("month:"):
        month = int(data.split(":")[1])

        result = []
        for r in get_data():
            d = parse_date(r.get("Дата окончания", ""))
            if d and d.month == month:
                result.append(
                    f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}"
                )

        await query.message.reply_text("\n\n".join(result) or "❌ Ничего не найдено")

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    await update.message.reply_text("Бот готов 👇", reply_markup=keyboard)

async def check_now(update, context):
    text = build_status_text()
    await update.message.reply_text(text or "😎 Олегыч, всё под контролем")

async def show_all(update, context):
    data = get_data()
    res = [
        f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
        for r in data
    ]
    await update.message.reply_text("\n\n".join(res[:50]) or "Нет данных")

async def show_cities(update, context):
    cities = get_cities()
    buttons = [[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
    await update.message.reply_text("Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))

# ================== ПОИСК ==================
async def text_handler(update, context):
    text = update.message.text.lower()

    if text == "🔍 поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введи фамилию или имя")
        return

    if context.user_data.get("mode") == "search":
        context.user_data["mode"] = None

        result = [
            f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}"
            for r in get_data()
            if text in r.get("ФИО", "").lower()
        ]

        await update.message.reply_text("\n\n".join(result) or "❌ Ничего не найдено")
        return

    if text == "🏙 по городу":
        await show_cities(update, context)

    elif text == "📅 по месяцу":
        await update.message.reply_text("Выбери месяц:", reply_markup=get_month_buttons())

    elif text == "⚡ проверить сейчас":
        await check_now(update, context)

    elif text == "📋 показать всё":
        await show_all(update, context)

# ================== АВТОУВЕДОМЛЕНИЕ ==================
async def notify(context: ContextTypes.DEFAULT_TYPE):
    if CHAT_ID:
        text = build_status_text()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=text or "😎 Олегыч, всё под контролем"
        )

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    # ⏰ каждый день в 11:00
    app.job_queue.run_daily(notify, time=time(hour=11, minute=0))

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
