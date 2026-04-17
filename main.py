import os
import json
import logging
from datetime import datetime, time
from typing import Optional, List

import gspread
from google.oauth2.service_account import Credentials
from google.api_core.exceptions import GoogleAPIError

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

# 🔐 ВАШ TELEGRAM ID (замените на свой!)
# Узнать можно через бота @userinfobot или командой /myid
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# Время уведомлений (часы:минуты)
NOTIFY_TIME = os.getenv("NOTIFY_TIME", "11:00")

# ================== GOOGLE ==================
def get_spreadsheet():
    """Получаем доступ ко всей таблице"""
    try:
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
        raise

def get_sheet():
    """Получаем доступ к основному листу"""
    try:
        return get_spreadsheet().sheet1
    except Exception as e:
        logger.error(f"❌ Ошибка доступа к листу: {e}")
        raise

def get_settings_sheet():
    """Получаем или создаём лист настроек"""
    try:
        spreadsheet = get_spreadsheet()
        try:
            return spreadsheet.worksheet('settings')
        except gspread.WorksheetNotFound:
            settings_sheet = spreadsheet.add_worksheet('settings', 100, 2)
            settings_sheet.update([['chat_id'], ['admin_id']], 'A1:B1')
            return settings_sheet
    except Exception as e:
        logger.error(f"❌ Ошибка доступа к settings: {e}")
        raise

def get_data():
    """Получаем все данные из таблицы"""
    try:
        return get_sheet().get_all_records()
    except GoogleAPIError as e:
        logger.error(f"❌ Ошибка чтения данных: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        return []

# ================== СОХРАНЕНИЕ ID ==================
def save_chat_id(chat_id: int, is_admin: bool = False):
    """Сохраняем chat_id в Google Таблицу"""
    try:
        settings_sheet = get_settings_sheet()
        data = settings_sheet.get_all_values()
        
        # Проверяем есть ли уже такой ID
        for i, row in enumerate(data, 1):
            if str(chat_id) in row:
                return  # Уже есть
        
        # Добавляем новый
        column = 'B' if is_admin else 'A'
        settings_sheet.update([[str(chat_id)]], f'{column}{len(data) + 1}')
        logger.info(f"✅ {'Admin' if is_admin else 'Chat'} ID сохранён: {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения ID: {e}")

def get_chat_ids() -> List[int]:
    """Получаем список chat_id для уведомлений"""
    try:
        settings_sheet = get_settings_sheet()
        data = settings_sheet.get_all_values()
        ids = []
        for row in data[1:]:  # Пропускаем заголовок
            if row and row[0] and row[0].isdigit():
                ids.append(int(row[0]))
        return ids if ids else ADMIN_IDS
    except:
        return ADMIN_IDS

def is_admin(user_id: int) -> bool:
    """Проверяем является ли пользователь админом"""
    return user_id in ADMIN_IDS or user_id in get_admin_ids()

def get_admin_ids() -> List[int]:
    """Получаем список админ ID из таблицы"""
    try:
        settings_sheet = get_settings_sheet()
        data = settings_sheet.get_all_values()
        ids = []
        for row in data[1:]:
            if len(row) > 1 and row[1] and row[1].isdigit():
                ids.append(int(row[1]))
        return ids
    except:
        return []

# ================== ДАТЫ ==================
def parse_date(date_str):
    """Парсим дату в разных форматах"""
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d",
        "%d-%m-%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d.%m.%y", "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
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

def pagination_buttons(data: list, page: int = 0, page_size: int = 20, prefix: str = "all"):
    """Создаёт кнопки пагинации"""
    if not data:
        return back_button()
    
    total_pages = (len(data) + page_size - 1) // page_size
    buttons = []
    
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page:{page-1}"))
    
    buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_page:{page+1}"))
    
    buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    
    return InlineKeyboardMarkup([buttons])

# ================== СТАТУСЫ ==================
def build_status_text():
    """Строим текст со статусами документов"""
    data = get_data()
    today = datetime.now()
    
    red, orange, yellow, green = [], [], [], []
    
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
        else:
            green.append(info)
    
    text = ""
    if red:
        text += f"🔴🔴🔴 ПРОСРОЧЕНО 🚨 ({len(red)})\n" + "\n\n".join(red) + "\n\n"
    if orange:
        text += f"🟠🟠 СРОЧНО ⚠️ ({len(orange)})\n" + "\n\n".join(orange) + "\n\n"
    if yellow:
        text += f"🟡 ВНИМАНИЕ ({len(yellow)})\n" + "\n\n".join(yellow) + "\n\n"
    if green:
        text += f"🟢 В НОРМЕ ({len(green)})\n" + "\n\n".join(green[:10])  # Показываем только 10
    
    return text.strip() if text else "😎 Всё под контролем"

def build_stats_text():
    """Строим статистику"""
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
        f"📊 **СТАТИСТИКА**\n\n"
        f"📋 Всего записей: {total}\n"
        f"🟢 В норме: {normal}\n"
        f"🟡 Внимание: {warning}\n"
        f"🟠 Срочно: {urgent}\n"
        f"🔴 Просрочено: {expired}\n\n"
        f"🏙 Городов: {len(cities)}\n"
        f"📅 Дата проверки: {today.strftime('%d.%m.%Y %H:%M')}"
    )
    
    return text

