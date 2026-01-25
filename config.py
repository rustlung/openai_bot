"""
Модуль конфигурации.
Загружает настройки из .env файла и предоставляет их приложению.
"""

import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


@dataclass
class Config:
    """Конфигурация приложения."""
    
    # Обязательные
    telegram_bot_token: str
    openai_api_key: str
    
    # Необязательные (с дефолтами)
    openai_model: str = "gpt-4"
    history_pairs_limit: int = 5
    memory_file_path: str = "data/memory.json"
    usd_rub_rate: float = 92.50


def load_config() -> Config:
    """
    Загружает конфигурацию из переменных окружения.
    Выбрасывает SystemExit с понятным сообщением, если обязательные переменные не заданы.
    """
    # Проверяем обязательные переменные
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    missing = []
    if not telegram_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    
    if missing:
        print("=" * 50)
        print("ОШИБКА КОНФИГУРАЦИИ")
        print("=" * 50)
        print(f"Не заданы обязательные переменные окружения:")
        for var in missing:
            print(f"  - {var}")
        print()
        print("Создайте файл .env на основе .env.example и заполните его.")
        print("=" * 50)
        sys.exit(1)
    
    # Загружаем необязательные с дефолтами
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # HISTORY_PAIRS_LIMIT — целое число
    try:
        history_pairs_limit = int(os.getenv("HISTORY_PAIRS_LIMIT", "5"))
    except ValueError:
        print("ПРЕДУПРЕЖДЕНИЕ: HISTORY_PAIRS_LIMIT должен быть числом. Используется значение по умолчанию: 5")
        history_pairs_limit = 5
    
    memory_file_path = os.getenv("MEMORY_FILE_PATH", "data/memory.json")
    
    # USD_RUB_RATE — число с плавающей точкой
    try:
        usd_rub_rate = float(os.getenv("USD_RUB_RATE", "92.50"))
    except ValueError:
        print("ПРЕДУПРЕЖДЕНИЕ: USD_RUB_RATE должен быть числом. Используется значение по умолчанию: 92.50")
        usd_rub_rate = 92.50
    
    return Config(
        telegram_bot_token=telegram_token,
        openai_api_key=openai_key,
        openai_model=openai_model,
        history_pairs_limit=history_pairs_limit,
        memory_file_path=memory_file_path,
        usd_rub_rate=usd_rub_rate,
    )


# Глобальный экземпляр конфигурации (создаётся при импорте)
config = load_config()
