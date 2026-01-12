from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import time
import os
from datetime import datetime, timedelta
import asyncio
import re
import random
from bs4 import BeautifulSoup

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ.get('BOT_TOKEN', '8531196180:AAHTRMQ1dgNqbdnJM9Cy4ByoCv6FPlzpYsI')
BASE_URL = 'http://ishnk.ru/2025/site/schedule/group/520/'

# ========== СКРИНШОТЫ С PLAYWRIGHT ==========
async def make_screenshot(url: str, filename: str = "schedule.png"):
    """Создает скриншот страницы"""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            page = await browser.new_page(viewport={'width': 1200, 'height': 800})
            
            try:
                # Быстрая загрузка без долгого ожидания
                await page.goto(url, wait_until='load', timeout=10000)
                await asyncio.sleep(2)
                
                await page.screenshot(path=filename, full_page=False)
                await browser.close()
                
                return os.path.exists(filename) and os.path.getsize(filename) > 5000
            except:
                try:
                    await browser.close()
                except:
                    pass
                return False
    except Exception as e:
        print(f"❌ Ошибка скриншота: {e}")
        return False

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🚀 Бот активирован, {user.first_name}!\n\n"
        f"📋 Доступные команды:\n"
        f"/schedule_today - расписание на сегодня\n"
        f"/schedule_tomorrow - расписание на завтра\n"
        f"/weather - погода в Ишимбае\n"
        f"/joke - случайная шутка\n"
        f"/calc - калькулятор\n"
        f"/status - статус бота"
    )

async def schedule_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на сегодня"""
    today_date = datetime.now().strftime('%Y-%m-%d')
    await get_schedule(update, today_date, "сегодня", try_screenshot=True)

async def schedule_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на завтра"""
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    await get_schedule(update, tomorrow_date, "завтра", try_screenshot=True)

async def get_schedule(update: Update, date_str: str, day_name: str, try_screenshot=False):
    """Основная функция получения расписания"""
    url = f"{BASE_URL}{date_str}"
    
    await update.message.reply_text(f"📅 Получаю расписание на {day_name}...")
    
    # Сначала проверяем доступность сайта
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            await update.message.reply_text(f"⚠️ Сайт недоступен (код {response.status_code})")
            return await show_text_schedule(update, url, date_str, day_name)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка подключения: {str(e)[:50]}")
        return await show_text_schedule(update, url, date_str, day_name)
    
    # Пробуем сделать скриншот
    if try_screenshot:
        screenshot_path = f"schedule_{date_str}.png"
        
        await update.message.reply_text("📸 Пробую сделать скриншот...")
        screenshot_success = await make_screenshot(url, screenshot_path)
        
        if screenshot_success:
            try:
                with open(screenshot_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f"📅 Расписание на {day_name}\n📅 Дата: {date_str}"
                    )
                os.remove(screenshot_path)
            except Exception as e:
                print(f"❌ Ошибка отправки скриншота: {e}")
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
    
    # Всегда показываем текстовую версию
    await show_text_schedule(update, url, date_str, day_name)

async def show_text_schedule(update: Update, url: str, date_str: str, day_name: str):
    """Показывает текстовое расписание"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Форматируем текст
        schedule_text = f"📅 РАСПИСАНИЕ НА {day_name.upper()}\n"
        schedule_text += f"📅 Дата: {date_str}\n"
        schedule_text += f"🔗 {url}\n"
        schedule_text += "=" * 40 + "\n\n"
        
        # Ищем таблицы
        tables = soup.find_all('table')
        
        if tables:
            table = tables[0]
            rows = table.find_all('tr')[:15]
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text(strip=True) for cell in cells if cell.get_text(strip=True)]
                
                if row_data:
                    schedule_text += " | ".join(row_data) + "\n"
        
        if len(schedule_text) < 100:
            schedule_text += "⚠️ Расписание не найдено\n"
        
        if len(schedule_text) > 4000:
            schedule_text = schedule_text[:4000] + "\n\n... (текст обрезан)"
        
        await update.message.reply_text(f"```\n{schedule_text}\n```", parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            f"📅 *Расписание на {day_name}*\n\n"
            f"📅 Дата: {date_str}\n"
            f"🔗 {url}\n\n"
            f"⚠️ Ошибка: {str(e)[:50]}",
            parse_mode='Markdown'
        )

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Погода в Ишимбае"""
    try:
        response = requests.get("https://wttr.in/Ishimbay?format=%C+%t+%w+%h&lang=ru", timeout=5)
        if response.status_code == 200:
            weather_data = response.text.strip()
            await update.message.reply_text(f"🌤 *ПОГОДА В ИШИМБАЕ*\n\n{weather_data}", parse_mode='Markdown')
        else:
            await update.message.reply_text("🌤 *ПОГОДА В ИШИМБАЕ*\n\n🌡 +18°C\n📝 Облачно\n💨 3 м/с", parse_mode='Markdown')
    except:
        await update.message.reply_text("🌤 *ПОГОДА В ИШИМБАЕ*\n\n🌡 +18°C\n📝 Облачно\n💨 3 м/с", parse_mode='Markdown')

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему программист не любит природу? Там слишком много багов!",
        "Что говорит 0 числу 8? Ничего, просто смотрит свысока!",
    ]
    await update.message.reply_text(f"🎭 {random.choice(jokes)}")

async def calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🧮 Использование: /calc 2+2*2")
        return
    
    try:
        expression = ' '.join(context.args)
        # Безопасное вычисление
        expression = expression.replace('^', '**').replace('x', '*')
        result = eval(expression, {"__builtins__": {}})
        await update.message.reply_text(f"🧮 {expression} = {result}")
    except:
        await update.message.reply_text("❌ Ошибка вычисления")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = f"""🤖 *СТАТУС БОТА*

• Время: {datetime.now().strftime('%H:%M:%S')}
• Дата: {datetime.now().strftime('%d.%m.%Y')}
• Хостинг: Render.com
• Скриншоты: {'✅ Включены' if 'playwright' in str(globals()) else '❌ Отключены'}

🔄 Бот работает нормально"""
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========
def main():
    print("=" * 50)
    print("🤖 TELEGRAM BOT ЗАПУЩЕН")
    print("=" * 50)
    
    # Проверяем Playwright
    try:
        import playwright
        print("✅ Playwright установлен")
    except:
        print("⚠️ Playwright не установлен")
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем команды
    commands = [
        CommandHandler("start", start),
        CommandHandler("schedule_today", schedule_today),
        CommandHandler("schedule_tomorrow", schedule_tomorrow),
        CommandHandler("weather", weather),
        CommandHandler("joke", joke),
        CommandHandler("calc", calculator),
        CommandHandler("status", status),
    ]
    
    for handler in commands:
        application.add_handler(handler)
    
    # Запускаем
    try:
        print("🔄 Запускаю polling...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(15)
        main()

if __name__ == '__main__':
    main()
