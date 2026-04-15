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

print("✅ NEW VERSION WORKING")

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", "568554255"))

# ================= GOOGLE =================
sheet = None

def init_google():
    global sheet
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")

        if not creds_json:
            print("❌ GOOGLE_CREDENTIALS не найден")
            return

        creds_dict = json.loads(creds_json)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1

        print("✅ Google подключен")

    except Exception as e:
        print("❌ Ошибка Google:", e)

# ================= КНОПКИ =================
keyboard = [
    ["🔍 Поиск", "📅 По месяцу"],
    ["📋 Показать всё", "⚡ Проверить сейчас"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= ДАННЫЕ =================
def get_data():
    try:
        if sheet:
            return sheet.get_all_records()
    except Exception as e:
        print("Ошибка чтения таблицы:", e)
    return []

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
    await asyncio.sleep(10)

    while True:
        print("🔄 Проверка...")

        try:
            results = check_expiring()

            if results:
                text = "⚠️ Напоминание:\n\n" + "\n".join(results)
                await app.bot.send_message(chat_id=ADMIN_ID, text=text)
            else:
                print("✅ Всё спокойно")

        except Exception as e:
            print("Ошибка фоновой проверки:", e)

        await asyncio.sleep(86400)

# ================= СТАРТ =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие 👇", reply_markup=markup)

# ================= ОБРАБОТКА =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    try:
        # --- ПРОВЕРИТЬ ---
        if text == "⚡ Проверить сейчас":
            results = check_expiring()
            await update.message.reply_text("\n".join(results) or "✅ Всё спокойно")

        # --- ВСЕ ---
        elif text == "📋 Показать всё":
            data = get_data()
            lines = [
                f"👤 {r.get('ФИО')}\n📅 До: {r.get('Дата окончания')}\n"
                for r in data
            ]
            await update.message.reply_text("\n".join(lines[:30]) or "Нет данных")

        # --- МЕСЯЦ ---
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
                try:
                    d = datetime.strptime(row.get("Дата окончания"), "%Y-%m-%d")
                    if d.month == month:
                        results.append(
                            f"👤 {row.get('ФИО')}\n📅 До: {row.get('Дата окончания')}\n"
                        )
                except:
                    continue

            await update.message.reply_text("\n".join(results) or "❌ Ничего не найдено")

        # --- ПОИСК ---
        elif text == "🔍 Поиск":
            await update.message.reply_text("Введи имя")

        else:
            data = get_data()
            results = [
                f"👤 {r.get('ФИО')}\n📅 До: {r.get('Дата окончания')}\n"
                for r in data
                if text.lower() in r.get("ФИО", "").lower()
            ]

            await update.message.reply_text("\n".join(results) or "❌ Ничего не найдено")

    except Exception as e:
        print("Ошибка:", e)
        await update.message.reply_text("⚠️ Ошибка")

# ================= MAIN =================
async def main():
    init_google()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle))

    asyncio.create_task(background_checker(app))

    print("🚀 Бот запущен")
    await app.run_polling()

# ================= ЗАПУСК =================
if __name__ == "__main__":
    asyncio.run(main())
