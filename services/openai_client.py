"""
Клиент для работы с OpenAI API.

Этот модуль предоставляет:
- generate_text() — генерация текста
- generate_image() — генерация изображений (gpt-image-1 / DALL-E)
- generate_video() — генерация видео (Sora 2)
- calculate_text_cost() — расчёт стоимости текста

Все функции возвращают кортеж (result, meta), где meta содержит
информацию для billing (токены, модель, cost_usd и т.д.)
"""

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

import httpx
from openai import AsyncOpenAI

from config import config, get_image_cost_usd
from utils.file_utils import ensure_dir


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
        
        Returns:
            Кортеж (assistant_text, meta), где meta содержит:
            - type: "text"
            - model: использованная модель
            - usage: {input_tokens, output_tokens, total_tokens}
            - cost_usd: стоимость в USD
        """
        used_model = model or self.default_model
        
        response = await self._client.chat.completions.create(
            model=used_model,
            messages=messages,
            **kwargs
        )
        
        # Извлекаем текст ответа
        assistant_text = response.choices[0].message.content or ""
        
        # Собираем usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        
        # Рассчитываем стоимость
        cost_usd = calculate_text_cost(input_tokens, output_tokens)
        
        meta = {
            "type": "text",
            "model": used_model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "cost_usd": cost_usd,
        }
        
        return assistant_text, meta
    
    async def generate_image(
        self,
        prompt: str,
        model: str | None = None,
        size: str | None = None,
        **kwargs: Any
    ) -> tuple[bytes, dict]:
        """
        Генерирует изображение.
        
        Args:
            prompt: Описание изображения
            model: Модель (по умолчанию из config.image_model)
            size: Размер (по умолчанию из config.image_size)
        
        Returns:
            Кортеж (image_bytes, meta), где meta содержит:
            - type: "image"
            - model: использованная модель
            - size: размер
            - n: количество изображений
            - cost_usd: стоимость в USD
        
        Raises:
            Exception: При ошибке генерации
        """
        used_model = model or config.image_model
        used_size = size or config.image_size
        
        # gpt-image-1 возвращает base64 по умолчанию и не поддерживает response_format
        # DALL-E 3 поддерживает response_format
        if used_model.startswith("gpt-image"):
            # Для gpt-image-1: не передаём response_format
            response = await self._client.images.generate(
                model=used_model,
                prompt=prompt,
                size=used_size,
                n=1,
                **kwargs
            )
            # gpt-image-1 возвращает base64 в поле b64_json
            b64_data = response.data[0].b64_json
            if b64_data:
                image_bytes = base64.b64decode(b64_data)
            else:
                # Если вернулся URL — скачиваем
                image_url = response.data[0].url
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(image_url)
                    img_response.raise_for_status()
                    image_bytes = img_response.content
        else:
            # Для DALL-E 2/3: можно использовать response_format
            response = await self._client.images.generate(
                model=used_model,
                prompt=prompt,
                size=used_size,
                n=1,
                response_format="b64_json",
                **kwargs
            )
            b64_data = response.data[0].b64_json
            image_bytes = base64.b64decode(b64_data)
        
        # Стоимость по размеру
        cost_usd = get_image_cost_usd(used_size)
        
        meta = {
            "type": "image",
            "model": used_model,
            "size": used_size,
            "n": 1,
            "cost_usd": cost_usd,
        }
        
        return image_bytes, meta
    
    async def generate_video(
        self,
        prompt: str,
        model: str | None = None,
        seconds: int | None = None,
        size: str | None = None,
        poll_interval: int | None = None,
        max_wait: int | None = None,
    ) -> tuple[bytes, dict]:
        """
        Генерирует видео через OpenAI Sora 2 API.
        
        Документация: https://platform.openai.com/docs/guides/video-generation
        
        Args:
            prompt: Описание видео
            model: Модель (sora-2 или sora-2-pro)
            seconds: Длительность в секундах (5-20)
            size: Размер ("1280x720" landscape или "720x1280" portrait)
            poll_interval: Интервал polling в секундах
            max_wait: Максимальное время ожидания в секундах
        
        Returns:
            Кортеж (video_bytes, meta), где meta содержит:
            - type: "video"
            - model: использованная модель
            - seconds: длительность
            - size: размер
            - cost_usd: стоимость
            - video_id: ID сгенерированного видео
        
        Raises:
            TimeoutError: Превышено время ожидания
            Exception: Ошибка генерации
        """
        used_model = model or config.video_model
        used_seconds = seconds or config.video_seconds
        used_size = size or config.video_size
        used_poll_interval = poll_interval or config.video_poll_interval_seconds
        used_max_wait = max_wait or config.video_max_wait_seconds
        
        # Создаём задачу на генерацию через SDK
        # POST /v1/videos
        # ВАЖНО: seconds должен быть строкой "4", "8" или "12"
        video_job = await self._client.videos.create(
            model=used_model,
            prompt=prompt,
            size=used_size,
            seconds=str(used_seconds),
        )
        
        video_id = video_job.id
        start_time = time.time()
        
        # Polling до завершения
        while True:
            elapsed = time.time() - start_time
            if elapsed > used_max_wait:
                raise TimeoutError(
                    f"Генерация видео превысила лимит ожидания ({used_max_wait} сек)"
                )
            
            # Проверяем статус
            # GET /v1/videos/{video_id}
            status = await self._client.videos.retrieve(video_id)
            
            if status.status == "completed":
                break
            elif status.status == "failed":
                error_msg = "Unknown error"
                if hasattr(status, "error") and status.error:
                    error_msg = getattr(status.error, "message", str(status.error))
                raise Exception(f"Генерация видео провалилась: {error_msg}")
            
            # Ждём перед следующей проверкой
            await asyncio.sleep(used_poll_interval)
        
        # Скачиваем видео
        # GET /v1/videos/{video_id}/content
        video_bytes = await self._download_video_content(video_id)
        
        # Стоимость: $0.10 за секунду для sora-2, $0.30 для sora-2-pro
        cost_usd = used_seconds * config.video_cost_usd_per_second
        
        meta = {
            "type": "video",
            "model": used_model,
            "seconds": used_seconds,
            "size": used_size,
            "cost_usd": cost_usd,
            "video_id": video_id,
        }
        
        return video_bytes, meta
    
    async def _download_video_content(self, video_id: str) -> bytes:
        """
        Скачивает видео контент по ID.
        GET /v1/videos/{video_id}/content
        """
        # Пробуем через SDK если есть метод
        try:
            content = await self._client.videos.download_content(video_id)
            # Если SDK возвращает объект с методом read или bytes
            if hasattr(content, "read"):
                return await content.read()
            elif hasattr(content, "content"):
                return content.content
            elif isinstance(content, bytes):
                return content
            else:
                # Пробуем получить arrayBuffer
                body = await content.arrayBuffer() if hasattr(content, "arrayBuffer") else content
                return bytes(body) if not isinstance(body, bytes) else body
        except AttributeError:
            pass
        
        # Fallback: прямой HTTP запрос
        url = f"https://api.openai.com/v1/videos/{video_id}/content"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content


# === Глобальный экземпляр клиента ===
_client: OpenAIClient | None = None


def get_client() -> OpenAIClient:
    """Возвращает глобальный экземпляр клиента (lazy initialization)."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client