# ================== АДМИН ПАНЕЛЬ ==================
async def admin_add_record(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict):
    """Добавляет новую запись в таблицу"""
    try:
        sheet = get_sheet()
        # Получаем заголовки
        headers = sheet.row_values(1)
        
        # Формируем новую строку
        new_row = []
        for header in headers:
            new_row.append(data.get(header, ""))
        
        # Добавляем строку
        sheet.append_row(new_row)
        logger.info(f"✅ Добавлена запись: {data}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка добавления записи: {e}")
        return False

async def admin_delete_record(update: Update, context: ContextTypes.DEFAULT_TYPE, row_number: int):
    """Удаляет запись по номеру строки"""
    try:
        sheet = get_sheet()
        sheet.delete_rows(row_number)
        logger.info(f"✅ Удалена строка: {row_number}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка удаления записи: {e}")
        return False

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    try:
        data = query.data
        
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
            await query.edit_message_text("Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("city:"):
            city = data.split(":")[1].lower()
            result = [
                f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
                for r in get_data()
                if city in r.get("Город", "").lower()
            ]
            text = "\n\n".join(result[:50]) or "❌ Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
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
            result = []
            for r in get_data():
                d = parse_date(r.get("Дата окончания", ""))
                if d and d.month == month:
                    result.append(
                        f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}"
                    )
            text = "\n\n".join(result[:50]) or "❌ Ничего не найдено"
            await query.edit_message_text(text, reply_markup=back_button())
        
        # ВСЕ ЗАПИСИ
        elif data == "all":
            data_rows = get_data()
            result = [
                f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}"
                for r in data_rows
            ]
            page = context.user_data.get("all_page", 0)
            page_size = 20
            start = page * page_size
            end = start + page_size
            page_data = result[start:end]
            
            text = "\n\n".join(page_data) or "Нет данных"
            await query.edit_message_text(
                f"📋 Записи {start+1}-{min(end, len(result))} из {len(result)}\n\n{text}",
                reply_markup=pagination_buttons(result, page)
            )
        
        elif data.startswith("all_page:"):
            page = int(data.split(":")[1])
            context.user_data["all_page"] = page
            await callback(update, context)
            return
        
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
            context.user_data["add_data"] = {}
            await query.edit_message_text(
                "➕ **Добавление записи**\n\n"
                "Введите данные в формате:\n"
                `ФИО, Должность, Город, Дата окончания`\n\n"
                "Пример:\n"
                `Иванов Иван, Инженер, Москва, 31.12.2025`\n\n"
                "Или отправьте /cancel для отмены",
                reply_markup=admin_back_button(),
                parse_mode='Markdown'
            )
        
        # АДМИН: УДАЛИТЬ
        elif data == "admin_delete":
            data_rows = get_data()
            buttons = []
            for i, row in enumerate(data_rows[:20], 2):  # Начинаем с 2 (1 - заголовки)
                buttons.append([InlineKeyboardButton(
                    f"{i}. {row.get('ФИО', 'N/A')}",
                    callback_data=f"admin_del_confirm:{i}"
                )])
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin")])
            await query.edit_message_text(
                "🗑 **Удаление записи**\n\nВыберите строку:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='Markdown'
            )
        
        elif data.startswith("admin_del_confirm:"):
            row_num = int(data.split(":")[1])
            success = await admin_delete_record(update, context, row_num)
            if success:
                await query.edit_message_text(f"✅ Запись {row_num} удалена!", reply_markup=admin_back_button())
            else:
                await query.edit_message_text("❌ Ошибка удаления.", reply_markup=admin_back_button())
        
        # АДМИН: РЕДАКТИРОВАТЬ
        elif data == "admin_edit":
            context.user_data["admin_action"] = "edit"
            await query.edit_message_text(
                "✏️ **Редактирование**\n\n"
                "Введите номер строки и новые данные:\n"
                `5, Иванов Иван, Инженер, Москва, 31.12.2025`\n\n"
                "Или отправьте /cancel для отмены",
                reply_markup=admin_back_button(),
                parse_mode='Markdown'
            )
        
        elif data == "noop":
            pass
    
    except Exception as e:
        logger.error(f"❌ Ошибка в callback: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка. Попробуйте ещё раз.", reply_markup=main_menu())

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Сохраняем как админ если ID совпадает
    is_admin_user = is_admin(user_id)
    save_chat_id(chat_id, is_admin=is_admin_user)
    
    if is_admin_user:
        await update.message.reply_text(
            f"👋 Привет, Администратор!\n\n"
            f"Выбери действие 👇",
            reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            f"👋 Привет, {update.effective_user.first_name}!\n\n"
            f"Выбери действие 👇",
            reply_markup=main_menu()
        )
    
    logger.info(f"✅ Команда /start от пользователя {user_id}")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ваш Telegram ID"""
    await update.message.reply_text(f"Ваш Telegram ID: `{update.effective_user.id}`", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает админ-панель"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён. Только для администратора.")
        return
    await update.message.reply_text("🔧 Админ-панель", reply_markup=admin_menu())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text(build_stats_text(), parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущее действие"""
    context.user_data.clear()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=main_menu())

