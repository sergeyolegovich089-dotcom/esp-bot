import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# === НАСТРОЙКИ ===
TOKEN = "ТВОЙ_ТОКЕН_БОТА"
SHEET_URL = "ТВОЯ_ССЫЛКА_НА_ТАБЛИЦУ"

# === GOOGLE SHEETS ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL).sheet1

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === КОМАНДА /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает. Используй /find Фамилия")

# === КОМАНДА /find ===
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши: /find Иванов")
        return

    name = context.args[0].lower()
    data = sheet.get_all_records()

    for row in data:
        if name in row["ФИО"].lower():
            msg = (
                f"ФИО: {row['ФИО']}\n"
                f"Должность: {row['Должность']}\n"
                f"Город: {row['Город']}\n"
                f"Начало: {row['Дата начала']}\n"
                f"Окончание: {row['Дата окончания']}\n"
                f"Статус: {row['Статус']}"
            )
            await update.message.reply_text(msg)
            return

    await update.message.reply_text("Не найдено")

# === ЗАПУСК ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
