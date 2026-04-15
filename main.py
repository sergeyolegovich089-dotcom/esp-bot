import logging
import os
import json
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# =========================
# 🔐 НАСТРОЙКИ
# =========================

TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_URL"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =========================
# 📊 GOOGLE SHEETS
# =========================

def get_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

# =========================
# 🧠 ЛОГИ
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========================
# 🚀 КОМАНДЫ
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот работает\n\n"
        "Используй:\n"
        "/find Иванов"
    )

# 🔍 УМНЫЙ ПОИСК
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("Напиши: /find Иванов")
            return

        query = " ".join(context.args).lower()

        sheet = get_sheet()
        data = sheet.get_all_records()

        results = []

        for row in data:
            fio = str(row.get("ФИО", "")).lower()

            if query in fio:
                results.append(row)

        if not results:
            await update.message.reply_text("❌ Ничего не найдено")
            return

        # выводим максимум 5 результатов
        for row in results[:5]:
            msg = (
                f"👤 {row.get('ФИО','-')}\n"
                f"💼 {row.get('Должность','-')}\n"
                f"🏙 {row.get('Город','-')}\n"
                f"📅 {row.get('Дата начала','-')} → {row.get('Дата окончания','-')}\n"
                f"📊 Статус: {row.get('Статус','-')}\n"
            )
            await update.message.reply_text(msg)

    except Exception as e:
        logging.error(f"Ошибка в /find: {e}")
        await update.message.reply_text("⚠️ Ошибка при поиске")

# =========================
# 🏁 ЗАПУСК
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))

    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
