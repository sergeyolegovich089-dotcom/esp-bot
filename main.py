import os
import json
from datetime import datetime, time

import gspread
from google.oauth2.service_account import Credentials

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

print("🔥 CARD VERSION")

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

# ================== UI ==================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏙 По городу", callback_data="cities")],
        [InlineKeyboardButton("📅 По месяцу", callback_data="months")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton("📋 Показать всё", callback_data="all")],
        [InlineKeyboardButton("⚡ Проверить сейчас", callback_data="check")],
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
    ])

# ================== СТАТУСЫ ==================
def build_status_text():
    data = get_data()
    today = datetime.now()

    result = []

    for row in data:
        d = parse_date(row.get("Дата окончания", ""))
        if not d:
            continue

        days = (d - today).days

        if days <= 30:
            result.append(
                f"👤 {row.get('ФИО')} — {days} дн."
            )

    return "\n".join(result)

# ================== КАРТОЧКА ==================
def build_card(row):
    return (
        f"👤 {row.get('ФИО')}\n"
        f"🏢 {row.get('Должность')}\n"
        f"🏙 {row.get('Город')}\n"
        f"📅 {row.get('Дата окончания')}"
    )

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # МЕНЮ
    if data == "menu":
        await query.edit_message_text("Выбери действие 👇", reply_markup=main_menu())

    # ГОРОДА
    elif data == "cities":
        cities = sorted({r.get("Город") for r in get_data() if r.get("Город")})
        buttons = [[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])

        await query.edit_message_text("Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("city:"):
        city = data.split(":")[1].lower()

        data_rows = [
            r for r in get_data()
            if city in r.get("Город", "").lower()
        ]

        buttons = [
            [InlineKeyboardButton(r.get("ФИО"), callback_data=f"user:{i}")]
            for i, r in enumerate(data_rows)
        ]

        context.user_data["list"] = data_rows

        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="cities")])

        await query.edit_message_text(
            "Выбери сотрудника:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # МЕСЯЦЫ
    elif data == "months":
        months = [
            ("Янв",1),("Фев",2),("Мар",3),("Апр",4),
            ("Май",5),("Июн",6),("Июл",7),("Авг",8),
            ("Сен",9),("Окт",10),("Ноя",11),("Дек",12)
        ]

        buttons = []
        for i in range(0, 12, 3):
            row = [InlineKeyboardButton(m[0], callback_data=f"month:{m[1]}") for m in months[i:i+3]]
            buttons.append(row)

        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])

        await query.edit_message_text("Выбери месяц:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("month:"):
        month = int(data.split(":")[1])

        data_rows = []
        for r in get_data():
            d = parse_date(r.get("Дата окончания", ""))
            if d and d.month == month:
                data_rows.append(r)

        buttons = [
            [InlineKeyboardButton(r.get("ФИО"), callback_data=f"user:{i}")]
            for i, r in enumerate(data_rows)
        ]

        context.user_data["list"] = data_rows

        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="months")])

        await query.edit_message_text(
            "Выбери сотрудника:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # КАРТОЧКА СОТРУДНИКА
    elif data.startswith("user:"):
        idx = int(data.split(":")[1])
        row = context.user_data.get("list", [])[idx]

        await query.edit_message_text(
            build_card(row),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
            ])
        )

    # ВСЕ
    elif data == "all":
        data_rows = get_data()

        buttons = [
            [InlineKeyboardButton(r.get("ФИО"), callback_data=f"user:{i}")]
            for i, r in enumerate(data_rows[:50])
        ]

        context.user_data["list"] = data_rows

        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])

        await query.edit_message_text(
            "Выбери сотрудника:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ПРОВЕРКА
    elif data == "check":
        text = build_status_text() or "😎 Олегыч, всё под контролем"
        await query.edit_message_text(text, reply_markup=back_button())

    # ПОИСК
    elif data == "search":
        context.user_data["search"] = True
        await query.edit_message_text("Введи фамилию или имя:")

# ================== ПОИСК ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("search"):
        context.user_data["search"] = False

        text = update.message.text.lower()

        data_rows = [
            r for r in get_data()
            if text in r.get("ФИО", "").lower()
        ]

        buttons = [
            [InlineKeyboardButton(r.get("ФИО"), callback_data=f"user:{i}")]
            for i, r in enumerate(data_rows)
        ]

        context.user_data["list"] = data_rows

        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])

        await update.message.reply_text(
            "Результаты поиска:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id

    await update.message.reply_text("Выбери действие 👇", reply_markup=main_menu())

# ================== АВТО ==================
async def notify(context: ContextTypes.DEFAULT_TYPE):
    if CHAT_ID:
        text = build_status_text() or "😎 Олегыч, всё под контролем"
        await context.bot.send_message(chat_id=CHAT_ID, text=text)

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.job_queue.run_daily(notify, time(hour=11, minute=0))

    print("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
