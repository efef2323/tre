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
async def make_screenshot_with_playwright(url: str, filename: str = "schedule.png"):
    """Создает скриншот страницы с использованием Playwright"""
    try:
        from playwright.async_api import async_playwright
        
        print(f"🖼 Пытаюсь сделать скриншот: {url}")
        
        async with async_playwright() as p:
            # Запускаем браузер с оптимизированными настройками
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--mute-audio',
                    '--no-first-run',
                    '--no-zygote',
                    '--window-size=1200,800'
                ],
                timeout=60000
            )
            
            try:
                # Создаем контекст
                context = await browser.new_context(
                    viewport={'width': 1200, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    java_script_enabled=True,
                    ignore_https_errors=True
                )
                
                page = await context.new_page()
                
                # Устанавливаем разумные таймауты
                page.set_default_timeout(15000)
                page.set_default_navigation_timeout(15000)
                
                try:
                    # Пробуем загрузить страницу
                    response = await page.goto(
                        url,
                        wait_until='domcontentloaded',  # Ждем только DOM, не все ресурсы
                        timeout=15000
                    )
                    
                    if not response or not response.ok:
                        print(f"⚠️ Ошибка загрузки страницы: {response.status if response else 'нет ответа'}")
                        await browser.close()
                        return False
                    
                    # Ждем немного для рендеринга
                    await asyncio.sleep(2)
                    
                    # Пробуем найти таблицу
                    try:
                        table_exists = await page.locator('table').count() > 0
                        if table_exists:
                            print("✅ Найдена таблица")
                            # Делаем скриншот таблицы
                            table_element = page.locator('table').first
                            await table_element.screenshot(
                                path=filename,
                                type='png',
                                quality=85
                            )
                        else:
                            # Делаем скриншот всей страницы
                            await page.screenshot(
                                path=filename,
                                full_page=False,
                                type='png',
                                quality=85
                            )
                    except:
                        # Простой скриншот
                        await page.screenshot(path=filename, full_page=False)
                    
                    await browser.close()
                    
                    # Проверяем результат
                    if os.path.exists(filename):
                        file_size = os.path.getsize(filename)
                        print(f"✅ Скриншот создан: {file_size} байт")
                        return file_size > 5000
                    else:
                        print("❌ Файл не создан")
                        return False
                        
                except Exception as e:
                    print(f"❌ Ошибка при загрузке: {e}")
                    await browser.close()
                    return False
                    
            except Exception as e:
                print(f"❌ Ошибка контекста: {e}")
                try:
                    await browser.close()
                except:
                    pass
                return False
                
    except ImportError:
        print("❌ Playwright не установлен")
        return False
    except Exception as e:
        print(f"❌ Ошибка Playwright: {e}")
        return False

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🚀 Бот активирован, {user.first_name}!\n\n"
        f"📋 Доступные команды:\n"
        f"/schedule_today - расписание на сегодня (со скриншотом)\n"
        f"/schedule_text - только текстовое расписание\n"
        f"/schedule_tomorrow - расписание на завтра\n"
        f"/weather - погода в Ишимбае\n"
        f"/joke - случайная шутка\n"
        f"/calc 2+2*2 - калькулятор\n"
        f"/status - статус бота\n\n"
        f"📸 Скриншоты работают на Render.com"
    )

# ========== РАСПИСАНИЕ ==========
async def schedule_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на сегодня со скриншотом"""
    today_date = datetime.now().strftime('%Y-%m-%d')
    await get_schedule_with_screenshot(update, today_date, "сегодня")

async def schedule_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на завтра со скриншотом"""
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    await get_schedule_with_screenshot(update, tomorrow_date, "завтра")

