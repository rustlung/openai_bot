"""
Сервисы приложения.
"""

from .openai_client import (
    OpenAIClient,
    generate_text,
    generate_image,
    generate_video,
    calculate_text_cost,
    get_client,
)

from .fx_rate import (
    FXRateService,
    get_usd_to_rub,
    get_fx_service,
)

__all__ = [
    # OpenAI
    "OpenAIClient",
    "generate_text",
    "generate_image",
    "generate_video",
    "calculate_text_cost",
    "get_client",
    # FX
    "FXRateService",
    "get_usd_to_rub",
    "get_fx_service",
]
