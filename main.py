import os
import logging
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

# =====================
# ENV
# =====================
TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")

# =====================
# GOOGLE SHEETS
# =====================
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    eval(os.getenv("GOOGLE_CREDENTIALS")), scopes=scope
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# =====================
# КНОПКИ
# =====================
menu = ReplyKeyboardMarkup(
    [
        ["🔍 Поиск", "📅 По месяцу"],
        ["📋 Показать все", "⚡ Проверить сейчас"],
        ["✅ Продлено"],
    ],
    resize_keyboard=True,
)

# =====================
# СТАРТ
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие 👇", reply_markup=menu)

# =====================
# ПОИСК ПО МЕСЯЦУ
# =====================
def parse_month(text):
    text = text.lower()

    months = {
        "январь": 1, "февраль": 2, "март": 3,
        "апрель": 4, "май": 5, "июнь": 6,
        "июль": 7, "август": 8, "сентябрь": 9,
        "октябрь": 10, "ноябрь": 11, "декабрь": 12
    }

    if text.isdigit():
        return int(text)

    return months.get(text)


# =====================
# ПРОВЕРКА СРОКОВ
# =====================
async def check_expiry(context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()
    today = datetime.now()

    for row in rows:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")
        status = row.get("Продлено", "").lower()

        if status == "да":
            continue

        try:
            expiry = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            continue

        days_left = (expiry - today).days

        if days_left in [30, 15, 7] or days_left <= 3:
            text = f"⚠️ {name}\nСрок до: {date_str} ({days_left} дн.)"
            await context.bot.send_message(chat_id=context.job.chat_id, text=text)


# =====================
# ПРОВЕРИТЬ СЕЙЧАС
# =====================
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sheet.get_all_records()
    today = datetime.now()
    found = False

    for row in rows:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")
        status = row.get("Продлено", "").lower()

        if status == "да":
            continue

        try:
            expiry = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            continue

        days_left = (expiry - today).days

        if days_left <= 30:
            found = True
            await update.message.reply_text(
                f"⚠️ {name}\nДо: {date_str} ({days_left} дн.)"
            )

    if not found:
        await update.message.reply_text("✅ Всё спокойно")


# =====================
# ОБРАБОТКА СООБЩЕНИЙ
# =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # кнопки
    if text == "📅 По месяцу":
        context.user_data["mode"] = "month"
        await update.message.reply_text("Введите месяц (например: июль или 7)")
        return

    elif text == "🔍 Поиск":
        context.user_data["mode"] = "search"
        await update.message.reply_text("Введите имя")
        return

    elif text == "📋 Показать все":
        rows = sheet.get_all_records()
        for row in rows:
            await update.message.reply_text(
                f"{row.get('ФИО')}\nДо: {row.get('Дата окончания')}"
            )
        return

    elif text == "⚡ Проверить сейчас":
        await check_now(update, context)
        return

    elif text == "✅ Продлено":
        context.user_data["mode"] = "done"
        await update.message.reply_text("Введите имя сотрудника")
        return

    # =====================
    # РЕЖИМЫ
    # =====================
    mode = context.user_data.get("mode")

    rows = sheet.get_all_records()

    # поиск
    if mode == "search":
        for row in rows:
            if text.lower() in row.get("ФИО", "").lower():
                await update.message.reply_text(
                    f"{row.get('ФИО')}\nДо: {row.get('Дата окончания')}"
                )
                return
        await update.message.reply_text("❌ Не найдено")

    # месяц
    elif mode == "month":
        month = parse_month(text)
        if not month:
            await update.message.reply_text("❌ Неверный месяц")
            return

        found = False

        for row in rows:
            try:
                date = datetime.strptime(row.get("Дата окончания"), "%Y-%m-%d")
            except:
                continue

            if date.month == month:
                found = True
                await update.message.reply_text(
                    f"{row.get('ФИО')}\nДо: {row.get('Дата окончания')}"
                )

        if not found:
            await update.message.reply_text("❌ Ничего не найдено")

    # продлено
    elif mode == "done":
        for i, row in enumerate(rows, start=2):
            if text.lower() in row.get("ФИО", "").lower():
                sheet.update_cell(i, 3, "да")  # колонка Продлено
                await update.message.reply_text(f"✅ Отмечено: {row.get('ФИО')}")
                return

        await update.message.reply_text("❌ Не найдено")


# =====================
# MAIN
# =====================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ежедневная проверка
    app.job_queue.run_daily(
        check_expiry,
        time=datetime.now().time(),
        data=None,
        name="check",
        chat_id=568554255  # ← твой ID
    )

    app.run_polling()


if __name__ == "__main__":
    main()
