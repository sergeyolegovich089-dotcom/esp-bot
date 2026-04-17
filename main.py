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

def get_spreadsheet():
    try:
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
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
        [InlineKeyboardButton("🏙 По городу", callback_data="cities")],
        [InlineKeyboardButton("📅 По месяцу", callback_data="months")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton("📋 Показать всё", callback_data="all")],
        [InlineKeyboardButton("⚡ Проверить сейчас", callback_data="check")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить запись", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Удалить запись", callback_data="admin_delete")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_edit")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")],
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
    ])

def admin_back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад к админке", callback_data="admin")]
    ])

# ================== ДАТЫ ==================
def parse_date(date_str):
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except:
            continue
    return None

# ================== СТАТУСЫ ==================
def build_status_text():
    data = get_data()
    today = datetime.now()
    red, orange, yellow, green = [], [], [], []
    
    for row in data:
        d = parse_date(row.get("Дата окончания", ""))
        if not d:
            continue
        days = (d - today).days
        info = f"👤 {row.get('ФИО')}\n🏢 {row.get('Должность')}\n🏙 {row.get('Город')}\n📅 {row.get('Дата окончания')} ({days} дн.)"
        
        if days < 0:
            red.append(info)
        elif days <= 7:
            orange.append(info)
        elif days <= 30:
            yellow.append(info)
        else:
            green.append(info)
    
    text = ""
    if red:
        text += f"🔴🔴🔴 ПРОСРОЧЕНО 🚨 ({len(red)})\n\n" + "\n\n".join(red) + "\n\n"
    if orange:
        text += f"🟠🟠 СРОЧНО ⚠️ ({len(orange)})\n\n" + "\n\n".join(orange) + "\n\n"
    if yellow:
        text += f"🟡 ВНИМАНИЕ ({len(yellow)})\n\n" + "\n\n".join(yellow) + "\n\n"
    if green:
        text += f"🟢 В НОРМЕ ({len(green)})\n"
    
    return text.strip() if text else "😎 Всё под контролем"

def build_stats_text():
    data = get_data()
    today = datetime.now()
    
    total = len(data)
    expired = 0
    urgent = 0
    warning = 0
    normal = 0
    cities = set()
    
    for row in data:
        d = parse_date(row.get("Дата окончания", ""))
        if not d:
            continue
        days = (d - today).days
        if row.get("Город"):
            cities.add(row.get("Город"))
        
        if days < 0:
            expired += 1
        elif days <= 7:
            urgent += 1
        elif days <= 30:
            warning += 1
        else:
            normal += 1
    
    text = (
        f"📊 СТАТИСТИКА\n\n"
        f"📋 Всего записей: {total}\n"
        f"🟢 В норме: {normal}\n"
        f"🟡 Внимание: {warning}\n"
        f"🟠 Срочно: {urgent}\n"
        f"🔴 Просрочено: {expired}\n\n"
        f"🏙 Городов: {len(cities)}\n"
        f"📅 Дата: {today.strftime('%d.%m.%Y %H:%M')}"
    )
    return text

# ================== АДМИН ФУНКЦИИ ==================
def add_record(fio, position, city, date):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.append_row([fio, position, city, date])
            return True
    except Exception as e:
        logger.error(f"Ошибка добавления: {e}")
    return False

def delete_record(row_number):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.delete_rows(row_number)
            return True
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
    return False

