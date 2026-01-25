"""
Клиент для работы с OpenAI API.

Этот модуль предоставляет:
- generate_text() — генерация текста (реализовано)
- generate_image() — генерация изображений (TODO)
- generate_video() — генерация видео (TODO)
- estimate_cost() — расчёт стоимости (TODO)

Все функции возвращают кортеж (result, meta), где meta содержит
информацию для billing (токены, модель и т.д.)
"""

from typing import Any
from openai import AsyncOpenAI

from config import config


class OpenAIClient:
    """
    Асинхронный клиент OpenAI.
    Инкапсулирует работу с API и подготовку метаданных для billing.
    """
    
    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        """
        Args:
            api_key: API ключ OpenAI (если None — берётся из config)
            default_model: Модель по умолчанию (если None — берётся из config)
        """
        self.api_key = api_key or config.openai_api_key
        self.default_model = default_model or config.openai_model
        self._client = AsyncOpenAI(api_key=self.api_key)
    
    async def generate_text(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any
    ) -> tuple[str, dict]:
        """
        Генерирует текстовый ответ от модели.
        
        Args:
            messages: Список сообщений в формате OpenAI
                      [{"role": "system|user|assistant", "content": "..."}]
            model: Модель для использования (опционально)
            **kwargs: Дополнительные параметры для API (temperature, max_tokens и т.д.)
        
        Returns:
            Кортеж (assistant_text, meta), где:
            - assistant_text: Текст ответа
            - meta: Словарь с метаданными для billing:
                - model: использованная модель
                - prompt_tokens: токены запроса
                - completion_tokens: токены ответа
                - total_tokens: всего токенов
        
        Raises:
            Exception: При ошибке API (обрабатывается вызывающим кодом)
        """
        used_model = model or self.default_model
        
        response = await self._client.chat.completions.create(
            model=used_model,
            messages=messages,
            **kwargs
        )
        
        # Извлекаем текст ответа
        assistant_text = response.choices[0].message.content or ""
        
        # Собираем метаданные для billing
        usage = response.usage
        meta = {
            "model": used_model,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }
        
        return assistant_text, meta


# === Глобальный экземпляр клиента ===
_client: OpenAIClient | None = None


def get_client() -> OpenAIClient:
    """Возвращает глобальный экземпляр клиента (lazy initialization)."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client


# === Функции-обёртки для удобства ===

async def generate_text(
    messages: list[dict[str, str]],
    model: str | None = None,
    **kwargs: Any
) -> tuple[str, dict]:
    """
    Генерирует текстовый ответ.
    
    Args:
        messages: Список сообщений в формате OpenAI
        model: Модель (опционально, по умолчанию из config)
        **kwargs: Дополнительные параметры API
    
    Returns:
        Кортеж (assistant_text, meta)
    
    Example:
        text, meta = await generate_text([
            {"role": "system", "content": "Ты помощник"},
            {"role": "user", "content": "Привет!"}
        ])
    """
    client = get_client()
    return await client.generate_text(messages, model, **kwargs)


# ============================================================
# TODO: Функции для будущих расширений (не реализованы)
# ============================================================

async def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard",
    **kwargs: Any
) -> tuple[str | None, dict]:
    """
    TODO: Генерация изображения через DALL-E.
    
    Args:
        prompt: Описание изображения
        model: Модель генерации (dall-e-2, dall-e-3)
        size: Размер изображения (1024x1024, 1792x1024, 1024x1792)
        quality: Качество (standard, hd — только для dall-e-3)
        **kwargs: Дополнительные параметры
    
    Returns:
        Кортеж (image_url, meta), где:
        - image_url: URL сгенерированного изображения (или None при ошибке)
        - meta: Метаданные для billing:
            - model: использованная модель
            - size: размер
            - quality: качество
            - cost_usd: примерная стоимость
    
    Example:
        url, meta = await generate_image("Космический кот в стиле киберпанк")
        if url:
            # Отправить изображение пользователю
            pass
    """
    # TODO: Реализовать генерацию изображений
    # client = get_client()
    # response = await client._client.images.generate(
    #     model=model,
    #     prompt=prompt,
    #     size=size,
    #     quality=quality,
    #     n=1,
    #     **kwargs
    # )
    # image_url = response.data[0].url
    # meta = {"model": model, "size": size, "quality": quality}
    # return image_url, meta
    
    raise NotImplementedError("generate_image() пока не реализована. См. TODO в services/openai_client.py")


async def generate_video(
    prompt: str,
    model: str = "sora",  # или другая модель видео в будущем
    duration: int = 5,
    **kwargs: Any
) -> tuple[str | None, dict]:
    """
    TODO: Генерация видео (когда API станет доступен).
    
    Args:
        prompt: Описание видео
        model: Модель генерации
        duration: Длительность в секундах
        **kwargs: Дополнительные параметры
    
    Returns:
        Кортеж (video_url, meta), где:
        - video_url: URL сгенерированного видео
        - meta: Метаданные для billing
    
    Note:
        На момент написания кода публичный API генерации видео от OpenAI
        недоступен. Эта функция — заготовка для будущего расширения.
    """
    # TODO: Реализовать когда появится API
    raise NotImplementedError("generate_video() пока не реализована — ожидаем публичный API.")


def estimate_cost(meta: dict, usd_rub_rate: float | None = None) -> dict:
    """
    TODO: Расчёт стоимости запроса на основе метаданных.
    
    Args:
        meta: Метаданные от generate_* функций
        usd_rub_rate: Курс USD/RUB (если None — берётся из config)
    
    Returns:
        Словарь с расчётом стоимости:
        - cost_usd: стоимость в долларах
        - cost_rub: стоимость в рублях
        - breakdown: детализация по компонентам
    
    Example:
        text, meta = await generate_text(messages)
        cost = estimate_cost(meta)
        print(f"Стоимость запроса: ${cost['cost_usd']:.4f} ({cost['cost_rub']:.2f} ₽)")
    
    Note:
        Цены на модели меняются. Актуальные цены см. на https://openai.com/pricing
    """
    # TODO: Реализовать расчёт стоимости
    # Примерные цены (на январь 2024, устаревают быстро):
    # GPT-4: $0.03/1K prompt, $0.06/1K completion
    # GPT-4 Turbo: $0.01/1K prompt, $0.03/1K completion
    # GPT-3.5 Turbo: $0.0015/1K prompt, $0.002/1K completion
    # DALL-E 3: $0.04-0.12 за изображение
    
    rate = usd_rub_rate or config.usd_rub_rate
    
    # Заглушка — возвращаем нулевую стоимость
    return {
        "cost_usd": 0.0,
        "cost_rub": 0.0,
        "breakdown": {},
        "note": "estimate_cost() пока не реализована полностью. См. TODO в services/openai_client.py"
    }
