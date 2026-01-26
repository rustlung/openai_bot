"""
Хранилище памяти диалогов, режимов и billing статистики.
Сохраняет данные в JSON файл для persistence между перезапусками.

Структура данных в файле:
{
    "chats": {
        "<chat_id>": {
            "mode": "assistant",
            "messages": [...],
            "billing": {
                "total_cost_usd": 0.0,
                "total_cost_rub": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_requests": 0,
                "breakdown": {
                    "text": {"count": 0, "cost_usd": 0.0, "tokens": 0},
                    "image": {"count": 0, "cost_usd": 0.0},
                    "video": {"count": 0, "cost_usd": 0.0, "seconds": 0}
                }
            }
        }
    }
}
"""

from typing import TypedDict
from pathlib import Path

from utils.file_utils import ensure_file, safe_write_json, safe_read_json


class Message(TypedDict):
    """Формат сообщения (совместим с OpenAI API)."""
    role: str  # "user" | "assistant" | "system"
    content: str


class BillingBreakdown(TypedDict, total=False):
    """Детализация по типам запросов."""
    text: dict   # {"count": int, "cost_usd": float, "tokens": int}
    image: dict  # {"count": int, "cost_usd": float}
    video: dict  # {"count": int, "cost_usd": float, "seconds": int}


class BillingData(TypedDict, total=False):
    """Данные billing для чата."""
    total_cost_usd: float
    total_cost_rub: float
    total_input_tokens: int
    total_output_tokens: int
    total_requests: int
    breakdown: BillingBreakdown


class ChatData(TypedDict, total=False):
    """Данные чата."""
    mode: str
    messages: list[Message]
    billing: BillingData


class StorageData(TypedDict):
    """Структура данных хранилища."""
    chats: dict[str, ChatData]


def _default_billing() -> BillingData:
    """Возвращает пустую структуру billing."""
    return {
        "total_cost_usd": 0.0,
        "total_cost_rub": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_requests": 0,
        "breakdown": {
            "text": {"count": 0, "cost_usd": 0.0, "tokens": 0},
            "image": {"count": 0, "cost_usd": 0.0},
            "video": {"count": 0, "cost_usd": 0.0, "seconds": 0},
        }
    }