# === Расчёт стоимости ===

def calculate_text_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Рассчитывает стоимость текстового запроса в USD.
    
    Args:
        input_tokens: Количество входных токенов
        output_tokens: Количество выходных токенов
    
    Returns:
        Стоимость в USD
    """
    input_cost = (input_tokens / 1_000_000) * config.price_text_input_usd_per_1m
    output_cost = (output_tokens / 1_000_000) * config.price_text_output_usd_per_1m
    return input_cost + output_cost


# === Функции-обёртки для удобства ===

async def generate_text(
    messages: list[dict[str, str]],
    model: str | None = None,
    **kwargs: Any
) -> tuple[str, dict]:
    """
    Генерирует текстовый ответ.
    
    Returns:
        Кортеж (assistant_text, meta)
    """
    client = get_client()
    return await client.generate_text(messages, model, **kwargs)


async def generate_image(
    prompt: str,
    model: str | None = None,
    size: str | None = None,
    **kwargs: Any
) -> tuple[bytes, dict]:
    """
    Генерирует изображение.
    
    Returns:
        Кортеж (image_bytes, meta)
    """
    client = get_client()
    return await client.generate_image(prompt, model, size, **kwargs)


async def generate_video(
    prompt: str,
    model: str | None = None,
    seconds: int | None = None,
    size: str | None = None,
    **kwargs: Any
) -> tuple[bytes, dict]:
    """
    Генерирует видео.
    
    Returns:
        Кортеж (video_bytes, meta)
    """
    client = get_client()
    return await client.generate_video(prompt, model, seconds, size, **kwargs)
