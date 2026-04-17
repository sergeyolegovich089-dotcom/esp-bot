import os
import json
import logging
from datetime import datetime, time, timedelta

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
NOTIFY_TIME = os.getenv("NOTIFY_TIME", "09:00")

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

def get_all_data():
    sheet = get_sheet()
    if not sheet:
        return []
    try:
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Ошибка чтения: {e}")
        return []

def get_all_rows():
    """Получаем все строки с номерами"""
    sheet = get_sheet()
    if not sheet:
        return []
    try:
        return sheet.get_all_values()
    except Exception as e:
        logger.error(f"Ошибка чтения строк: {e}")
        return []

# ================== АДМИН ==================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS_LIST

# ================== ДАТЫ ==================
def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except:
            continue
    return None

def days_until_end(date_str):
    """Считаем дни до окончания"""
    end_date = parse_date(date_str)
    if not end_date:
        return None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (end_date - today).days

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
        [InlineKeyboardButton("📅 Продлить ЦЭП", callback_data="admin_extend")],
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

# ================== СТАТУСЫ ==================
def build_status_text():
    data = get_all_data()
    today = datetime.now()
    red, orange, yellow, green = [], [], [], []
    
    for row in data:
        days = days_until_end(row.get("Дата окончания", ""))
        if days is None:
            continue
        
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
        text += f"🔴🔴 ПРОСРОЧЕНО 🚨 ({len(red)})\n\n" + "\n\n".join(red) + "\n\n"
    if orange:
        text += f"🟠 СРОЧНО ⚠️ ({len(orange)})\n\n" + "\n\n".join(orange) + "\n\n"
    if yellow:
        text += f"🟡 ВНИМАНИЕ ({len(yellow)})\n\n" + "\n\n".join(yellow) + "\n\n"
    if green:
        text += f"🟢 В НОРМЕ ({len(green)})\n"
    
    return text.strip() if text else "😎 Всё под контролем"

def build_stats_text():
    data = get_all_data()
    today = datetime.now()
    
    total = len(data)
    expired = urgent = warning = normal = 0
    cities = set()
    
    for row in data:
        days = days_until_end(row.get("Дата окончания", ""))
        if days is None:
            continue
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
    
    return (
        f"📊 СТАТИСТИКА\n\n"
        f"📋 Всего: {total}\n"
        f"🟢 В норме: {normal}\n"
        f"🟡 Внимание: {warning}\n"
        f"🟠 Срочно: {urgent}\n"
        f"🔴 Просрочено: {expired}\n\n"
        f"🏙 Городов: {len(cities)}\n"
        f"📅 {today.strftime('%d.%m.%Y %H:%M')}"
    )

