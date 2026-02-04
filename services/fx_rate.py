"""
Сервис получения курса валют USD -> RUB.

Использует бесплатный API без ключей (по умолчанию: open.er-api.com).
Кеширует результат в JSON файл для снижения нагрузки на API.
"""

import time
from pathlib import Path

import httpx

from config import config
from utils.file_utils import safe_read_json, safe_write_json, ensure_dir


class FXRateService:
    """
    Сервис курса валют с кешированием.
    
    Поддерживаемые форматы:
    - open.er-api.com: https://open.er-api.com/v6/latest/USD
    - Frankfurter (ECB): https://api.frankfurter.app/latest?from=USD&to=RUB
    """
    
    def __init__(
        self,
        api_url: str | None = None,
        cache_file: str | None = None,
        cache_ttl: int | None = None,
        fallback_rate: float | None = None,
    ):
        self.api_url = api_url or config.fx_api_url
        self.cache_file = Path(cache_file or config.fx_cache_file_path)
        self.cache_ttl = cache_ttl or config.fx_cache_ttl_seconds
        self.fallback_rate = fallback_rate or config.usd_rub_rate_fallback
        
        # Убеждаемся что директория существует
        ensure_dir(self.cache_file.parent)
    
    def _load_cache(self) -> dict | None:
        """Загружает кеш из файла."""
        data = safe_read_json(self.cache_file, None)
        if not data:
            return None
        
        # Проверяем TTL
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > self.cache_ttl:
            return None  # Кеш устарел
        
        return data
    
    def _save_cache(self, rate: float, source: str, date: str) -> None:
        """Сохраняет курс в кеш."""
        data = {
            "rate": rate,
            "source": source,
            "date": date,
            "cached_at": time.time(),
        }
        safe_write_json(self.cache_file, data)
    
    async def get_rate(self) -> tuple[float, dict]:
        """
        Получает актуальный курс USD -> RUB.
        
        Returns:
            Кортеж (rate, meta), где:
            - rate: курс USD/RUB (float)
            - meta: метаданные
                - source: источник данных
                - date: дата курса
                - cached: True если из кеша
                - error: сообщение об ошибке (если есть)
        """
        # Пробуем из кеша
        cache = self._load_cache()
        if cache:
            return cache["rate"], {
                "source": cache.get("source", "cache"),
                "date": cache.get("date", "unknown"),
                "cached": True,
            }
        
        # Запрашиваем свежий курс
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                data = response.json()
            
            # Парсим ответ в зависимости от формата
            # open.er-api.com: {"result":"success","time_last_update_utc":"...","rates":{"RUB":...}}
            # Frankfurter: {"amount":1,"base":"USD","date":"2024-01-25","rates":{"RUB":88.5}}
            rate = None
            date = "unknown"
            source = "unknown"
            
            if isinstance(data, dict) and "rates" in data:
                rate = data.get("rates", {}).get("RUB")
                
                # Определяем источник
                if "time_last_update_utc" in data or "time_last_update_unix" in data:
                    source = "open_er_api"
                    date = data.get("time_last_update_utc", "unknown")
                elif "date" in data:
                    source = "frankfurter"
                    date = data.get("date", "unknown")
            
            if rate is None:
                raise ValueError("RUB rate not found in response")
            
            # Сохраняем в кеш
            self._save_cache(rate, source, date)
            
            return rate, {
                "source": source,
                "date": date,
                "cached": False,
            }
            
        except Exception as e:
            print(f"Ошибка получения курса валют: {e}")
            
            # Возвращаем fallback
            return self.fallback_rate, {
                "source": "fallback",
                "date": "unknown",
                "cached": False,
                "error": str(e),
            }


# Глобальный экземпляр сервиса
_fx_service: FXRateService | None = None


def get_fx_service() -> FXRateService:
    """Возвращает глобальный экземпляр сервиса (lazy initialization)."""
    global _fx_service
    if _fx_service is None:
        _fx_service = FXRateService()
    return _fx_service


async def get_usd_to_rub() -> tuple[float, dict]:
    """
    Получает курс USD -> RUB.
    
    Returns:
        Кортеж (rate, meta)
    
    Example:
        rate, meta = await get_usd_to_rub()
        print(f"Курс: {rate:.2f} RUB/USD (источник: {meta['source']})")
    """
    service = get_fx_service()
    return await service.get_rate()
