import os
import json
import logging
from datetime import datetime, time

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== КОНФИГ ==================
TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")
NOTIFY_TIME = os.getenv("NOTIFY_TIME", "11:00")

# Парсим ADMIN_IDS
try:
    ADMIN_IDS_LIST = [int(id.strip()) for id in ADMIN_IDS.split(",") if id.strip()]
except:
    ADMIN_IDS_LIST = []

# ================== GOOGLE ==================
def get_sheet():
    try:
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        logger.error(f"Google Sheets ошибка: {e}")
        return None

def get_data():
    sheet = get_sheet()
    if not sheet:
        return []
    try:
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Ошибка чтения: {e}")
        return []

# ================== ПРОВЕРКА АДМИНА ==================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS_LIST

# ================== UI ==================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("По городу", callback_data="cities")],
        [InlineKeyboardButton("По месяцу", callback_data="months")],
        [InlineKeyboardButton("Поиск", callback_data="search")],
        [InlineKeyboardButton("Показать всё", callback_data="all")],
        [InlineKeyboardButton("Проверить сейчас", callback_data="check")],
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад", callback_data="menu")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Добавить запись", callback_data="admin_add")],
        [InlineKeyboardButton("Назад", callback_data="menu")],
    ])

# ================== ДАТЫ ==================
def parse_date(date_str):
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except:
            continue
    return None

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
        info = f"ФИО: {row.get('ФИО')}\nДолжность: {row.get('Должность')}\nГород: {row.get('Город')}\nДата: {row.get('Дата окончания')} ({days} дн.)"
        
        if days < 0:
            red.append(info)
        elif days <= 7:
            orange.append(info)
        elif days <= 30:
            yellow.append(info)
    
    text = ""
    if red:
        text += "ПРОСРОЧЕНО:\n" + "\n\n".join(red) + "\n\n"
    if orange:
        text += "СРОЧНО:\n" + "\n\n".join(orange) + "\n\n"
    if yellow:
        text += "ВНИМАНИЕ:\n" + "\n\n".join(yellow)
    
    return text.strip() if text else "Всё под контролем"

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        
        if data == "menu":
            await query.edit_message_text("Выбери действие:", reply_markup=main_menu())
        
        elif data == "admin":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text("Доступ запрещён")
                return
            await query.edit_message_text("Админ-панель", reply_markup=admin_menu())
        
        elif data == "cities":
            cities = sorted({r.get("Город") for r in get_data() if r.get("Город")})
            buttons = [[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
            buttons.append([InlineKeyboardButton("Назад", callback_data="menu")])
            await query.edit_message_text("Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("city:"):
            city = data.split(":")[1].lower()
            result = []
            for r in get_data():
                if city in r.get("Город", "").lower():
                    result.append(f"Город: {r.get('Город')}\nФИО: {r.get('ФИО')}\nДолжность: {r.get('Должность')}\nДата: {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
        elif data == "months":
            months = [("Янв",1),("Фев",2),("Мар",3),("Апр",4),("Май",5),("Июн",6),("Июл",7),("Авг",8),("Сен",9),("Окт",10),("Ноя",11),("Дек",12)]
            buttons = []
            for i in range(0, 12, 3):
                row = [InlineKeyboardButton(m[0], callback_data=f"month:{m[1]}") for m in months[i:i+3]]
                buttons.append(row)
            buttons.append([InlineKeyboardButton("Назад", callback_data="menu")])
            await query.edit_message_text("Выбери месяц:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("month:"):
            month = int(data.split(":")[1])
            result = []
            for r in get_data():
                d = parse_date(r.get("Дата окончания", ""))
                if d and d.month == month:
                    result.append(f"ФИО: {r.get('ФИО')}\nДолжность: {r.get('Должность')}\nГород: {r.get('Город')}\nДата: {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
        elif data == "all":
            data_rows = get_data()
            result = []
            for r in data_rows:
                result.append(f"Город: {r.get('Город')}\nФИО: {r.get('ФИО')}\nДолжность: {r.get('Должность')}\nДата: {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "Нет данных"
            await query.edit_message_text(text, reply_markup=back_button())
        
        elif data == "check":
            text = build_status_text()
            await query.edit_message_text(text, reply_markup=back_button())
        
        elif data == "admin_add":
            context.user_data["admin_action"] = "add"
            await query.edit_message_text("Введите данные: ФИО, Должность, Город, Дата\nИли /cancel для отмены", reply_markup=back_button())
        
    except Exception as e:
        logger.error(f"Callback ошибка: {e}")
        await query.edit_message_text("Ошибка. Попробуйте /start")

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        keyboard = main_menu()
        # Добавляем кнопку админки для админа
        keyboard.inline_keyboard.append([InlineKeyboardButton("Админ-панель", callback_data="admin")])
        await update.message.reply_text("Привет, Админ! Выбери действие:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Привет! Выбери действие:", reply_markup=main_menu())
    
    logger.info(f"/start от {user_id}")

# ================== МОЙ ID ==================
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш ID: {update.effective_user.id}")

# ================== ОТМЕНА ==================
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=main_menu())

# ================== СООБЩЕНИЯ ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Поиск
    if context.user_data.get("search"):
        context.user_data["search"] = False
        result = []
        for r in get_data():
            if text.lower() in r.get("ФИО", "").lower():
                result.append(f"ФИО: {r.get('ФИО')}\nДолжность: {r.get('Должность')}\nГород: {r.get('Город')}\nДата: {r.get('Дата окончания')}")
        await update.message.reply_text("\n\n".join(result[:50]) or "Ничего не найдено", reply_markup=main_menu())
        return
    
    # Админ: Добавление
    if context.user_data.get("admin_action") == "add":
        if not is_admin(user_id):
            await update.message.reply_text("Доступ запрещён")
            return
        
        context.user_data["admin_action"] = None
        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 4:
                await update.message.reply_text("Неверный формат. Используйте: ФИО, Должность, Город, Дата")
                return
            
            sheet = get_sheet()
            if sheet:
                sheet.append_row([parts[0], parts[1], parts[2], parts[3]])
                await update.message.reply_text("Запись добавлена!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("Ошибка подключения к таблице")
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            await update.message.reply_text("Ошибка. Попробуйте ещё раз.")
        return
    
    # Обычное сообщение
    await update.message.reply_text("Используйте меню или /start", reply_markup=main_menu())

# ================== MAIN ==================
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN не найден!")
        return
    if not SHEET_ID:
        logger.error("SHEET_ID не найден!")
        return
    if not GOOGLE_CREDENTIALS:
        logger.error("GOOGLE_CREDENTIALS не найден!")
        return
    
    logger.info("ECP BOT STARTING...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