# ================== УВЕДОМЛЕНИЯ ==================
def check_and_notify():
    """Проверяет сроки и отправляет уведомления"""
    sheet = get_sheet()
    if not sheet:
        return []
    
    rows = get_all_rows()
    if not rows:
        return []
    
    headers = rows[0]
    notifications = []
    
    # Находим индексы колонок
    try:
        idx_fio = headers.index("ФИО")
        idx_position = headers.index("Должность")
        idx_city = headers.index("Город")
        idx_end = headers.index("Дата окончания")
        idx_status = headers.index("Статус")
        idx_notify = headers.index("Уведомление")
        idx_extended = headers.index("Продлено")
    except ValueError as e:
        logger.error(f"Не найдена колонка: {e}")
        return []
    
    today = datetime.now()
    
    for row_num, row in enumerate(rows[1:], 2):  # Начинаем с строки 2
        if len(row) <= idx_end:
            continue
        
        fio = row[idx_fio] if idx_fio < len(row) else ""
        position = row[idx_position] if idx_position < len(row) else ""
        city = row[idx_city] if idx_city < len(row) else ""
        end_date_str = row[idx_end]
        current_notify = row[idx_notify] if idx_notify < len(row) else "нет"
        status = row[idx_status] if idx_status < len(row) else ""
        
        # Если уже продлён - пропускаем
        if status == "extended":
            continue
        
        days = days_until_end(end_date_str)
        if days is None:
            continue
        
        # Определяем какое уведомление отправлять
        notify_type = None
        
        if days == 30 and current_notify not in ["30", "14", "7", "expired"]:
            notify_type = "30"
        elif days == 14 and current_notify not in ["14", "7", "expired"]:
            notify_type = "14"
        elif days == 7 and current_notify not in ["7", "expired"]:
            notify_type = "7"
        elif days <= 0 and current_notify != "expired":
            notify_type = "expired"
        
        if notify_type:
            # Формируем сообщение
            if notify_type == "30":
                msg = (
                    f"⚠️ ПЛАНИРОВАНИЕ\n\n"
                    f"Через 30 дней истекает ЦЭП:\n"
                    f"👤 {fio}\n"
                    f"🏢 {position}\n"
                    f"🏙 {city}\n"
                    f"📅 Истекает: {end_date_str}"
                )
            elif notify_type == "14":
                msg = (
                    f"🟠 ВНИМАНИЕ\n\n"
                    f"Через 2 недели истекает ЦЭП:\n"
                    f"👤 {fio}\n"
                    f"🏢 {position}\n"
                    f"🏙 {city}\n"
                    f"📅 Истекает: {end_date_str}"
                )
            elif notify_type == "7":
                msg = (
                    f"🚨 СРОЧНО!\n\n"
                    f"Через 7 дней истекает ЦЭП:\n"
                    f"👤 {fio}\n"
                    f"🏢 {position}\n"
                    f"🏙 {city}\n"
                    f"📅 Истекает: {end_date_str}"
                )
            elif notify_type == "expired":
                msg = (
                    f"❌ ПРОСРОЧЕНО!\n\n"
                    f"Истёк ЦЭП:\n"
                    f"👤 {fio}\n"
                    f"🏢 {position}\n"
                    f"🏙 {city}\n"
                    f"📅 Истёк: {end_date_str}\n"
                    f"⏰ Просрочено: {abs(days)} дн."
                )
            
            notifications.append({
                "row": row_num,
                "message": msg,
                "notify_type": notify_type,
                "fio": fio
            })
            
            # Обновляем столбец G (Уведомление)
            try:
                sheet.update_cell(row_num, idx_notify + 1, notify_type)
                logger.info(f"✅ Уведомление {notify_type} для {fio} (строка {row_num})")
            except Exception as e:
                logger.error(f"Ошибка обновления уведомления: {e}")
    
    return notifications