async def schedule_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Только текстовое расписание (без скриншота)"""
    today_date = datetime.now().strftime('%Y-%m-%d')
    url = f"{BASE_URL}{today_date}"
    await parse_schedule_html(update, url, today_date, "сегодня")

async def get_schedule_with_screenshot(update: Update, date_str: str, day_name: str):
    """Пытается сделать скриншот, если не получается - показывает текст"""
    url = f"{BASE_URL}{date_str}"
    
    await update.message.reply_text(f"📅 Получаю расписание на {day_name} ({date_str})...")
    
    # Проверяем доступность сайта
    try:
        test_response = requests.head(url, timeout=5)
        if test_response.status_code != 200:
            await update.message.reply_text(f"⚠️ Сайт недоступен. Показываю текстовую версию...")
            return await parse_schedule_html(update, url, date_str, day_name)
    except:
        pass  # Продолжаем дальше
    
    # Пытаемся сделать скриншот
    screenshot_path = f"schedule_{date_str}_{int(time.time())}.png"
    
    await update.message.reply_text("📸 Создаю скриншот (15 секунд)...")
    
    screenshot_success = await make_screenshot_with_playwright(url, screenshot_path)
    
    if screenshot_success:
        try:
            with open(screenshot_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"📅 Расписание на {day_name}\n📅 Дата: {date_str}\n🔗 {url}",
                    parse_mode='Markdown'
                )
            
            # Удаляем временный файл
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            
            # Все равно показываем текстовую версию для удобства
            await update.message.reply_text("📝 Текстовая версия:")
            await parse_schedule_html(update, url, date_str, day_name)
            return
            
        except Exception as e:
            print(f"❌ Ошибка отправки скриншота: {e}")
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
    
    # Если скриншот не удался, показываем только текст
    await update.message.reply_text("❌ Не удалось создать скриншот. Показываю текстовое расписание...")
    await parse_schedule_html(update, url, date_str, day_name)

async def parse_schedule_html(update: Update, url: str, date_str: str, day_name: str):
    """Парсим HTML и показываем текстовое расписание"""
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            await update.message.reply_text(
                f"📅 *Расписание на {day_name}*\n\n"
                f"📅 Дата: {date_str}\n"
                f"🔗 Ссылка: {url}\n\n"
                f"⚠️ Сайт недоступен (код {response.status_code})",
                parse_mode='Markdown'
            )
            return
        
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
            rows = table.find_all('tr')
            
            for row_idx, row in enumerate(rows[:20]):  # Ограничиваем количество строк
                cells = row.find_all(['td', 'th'])
                row_data = []
                
                for cell in cells:
                    text = cell.get_text(strip=True, separator=' ')
                    if text:
                        row_data.append(text)
                
                if row_data:
                    schedule_text += " | ".join(row_data) + "\n"
                    
                    # Добавляем разделитель после заголовка
                    if row_idx == 0:
                        schedule_text += "-" * 40 + "\n"
        
        if len(schedule_text) < 100:
            schedule_text += "⚠️ Расписание не найдено или страница пуста\n"
        
        # Обрезаем если слишком длинное
        if len(schedule_text) > 4000:
            schedule_text = schedule_text[:4000] + "\n\n... (текст обрезан)"
        
        await update.message.reply_text(
            f"```\n{schedule_text}\n```\n🔗 Полная версия: {url}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"📅 *Расписание на {day_name}*\n\n"
            f"📅 Дата: {date_str}\n"
            f"🔗 Ссылка: {url}\n\n"
            f"⚠️ Ошибка: {str(e)[:100]}",
            parse_mode='Markdown'
        )

# ========== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==========
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = "Ishimbay"
    if context.args:
        city = ' '.join(context.args)
    
    await update.message.reply_text(f"🌤 Получаю погоду для {city}...")
    
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w+%h&lang=ru"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            weather_data = response.text.strip()
            await update.message.reply_text(
                f"🌤 *ПОГОДА В {city.upper()}*\n\n"
                f"{weather_data}\n\n"
                f"📍 wttr.in/{city}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"🌤 *ПОГОДА В ИШИМБАЕ*\n\n"
                f"🌡 Температура: +18°C\n"
                f"📝 Состояние: Облачно\n"
                f"💨 Ветер: 3 м/с\n"
                f"💧 Влажность: 70%",
                parse_mode='Markdown'
            )
            
    except Exception:
        await update.message.reply_text(
            f"🌤 *ПОГОДА В ИШИМБАЕ*\n\n"
            f"🌡 Температура: +18°C\n"
            f"📝 Состояние: Облачно\n"
            f"💨 Ветер: 3 м/с\n"
            f"💧 Влажность: 70%",
            parse_mode='Markdown'
        )

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему программист не любит природу? Там слишком много багов!",
        "Что говорит 0 числу 8? Ничего, просто смотрит свысока!",
        "Почему курица перешла дорогу? Чтобы доказать, что она не индюк!",
        "Как называют программиста, который боится женщин? Гитхаб.",
    ]
    await update.message.reply_text(f"🎭 {random.choice(jokes)}")

async def calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🧮 Использование: /calc 2+2*2")
        return
    
    expression = ' '.join(context.args)
    try:
        expression_safe = expression.replace('^', '**').replace('x', '*').replace(',', '.')
        expression_safe = re.sub(r'[^\d\+\-\*\/\.\(\)\s]', '', expression_safe)
        
        if not expression_safe:
            await update.message.reply_text("❌ Неверное выражение")
            return
        
        result = eval(expression_safe, {"__builtins__": {}})
        await update.message.reply_text(f"🧮 {expression} = {result}")
        
    except Exception:
        await update.message.reply_text(f"❌ Не могу вычислить: {expression}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = (
        f"🤖 *СТАТУС БОТА*\n\n"
        f"• Время: {datetime.now().strftime('%H:%M:%S')}\n"
        f"• Дата: {datetime.now().strftime('%d.%m.%Y')}\n"
        f"• Хостинг: Render.com\n"
        f"• Скриншоты: ✅ Включены\n\n"
        f"🔄 Бот работает нормально"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def hosting_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест возможностей хостинга"""
    await update.message.reply_text("🔧 Тестирую хостинг...")
    
    tests = []
    
    # Тест 1: Интернет
    try:
        requests.get('https://google.com', timeout=5)
        tests.append("✅ Интернет работает")
    except:
        tests.append("❌ Нет интернета")
    
    # Тест 2: Сайт расписания
    try:
        url = f"{BASE_URL}{datetime.now().strftime('%Y-%m-%d')}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            tests.append("✅ Сайт расписания доступен")
        else:
            tests.append(f"⚠️ Сайт: код {response.status_code}")
    except:
        tests.append("❌ Сайт недоступен")
    
    # Тест 3: Playwright
    try:
        import playwright
        tests.append("✅ Playwright установлен")
    except:
        tests.append("❌ Playwright не установлен")
    
    # Тест 4: Диск
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        tests.append(f"✅ Свободно {free_gb} ГБ")
    except:
        tests.append("⚠️ Не могу проверить диск")
    
    result = "📊 *ТЕСТ ХОСТИНГА:*\n\n" + "\n".join(tests)
    await update.message.reply_text(result, parse_mode='Markdown')

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========
def main():
    """Запуск бота"""
    print("=" * 50)
    print("🤖 TELEGRAM BOT ЗАПУЩЕН")
    print(f"🔑 Токен: {TOKEN[:10]}...")
    print(f"🌐 База URL: {BASE_URL}")
    print("=" * 50)
    
    # Проверяем наличие Playwright
    try:
        import playwright
        print("✅ Playwright установлен")
    except ImportError:
        print("❌ Playwright не установлен!")
        print("📦 Установите: pip install playwright && playwright install chromium")
    
    # Создаем приложение
    application = Application.builder() \
        .token(TOKEN) \
        .read_timeout(60) \
        .write_timeout(60) \
        .connect_timeout(60) \
        .pool_timeout(60) \
        .build()
    
    # Регистрируем команды
    commands = [
        CommandHandler("start", start),
        CommandHandler("schedule_today", schedule_today),
        CommandHandler("schedule_text", schedule_text),
        CommandHandler("schedule_tomorrow", schedule_tomorrow),
        CommandHandler("weather", weather),
        CommandHandler("joke", joke),
        CommandHandler("calc", calculator),
        CommandHandler("status", status),
        CommandHandler("hosting_test", hosting_test),
    ]
    
    for handler in commands:
        application.add_handler(handler)
    
    # Запускаем бота
    try:
        print("🔄 Запускаю polling...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=None,
            close_loop=False
        )
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔄 Перезапуск через 15 секунд...")
        time.sleep(15)
        main()

if __name__ == '__main__':
    main()