class MemoryStore:
    """
    Управление памятью диалогов и billing статистикой.
    
    Особенности:
    - Хранит последние N пар сообщений (user+assistant) для каждого чата
    - Автоматически сохраняет на диск при каждом изменении
    - Поддерживает режимы (system prompts) для каждого чата
    - Накапливает статистику расходов (billing)
    """
    
    DEFAULT_MODE = "assistant"
    
    def __init__(self, file_path: str | Path, pairs_limit: int = 5):
        """
        Args:
            file_path: Путь к JSON файлу хранилища
            pairs_limit: Максимальное количество пар сообщений (user+assistant)
        """
        self.file_path = Path(file_path)
        self.pairs_limit = pairs_limit
        self.max_messages = pairs_limit * 2  # Каждая пара = 2 сообщения
        
        # Загружаем данные или создаём пустое хранилище
        self._data: StorageData = self._load()
    
    def _load(self) -> StorageData:
        """Загружает данные из файла или создаёт пустую структуру."""
        ensure_file(self.file_path, {"chats": {}})
        data = safe_read_json(self.file_path, {"chats": {}})
        
        # Валидация структуры
        if not isinstance(data, dict):
            data = {"chats": {}}
        if "chats" not in data:
            data["chats"] = {}
        
        return data
    
    def _save(self) -> None:
        """Сохраняет данные на диск."""
        safe_write_json(self.file_path, self._data)
    
    def _ensure_chat(self, chat_id: int | str) -> ChatData:
        """Убеждается, что чат существует в хранилище с полной структурой."""
        key = str(chat_id)
        if key not in self._data["chats"]:
            self._data["chats"][key] = {
                "mode": self.DEFAULT_MODE,
                "messages": [],
                "billing": _default_billing(),
            }
        else:
            # Убеждаемся что billing существует (миграция старых данных)
            chat = self._data["chats"][key]
            if "billing" not in chat:
                chat["billing"] = _default_billing()
            # Проверяем breakdown
            if "breakdown" not in chat["billing"]:
                chat["billing"]["breakdown"] = {
                    "text": {"count": 0, "cost_usd": 0.0, "tokens": 0},
                    "image": {"count": 0, "cost_usd": 0.0},
                    "video": {"count": 0, "cost_usd": 0.0, "seconds": 0},
                }
        
        return self._data["chats"][key]
    
    # === Работа с сообщениями ===
    
    def get_messages(self, chat_id: int | str) -> list[Message]:
        """Возвращает историю сообщений для чата."""
        chat = self._ensure_chat(chat_id)
        return chat["messages"].copy()
    
    def add_message(self, chat_id: int | str, role: str, content: str) -> None:
        """Добавляет сообщение в историю чата."""
        chat = self._ensure_chat(chat_id)
        chat["messages"].append({"role": role, "content": content})
        
        # Обрезаем до максимума
        if len(chat["messages"]) > self.max_messages:
            chat["messages"] = chat["messages"][-self.max_messages:]
        
        self._save()
    
    def add_exchange(self, chat_id: int | str, user_content: str, assistant_content: str) -> None:
        """Добавляет пару сообщений (user + assistant) в историю."""
        chat = self._ensure_chat(chat_id)
        chat["messages"].append({"role": "user", "content": user_content})
        chat["messages"].append({"role": "assistant", "content": assistant_content})
        
        if len(chat["messages"]) > self.max_messages:
            chat["messages"] = chat["messages"][-self.max_messages:]
        
        self._save()
    
    def clear_messages(self, chat_id: int | str) -> None:
        """Очищает историю сообщений чата (режим и billing сохраняются)."""
        chat = self._ensure_chat(chat_id)
        chat["messages"] = []
        self._save()
    
    # === Работа с режимами ===
    
    def get_mode(self, chat_id: int | str) -> str:
        """Возвращает текущий режим чата."""
        chat = self._ensure_chat(chat_id)
        return chat.get("mode", self.DEFAULT_MODE)
    
    def set_mode(self, chat_id: int | str, mode: str) -> None:
        """Устанавливает режим для чата."""
        chat = self._ensure_chat(chat_id)
        chat["mode"] = mode
        self._save()
    
    # === Billing ===
    
    def get_billing(self, chat_id: int | str) -> BillingData:
        """Возвращает billing статистику для чата."""
        chat = self._ensure_chat(chat_id)
        return chat["billing"].copy()
    
    def update_billing(
        self,
        chat_id: int | str,
        meta: dict,
        usd_to_rub_rate: float,
    ) -> None:
        """
        Обновляет billing статистику после успешного запроса.
        
        Args:
            chat_id: ID чата
            meta: Метаданные от generate_* функций (должен содержать type, cost_usd, usage)
            usd_to_rub_rate: Текущий курс USD/RUB
        """
        chat = self._ensure_chat(chat_id)
        billing = chat["billing"]
        
        request_type = meta.get("type", "unknown")
        cost_usd = meta.get("cost_usd", 0.0)
        cost_rub = cost_usd * usd_to_rub_rate
        
        # Общие счётчики
        billing["total_cost_usd"] = billing.get("total_cost_usd", 0.0) + cost_usd
        billing["total_cost_rub"] = billing.get("total_cost_rub", 0.0) + cost_rub
        billing["total_requests"] = billing.get("total_requests", 0) + 1
        
        # Детализация по типу
        breakdown = billing.setdefault("breakdown", {})
        
        if request_type == "text":
            usage = meta.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            
            # Общие токены
            billing["total_input_tokens"] = billing.get("total_input_tokens", 0) + input_tokens
            billing["total_output_tokens"] = billing.get("total_output_tokens", 0) + output_tokens
            
            # Breakdown для текста
            text_stats = breakdown.setdefault("text", {"count": 0, "cost_usd": 0.0, "tokens": 0})
            text_stats["count"] = text_stats.get("count", 0) + 1
            text_stats["cost_usd"] = text_stats.get("cost_usd", 0.0) + cost_usd
            text_stats["tokens"] = text_stats.get("tokens", 0) + input_tokens + output_tokens
            
        elif request_type == "image":
            img_stats = breakdown.setdefault("image", {"count": 0, "cost_usd": 0.0})
            img_stats["count"] = img_stats.get("count", 0) + 1
            img_stats["cost_usd"] = img_stats.get("cost_usd", 0.0) + cost_usd
            
        elif request_type == "video":
            video_seconds = meta.get("seconds", 0)
            vid_stats = breakdown.setdefault("video", {"count": 0, "cost_usd": 0.0, "seconds": 0})
            vid_stats["count"] = vid_stats.get("count", 0) + 1
            vid_stats["cost_usd"] = vid_stats.get("cost_usd", 0.0) + cost_usd
            vid_stats["seconds"] = vid_stats.get("seconds", 0) + video_seconds
        
        self._save()
    
    def clear_billing(self, chat_id: int | str) -> None:
        """Сбрасывает billing статистику для чата."""
        chat = self._ensure_chat(chat_id)
        chat["billing"] = _default_billing()
        self._save()
    
    # === Legacy compatibility ===
    
    def update_stats(self, chat_id: int | str, usage_meta: dict) -> None:
        """
        DEPRECATED: Используйте update_billing() вместо этого.
        Оставлено для обратной совместимости.
        """
        # Простая обёртка с дефолтным курсом
        from config import config
        self.update_billing(chat_id, usage_meta, config.usd_rub_rate_fallback)