# ================== ПРОДЛЕНИЕ ==================
def extend_certificate(row_num, new_date):
    """Отмечает сертификат как продлённый"""
    sheet = get_sheet()
    if not sheet:
        return False
    
    try:
        headers = get_all_rows()[0]
        idx_status = headers.index("Статус")
        idx_notify = headers.index("Уведомление")
        idx_extended = headers.index("Продлено")
        
        # Обновляем колонки
        sheet.update_cell(row_num, idx_status + 1, "extended")
        sheet.update_cell(row_num, idx_notify + 1, "none")
        sheet.update_cell(row_num, idx_extended + 1, new_date)
        
        logger.info(f"✅ Продлено: строка {row_num}, новая дата: {new_date}")
        return True
    except Exception as e:
        logger.error(f"Ошибка продления: {e}")
        return False

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    try:
        # Проверка админа
        if data.startswith("admin") and not is_admin(user_id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        
        # Меню
        if data == "menu":
            await query.edit_message_text("Выбери действие 👇", reply_markup=main_menu())
        
        # Админ меню
        elif data == "admin":
            await query.edit_message_text("🔧 Админ-панель", reply_markup=admin_menu())
        
        # Города
        elif data == "cities":
            cities = sorted({r.get("Город") for r in get_all_data() if r.get("Город")})
            buttons = [[InlineKeyboardButton(c, callback_data=f"city:{c}")] for c in cities]
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
            await query.edit_message_text("🏙 Выбери город:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("city:"):
            city = data.split(":")[1].lower()
            result = [f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}" for r in get_all_data() if city in r.get("Город", "").lower()]
            await query.edit_message_text("\n\n".join(result[:50]) or "❌ Ничего не найдено", reply_markup=back_button())
        
        # Месяцы
        elif data == "months":
            months = [("Янв",1),("Фев",2),("Мар",3),("Апр",4),("Май",5),("Июн",6),("Июл",7),("Авг",8),("Сен",9),("Окт",10),("Ноя",11),("Дек",12)]
            buttons = [[InlineKeyboardButton(m[0], callback_data=f"month:{m[1]}") for m in months[i:i+3]] for i in range(0, 12, 3)]
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
            await query.edit_message_text("📅 Выбери месяц:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("month:"):
            month = int(data.split(":")[1])
            result = [f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}" for r in get_all_data() if parse_date(r.get("Дата окончания", "")).month == month if parse_date(r.get("Дата окончания", ""))]
            await query.edit_message_text("\n\n".join(result[:50]) or "❌ Ничего не найдено", reply_markup=back_button())
        
        # Все записи
        elif data == "all":
            result = [f"🏙 {r.get('Город')}\n👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n📅 {r.get('Дата окончания')}" for r in get_all_data()]
            await query.edit_message_text(f"📋 Записей: {len(result)}\n\n" + "\n\n".join(result[:50]) or "Нет данных", reply_markup=back_button())
        
        # Проверка
        elif data == "check":
            await query.edit_message_text(build_status_text(), reply_markup=back_button())
        
        # Статистика
        elif data == "stats":
            if not is_admin(user_id):
                await query.edit_message_text("⛔ Только для админа.")
                return
            await query.edit_message_text(build_stats_text(), reply_markup=admin_back_button())
        
        # Админ: Продлить
        elif data == "admin_extend":
            rows = get_all_rows()
            if not rows:
                await query.edit_message_text("❌ Нет данных", reply_markup=admin_back_button())
                return
            
            headers = rows[0]
            try:
                idx_fio = headers.index("ФИО")
                idx_end = headers.index("Дата окончания")
                idx_notify = headers.index("Уведомление")
            except:
                await query.edit_message_text("❌ Ошибка структуры таблицы", reply_markup=admin_back_button())
                return
            
            # Показываем только те у кого скоро истекает
            buttons = []
            for row_num, row in enumerate(rows[1:], 2):
                if len(row) <= idx_end:
                    continue
                notify = row[idx_notify] if idx_notify < len(row) else "нет"
                if notify in ["30", "14", "7", "expired"]:
                    fio = row[idx_fio] if idx_fio < len(row) else "N/A"
                    end = row[idx_end] if idx_end < len(row) else ""
                    buttons.append([InlineKeyboardButton(f"{row_num}. {fio} ({end})", callback_data=f"extend_select:{row_num}")])
            
            if not buttons:
                await query.edit_message_text("✅ Нет записей требующих продления", reply_markup=admin_back_button())
            else:
                buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin")])
                await query.edit_message_text("📅 Выберите запись для продления:", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("extend_select:"):
            row_num = int(data.split(":")[1])
            context.user_data["extend_row"] = row_num
            context.user_data["admin_action"] = "extend"
            await query.edit_message_text(
                f"✏️ Продление ЦЭП (строка {row_num})\n\n"
                f"Введите новую дату окончания:\n"
                f"Пример: 2027-07-26\n\n"
                f"Или /cancel для отмены",
                reply_markup=admin_back_button()
            )
        
        # Админ: Добавить
        elif data == "admin_add":
            context.user_data["admin_action"] = "add"
            await query.edit_message_text(
                "➕ Добавление\n\n"
                "Введите: ФИО, Должность, Город, Дата начала, Дата окончания\n"
                "Пример: Иванов Иван, Инженер, Москва, 2025-01-01, 2026-01-01\n\n"
                "Или /cancel",
                reply_markup=admin_back_button()
            )
        
        # Админ: Удалить
        elif data == "admin_delete":
            rows = get_all_rows()
            buttons = [[InlineKeyboardButton(f"{i}. {row[0]}", callback_data=f"admin_del_confirm:{i}")] for i, row in enumerate(rows[1:], 2) if row]
            buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin")])
            await query.edit_message_text("🗑 Удаление (выберите строку):", reply_markup=InlineKeyboardMarkup(buttons))
        
        elif data.startswith("admin_del_confirm:"):
            row_num = int(data.split(":")[1])
            sheet = get_sheet()
            if sheet:
                sheet.delete_rows(row_num)
                await query.edit_message_text(f"✅ Строка {row_num} удалена!", reply_markup=admin_back_button())
        
        # Админ: Редактировать
        elif data == "admin_edit":
            context.user_data["admin_action"] = "edit"
            await query.edit_message_text(
                "✏️ Редактирование\n\n"
                "Введите: Номер, ФИО, Должность, Город, Дата начала, Дата окончания\n"
                "Пример: 5, Иванов Иван, Инженер, Москва, 2025-01-01, 2026-01-01\n\n"
                "Или /cancel",
                reply_markup=admin_back_button()
            )
    
    except Exception as e:
        logger.error(f"Callback ошибка: {e}")
        await query.edit_message_text("⚠️ Ошибка. /start", reply_markup=main_menu())

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        keyboard = main_menu()
        keyboard.inline_keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin")])
        await update.message.reply_text(f"👋 Привет, Админ!\n\nВыбери действие:", reply_markup=keyboard)
    else:
        await update.message.reply_text(f"👋 Привет!\n\nВыбери действие:", reply_markup=main_menu())
    logger.info(f"/start от {user_id}")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш ID: `{update.effective_user.id}`", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(user_id := update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text("🔧 Админ-панель", reply_markup=admin_menu())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text(build_stats_text())

async def test_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    notifications = check_and_notify()
    if notifications:
        await update.message.reply_text(f"🔔 Найдено уведомлений: {len(notifications)}")
        for n in notifications[:5]:
            await update.message.reply_text(n["message"])
    else:
        await update.message.reply_text("✅ Уведомлений нет")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.", reply_markup=main_menu())

# ================== СООБЩЕНИЯ ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Поиск
    if context.user_data.get("search"):
        context.user_data["search"] = False
        result = [f"👤 {r.get('ФИО')}\n🏢 {r.get('Должность')}\n🏙 {r.get('Город')}\n📅 {r.get('Дата окончания')}" for r in get_all_data() if text.lower() in r.get("ФИО", "").lower()]
        await update.message.reply_text("\n\n".join(result[:50]) or "❌ Ничего не найдено", reply_markup=main_menu())
        return
    
    # Продление
    if context.user_data.get("admin_action") == "extend":
        if not is_admin(user_id):
            return
        context.user_data["admin_action"] = None
        row_num = context.user_data.get("extend_row")
        if row_num:
            success = extend_certificate(row_num, text.strip())
            await update.message.reply_text(f"{'✅ Продлено!' if success else '❌ Ошибка'}", reply_markup=admin_menu())
        return
    
    # Добавление
    if context.user_data.get("admin_action") == "add":
        if not is_admin(user_id):
            return
        context.user_data["admin_action"] = None
        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) >= 5:
                sheet = get_sheet()
                sheet.append_row([parts[0], parts[1], parts[2], parts[3], parts[4], "active", "none", ""])
                await update.message.reply_text("✅ Добавлено!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("❌ Неверный формат", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            await update.message.reply_text("❌ Ошибка", reply_markup=admin_menu())
        return
    
    # Редактирование
    if context.user_data.get("admin_action") == "edit":
        if not is_admin(user_id):
            return
        context.user_data["admin_action"] = None
        try:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) >= 6:
                sheet = get_sheet()
                row_num = int(parts[0])
                for i, val in enumerate(parts[1:], 1):
                    sheet.update_cell(row_num, i, val)
                await update.message.reply_text(f"✅ Строка {row_num} обновлена!", reply_markup=admin_menu())
            else:
                await update.message.reply_text("❌ Неверный формат", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка редактирования: {e}")
            await update.message.reply_text("❌ Ошибка", reply_markup=admin_menu())
        return
    
    await update.message.reply_text("Используйте меню или /start", reply_markup=main_menu())

# ================== ЕЖЕДНЕВНЫЕ УВЕДОМЛЕНИЯ ==================
async def daily_notify(context: ContextTypes.DEFAULT_TYPE):
    chat_ids = ADMIN_IDS_LIST
    if not chat_ids:
        return
    
    notifications = check_and_notify()
    for n in notifications:
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=n["message"])
                logger.info(f"🔔 Уведомление отправлено: {n['fio']}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

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
    
    logger.info("🔥 ECP BOT v3.0 (SMART REMINDERS)")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("testnotify", test_notify))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Ежедневные уведомления в 09:00
    hour, minute = map(int, NOTIFY_TIME.split(":"))
    app.job_queue.run_daily(daily_notify, time=time(hour=hour, minute=minute))
    
    logger.info(f"🚀 BOT STARTED (уведомления в {NOTIFY_TIME})")
    app.run_polling()

if __name__ == "__main__":
    main()
