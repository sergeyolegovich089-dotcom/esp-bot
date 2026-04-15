import os
import asyncio
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# --- Google авторизация ---
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# ================= КНОПКИ =================
keyboard = [
    ["🔍 Поиск", "📅 По месяцу"],
    ["📋 Показать всё", "⚡ Проверить сейчас"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= ДАННЫЕ =================
def get_data():
    return sheet.get_all_records()

# ================= ПРОВЕРКА =================
def check_expiring():
    data = get_data()
    today = datetime.today()
    results = []

    for row in data:
        name = row.get("ФИО", "")
        date_str = row.get("Дата окончания", "")

        try:
            exp_date = datetime.strptime(date_str, "%Y-%m-%d")
            days_left = (exp_date - today).days

            if days_left in [30, 15, 7] or days_left <= 3:
                results.append(
                    f"👤 {name}\n📅 До: {date_str}\n⏳ Осталось: {days_left} дн.\n"
                )
        except:
            continue

    return results

# ================= ФОН =================
async def background_checker(app):
    while True:
        print("🔄 Фоновая проверка...")

        try:
            results = check_expiring()

            if results:
                text = "⚠️ Напоминание по ЭЦП:\n\n" + "\n".join(results)
                await app.bot.send_message(chat_id=ADMIN_ID, text=text)
            else:
                print("✅ Всё спокойно")

        except Exception as e:
            print("Ошибка проверки:", e)

        await asyncio.sleep(86400)  # раз в сутки

# ================= СТАРТ =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери действие 👇",
        reply_markup=markup
    )

# ================= ОБРАБОТКА =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # --- ПРОВЕРИТЬ СЕЙЧАС ---
    if text == "⚡ Проверить сейчас":
        results = check_expiring()

        if results:
            await update.message.reply_text("\n".join(results))
        else:
            await update.message.reply_text("✅ Всё спокойно")

    # --- ПОКАЗАТЬ ВСЕ ---
    elif text == "📋 Показать всё":
        data = get_data()
        lines = []

        for row in data:
            lines.append(
                f"👤 {row.get('ФИО')}\n📅 До: {row.get('Дата окончания')}\n"
            )

        await update.message.reply_text("\n".join(lines[:30]))

    # --- ПО МЕСЯЦУ ---
    elif text == "📅 По месяцу":
        await update.message.reply_text("Введи месяц (например: июль или 7)")

    elif text.lower() in [
        "январь","февраль","март","апрель","май","июнь",
        "июль","август","сентябрь","октябрь","ноябрь","декабрь"
    ] or text.isdigit():

        months = {
            "январь":1,"февраль":2,"март":3,"апрель":4,
            "май":5,"июнь":6,"июль":7,"август":8,
            "сентябрь":9,"октябрь":10,"ноябрь":11,"декабрь":12
        }

        month = int(text) if text.isdigit() else months.get(text.lower())

        data = get_data()
        results = []

        for row in data:
            date_str = row.get("Дата окончания", "")
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if d.month == month:
                    results.append(
                        f"👤 {row.get('ФИО')}\n📅 До: {date_str}\n"
                    )
            except:
                continue

        if results:
            await update.message.reply_text("\n".join(results))
        else:
            await update.message.reply_text("❌ Ничего не найдено")

    # --- ПОИСК (ПРОСТОЙ) ---
    elif text == "🔍 Поиск":
        await update.message.reply_text("Введи имя для поиска")

    else:
        data = get_data()
        results = []

        for row in data:
            name = row.get("ФИО", "").lower()
            if text.lower() in name:
                results.append(
                    f"👤 {row.get('ФИО')}\n📅 До: {row.get('Дата окончания')}\n"
                )

        if results:
            await update.message.reply_text("\n".join(results))
        else:
            await update.message.reply_text("❌ Ничего не найдено")

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle))

    # 🔥 ФОН БЕЗ JOBQUEUE
    asyncio.create_task(background_checker(app))

    print("🚀 Бот запущен")
    await app.run_polling()

# ================= ЗАПУСК =================
if __name__ == "__main__":
    asyncio.run(main())
