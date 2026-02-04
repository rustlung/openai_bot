"""
Модуль конфигурации.
Загружает настройки из .env файла и предоставляет их приложению.
"""

import os
import sys
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


def _get_float(key: str, default: float) -> float:
    """Безопасно получает float из env."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {key} должен быть числом. Используется: {default}")
        return default


def _get_int(key: str, default: int) -> int:
    """Безопасно получает int из env."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {key} должен быть целым числом. Используется: {default}")
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    """Безопасно получает bool из env (1/true/yes = True)."""
    val = os.getenv(key, "1" if default else "0").lower()
    return val in ("1", "true", "yes", "on")


@dataclass
class Config:
    """Конфигурация приложения."""
    
    # === Обязательные ===
    telegram_bot_token: str
    openai_api_key: str
    
    # === Базовые настройки ===
    openai_model: str = "gpt-4"
    history_pairs_limit: int = 5
    memory_file_path: str = "data/memory.json"
    
    # === Billing: цены на текст (USD за 1M токенов) ===
    price_text_input_usd_per_1m: float = 2.50    # GPT-4o default
    price_text_output_usd_per_1m: float = 10.00  # GPT-4o default
    
    # === FX (курс валют) ===
    fx_api_url: str = "https://open.er-api.com/v6/latest/USD"
    fx_cache_file_path: str = "data/fx_cache.json"
    fx_cache_ttl_seconds: int = 21600  # 6 часов
    usd_rub_rate_fallback: float = 75.92  # Fallback если API недоступен
    
    # === Показ стоимости ===
    show_cost_each_reply: bool = False
    
    # === Image generation ===
    image_model: str = "gpt-image-1"
    image_size: str = "1024x1024"
    # Цены за изображение по размерам (USD)
    image_cost_usd_1024x1024: float = 0.011
    image_cost_usd_1024x1536: float = 0.016
    image_cost_usd_1536x1024: float = 0.016
    image_cost_usd_default: float = 0.011
    
    # === Video generation (Sora 2) ===
    # Модели: sora-2 (быстрее, $0.10/сек) или sora-2-pro (качественнее, $0.30/сек)
    # Размеры: 1280x720 (landscape) или 720x1280 (portrait)
    # Длительность: ТОЛЬКО 4, 8 или 12 секунд
    video_model: str = "sora-2"
    video_seconds: int = 4  # Допустимые значения: 4, 8, 12
    video_size: str = "1280x720"  # landscape
    video_cost_usd_per_second: float = 0.10  # $0.10 для sora-2, $0.30 для sora-2-pro
    video_poll_interval_seconds: int = 10  # Рекомендуется 10-20 сек
    video_max_wait_seconds: int = 300  # Видео может генерироваться несколько минут
    
    # === Debug ===
    debug_keep_media: bool = False


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
        print("Не заданы обязательные переменные окружения:")
        for var in missing:
            print(f"  - {var}")
        print()
        print("Создайте файл .env на основе .env.example и заполните его.")
        print("=" * 50)
        sys.exit(1)
    
    return Config(
        # Обязательные
        telegram_bot_token=telegram_token,
        openai_api_key=openai_key,
        
        # Базовые
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
        history_pairs_limit=_get_int("HISTORY_PAIRS_LIMIT", 5),
        memory_file_path=os.getenv("MEMORY_FILE_PATH", "data/memory.json"),
        
        # Billing: текст
        price_text_input_usd_per_1m=_get_float("PRICE_TEXT_INPUT_USD_PER_1M", 2.50),
        price_text_output_usd_per_1m=_get_float("PRICE_TEXT_OUTPUT_USD_PER_1M", 10.00),
        
        # FX
        fx_api_url=os.getenv("FX_API_URL", "https://open.er-api.com/v6/latest/USD"),
        fx_cache_file_path=os.getenv("FX_CACHE_FILE_PATH", "data/fx_cache.json"),
        fx_cache_ttl_seconds=_get_int("FX_CACHE_TTL_SECONDS", 21600),
        usd_rub_rate_fallback=_get_float("USD_RUB_RATE", 75.92),
        
        # Показ стоимости
        show_cost_each_reply=_get_bool("SHOW_COST_EACH_REPLY", False),
        
        # Image
        image_model=os.getenv("IMAGE_MODEL", "gpt-image-1"),
        image_size=os.getenv("IMAGE_SIZE", "1024x1024"),
        image_cost_usd_1024x1024=_get_float("IMAGE_COST_USD_1024x1024", 0.011),
        image_cost_usd_1024x1536=_get_float("IMAGE_COST_USD_1024x1536", 0.016),
        image_cost_usd_1536x1024=_get_float("IMAGE_COST_USD_1536x1024", 0.016),
        image_cost_usd_default=_get_float("IMAGE_COST_USD_DEFAULT", 0.011),
        
        # Video (Sora 2)
        video_model=os.getenv("VIDEO_MODEL", "sora-2"),
        video_seconds=_get_int("VIDEO_SECONDS", 4),  # Только 4, 8 или 12
        video_size=os.getenv("VIDEO_SIZE", "1280x720"),
        video_cost_usd_per_second=_get_float("VIDEO_COST_USD_PER_SECOND", 0.10),
        video_poll_interval_seconds=_get_int("VIDEO_POLL_INTERVAL_SECONDS", 10),
        video_max_wait_seconds=_get_int("VIDEO_MAX_WAIT_SECONDS", 300),
        
        # Debug
        debug_keep_media=_get_bool("DEBUG_KEEP_MEDIA", False),
    )


def get_image_cost_usd(size: str) -> float:
    """Возвращает стоимость генерации изображения по размеру."""
    size_map = {
        "1024x1024": config.image_cost_usd_1024x1024,
        "1024x1536": config.image_cost_usd_1024x1536,
        "1536x1024": config.image_cost_usd_1536x1024,
    }
    return size_map.get(size, config.image_cost_usd_default)


# Глобальный экземпляр конфигурации (создаётся при импорте)
config = load_config()