# ================== СООБЩЕНИЯ ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Поиск
    if context.user_data.get("search"):
        context.user_data["search"] = False
        try:
            result = [
                f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}"
                for r in get_data()
                if text.lower() in r.get("ФИО", "").lower()
            ]
            await update.message.reply_text(
                "\n\n".join(result[:50]) or "❌ Ничего не найдено",
                reply_markup=main_menu()
            )
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            await update.message.reply_text("⚠️ Ошибка при поиске.", reply_markup=main_menu())
        return
    
    # Админ: Добавление
    if context.user_data.get("admin_action") == "add":
        context.user_data["admin_action"] = None
        try:
            # Парсим ввод: ФИО, Должность, Город, Дата
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 4:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: ФИО, Должность, Город, Дата\n/cancel для отмены",
                    reply_markup=admin_back_button()
                )
                return
            
            data = {
                "ФИО": parts[0],
                "Должность": parts[1],
                "Город": parts[2],
                "Дата окончания": parts[3]
            }
            
            success = await admin_add_record(update, context, data)
            if success:
                await update.message.reply_text("✅ Запись добавлена!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("❌ Ошибка добавления.", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"❌ Ошибка добавления: {e}")
            await update.message.reply_text("⚠️ Ошибка. Попробуйте ещё раз.", reply_markup=admin_menu())
        return
    
    # Админ: Редактирование
    if context.user_data.get("admin_action") == "edit":
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
            sheet = get_sheet()
            
            # Обновляем ячейки
            for i, value in enumerate(parts[1:], 2):
                sheet.update_cell(row_num, i, value)
            
            await update.message.reply_text(f"✅ Строка {row_num} обновлена!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"❌ Ошибка редактирования: {e}")
            await update.message.reply_text("⚠️ Ошибка. Попробуйте ещё раз.", reply_markup=admin_menu())
        return
    
    # Обычное сообщение
    await update.message.reply_text(
        "Не понимаю команду. Используйте меню или /start",
        reply_markup=main_menu()
    )

# ================== УВЕДОМЛЕНИЯ ==================
async def notify(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневные уведомления"""
    chat_ids = get_chat_ids()
    if not chat_ids:
        logger.warning("⚠️ Нет chat_id для уведомлений")
        return
    
    text = build_status_text()
    
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"✅ Уведомление отправлено в чат {chat_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления в {chat_id}: {e}")

# ================== MAIN ==================
def main():
    # Валидация
    if not TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return
    if not SHEET_ID:
        logger.error("❌ SHEET_ID не найден!")
        return
    if not GOOGLE_CREDENTIALS:
        logger.error("❌ GOOGLE_CREDENTIALS не найден!")
        return
    if not ADMIN_IDS or ADMIN_IDS == [0]:
        logger.warning("⚠️ ADMIN_IDS не настроен! Первый /start зарегистрирует админа.")
    
    logger.info("🔥 ECP BOT VERSION 2.0 (ADMIN + LOGGING)")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # Обработчики
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Уведомления
    hour, minute = map(int, NOTIFY_TIME.split(":"))
    app.job_queue.run_daily(notify, time=time(hour=hour, minute=minute))
    
    logger.info(f"🚀 BOT STARTED (notify at {NOTIFY_TIME})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