def update_record(row_number, fio, position, city, date):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.update_cell(row_number, 1, fio)
            sheet.update_cell(row_number, 2, position)
            sheet.update_cell(row_number, 3, city)
            sheet.update_cell(row_number, 4, date)
            return True
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")
    return False

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    try:
        # ПРОВЕРКА АДМИНА
        if data.startswith("admin") and not is_admin(user_id):
            await query.edit_message_text("⛔ Доступ запрещён. Только для администратора.")
            return
        
        # МЕНЮ
        if data == "menu":
            await query.edit_message_text("Выбери действие 👇", reply_markup=main_menu())
        
        # АДМИН МЕНЮ
        elif data == "admin":
            await query.edit_message_text("🔧 Админ-панель", reply_markup=admin_menu())
        
        # ГОРОДА
        elif data == "cities":
            cities = sorted({r.get("Город") for r in get_data() if r.get("Город")})
            buttons = [[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
            await query.edit_message_text("🏙 Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("city:"):
            city = data.split(":")[1].lower()
            result = []
            for r in get_data():
                if city in r.get("Город", "").lower():
                    result.append(f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "❌ Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
        # МЕСЯЦЫ
        elif data == "months":
            months = [("Янв",1),("Фев",2),("Мар",3),("Апр",4),("Май",5),("Июн",6),("Июл",7),("Авг",8),("Сен",9),("Окт",10),("Ноя",11),("Дек",12)]
            buttons = []
            for i in range(0, 12, 3):
                row = [InlineKeyboardButton(m[0], callback_data=f"month:{m[1]}") for m in months[i:i+3]]
                buttons.append(row)
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
            await query.edit_message_text("📅 Выбери месяц:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("month:"):
            month = int(data.split(":")[1])
            result = []
            for r in get_data():
                d = parse_date(r.get("Дата окончания", ""))
                if d and d.month == month:
                    result.append(f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "❌ Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
        # ВСЕ ЗАПИСИ
        elif data == "all":
            data_rows = get_data()
            result = []
            for r in data_rows:
                result.append(f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}")
            text = "\n\n".join(result[:50]) or "Нет данных"
            await query.edit_message_text(f"📋 Записей: {len(result)}\n\n{text}", reply_markup=back_button())
        
        # ПРОВЕРКА
        elif data == "check":
            text = build_status_text()
            await query.edit_message_text(text, reply_markup=back_button())
        
        # СТАТИСТИКА
        elif data == "stats":
            if not is_admin(user_id):
                await query.edit_message_text("⛔ Статистика доступна только администратору.")
                return
            text = build_stats_text()
            await query.edit_message_text(text, reply_markup=admin_back_button())
        
        # АДМИН: ДОБАВИТЬ
        elif data == "admin_add":
            context.user_data["admin_action"] = "add"
            await query.edit_message_text(
                "➕ Добавление записи\n\n"
                "Введите данные через запятую:\n"
                "ФИО, Должность, Город, Дата окончания\n\n"
                "Пример:\n"
                "Иванов Иван, Инженер, Москва, 31.12.2025\n\n"
                "Или /cancel для отмены",
                reply_markup=admin_back_button()
            )
        
        # АДМИН: УДАЛИТЬ
        elif data == "admin_delete":
            data_rows = get_data()
            buttons = []
            for i, row in enumerate(data_rows[:20], 2):
                buttons.append([InlineKeyboardButton(
                    f"{i}. {row.get('ФИО', 'N/A')}",
                    callback_data=f"admin_del_confirm:{i}"
                )])
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin")])
            await query.edit_message_text(
                "🗑 Удаление записи\n\nВыберите строку:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif data.startswith("admin_del_confirm:"):
            row_num = int(data.split(":")[1])
            success = delete_record(row_num)
            if success:
                await query.edit_message_text(f"✅ Запись {row_num} удалена!", reply_markup=admin_back_button())
            else:
                await query.edit_message_text("❌ Ошибка удаления.", reply_markup=admin_back_button())
        
        # АДМИН: РЕДАКТИРОВАТЬ
        elif data == "admin_edit":
            context.user_data["admin_action"] = "edit"
            await query.edit_message_text(
                "✏️ Редактирование\n\n"
                "Введите номер строки и новые данные:\n"
                "5, Иванов Иван, Инженер, Москва, 31.12.2025\n\n"
                "Или /cancel для отмены",
                reply_markup=admin_back_button()
            )
        
    except Exception as e:
        logger.error(f"Callback ошибка: {e}")
        await query.edit_message_text("⚠️ Ошибка. Попробуйте /start", reply_markup=main_menu())

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        keyboard = main_menu()
        keyboard.inline_keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin")])
        await update.message.reply_text(
            f"👋 Привет, Администратор!\n\n"
            f"Выбери действие 👇",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            f"👋 Привет, {update.effective_user.first_name}!\n\n"
            f"Выбери действие 👇",
            reply_markup=main_menu()
        )
    
    logger.info(f"/start от {user_id}")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш Telegram ID: `{update.effective_user.id}`", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён. Только для администратора.")
        return
    await update.message.reply_text("🔧 Админ-панель", reply_markup=admin_menu())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text(build_stats_text())

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=main_menu())

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
                result.append(f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}")
        await update.message.reply_text(
            "\n\n".join(result[:50]) or "❌ Ничего не найдено",
            reply_markup=main_menu()
        )
        return
    
    # Админ: Добавление
    if context.user_data.get("admin_action") == "add":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Доступ запрещён.")
            return
        
        context.user_data["admin_action"] = None
        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 4:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: ФИО, Должность, Город, Дата\n/cancel для отмены",
                    reply_markup=admin_back_button()
                )
                return
            
            success = add_record(parts[0], parts[1], parts[2], parts[3])
            if success:
                await update.message.reply_text("✅ Запись добавлена!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("❌ Ошибка добавления.", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            await update.message.reply_text("⚠️ Ошибка. Попробуйте ещё раз.", reply_markup=admin_menu())
        return
    
    # Админ: Редактирование
    if context.user_data.get("admin_action") == "edit":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Доступ запрещён.")
            return
        
        context.user_data["admin_action"] = None
        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 5:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: Номер, ФИО, Должность, Город, Дата\n/cancel для отмены",
                    reply_markup=admin_back_button()
                )
                return
            
            row_num = int(parts[0])
            success = update_record(row_num, parts[1], parts[2], parts[3], parts[4])
            if success:
                await update.message.reply_text(f"✅ Строка {row_num} обновлена!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("❌ Ошибка обновления.", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка редактирования: {e}")
            await update.message.reply_text("⚠️ Ошибка. Попробуйте ещё раз.", reply_markup=admin_menu())
        return
    
    # Обычное сообщение
    await update.message.reply_text(
        "Не понимаю команду. Используйте меню или /start",
        reply_markup=main_menu()
    )

# ================== MAIN ==================
def main():
    if not TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return
    if not SHEET_ID:
        logger.error("❌ SHEET_ID не найден!")
        return
    if not GOOGLE_CREDENTIALS:
        logger.error("❌ GOOGLE_CREDENTIALS не найден!")
        return
    
    logger.info("🔥 ECP BOT VERSION 2.0 (ADMIN + EMOJI)")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
