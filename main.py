"""
Главный модуль запуска Telegram бота.

Запуск:
    python main.py

Перед запуском:
    1. Создайте .env файл на основе .env.example
    2. Заполните TELEGRAM_BOT_TOKEN и OPENAI_API_KEY
    3. Убедитесь, что prompts.json существует
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import config
from bot.handlers import router, setup_handlers


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная функция запуска бота."""
    
    print("=" * 50)
    print("Запуск Telegram бота")
    print("=" * 50)
    
    # Инициализация хендлеров (загрузка prompts, создание memory store)
    setup_handlers()
    
    # Создание бота и диспетчера
    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация роутера
    dp.include_router(router)
    
    print("=" * 50)
    print("Бот запущен! Нажмите Ctrl+C для остановки.")
    print("=" * 50)
    
    # Запуск polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен.")
