"""
Хранилище памяти диалогов и режимов пользователей.
Сохраняет данные в JSON файл для persistence между перезапусками.

Структура данных в файле:
{
    "chats": {
        "<chat_id>": {
            "mode": "assistant",
            "messages": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        }
    },
    "stats": {
        // Зарезервировано для будущей статистики billing
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


class ChatData(TypedDict):
    """Данные чата."""
    mode: str
    messages: list[Message]


class StorageData(TypedDict):
    """Структура данных хранилища."""
    chats: dict[str, ChatData]
    stats: dict  # Зарезервировано для billing


class MemoryStore:
    """
    Управление памятью диалогов.
    
    Особенности:
    - Хранит последние N пар сообщений (user+assistant) для каждого чата
    - Автоматически сохраняет на диск при каждом изменении
    - Поддерживает режимы (system prompts) для каждого чата
    - Готов к расширению для статистики расходов (billing)
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
        ensure_file(self.file_path, {"chats": {}, "stats": {}})
        data = safe_read_json(self.file_path, {"chats": {}, "stats": {}})
        
        # Валидация структуры
        if not isinstance(data, dict):
            data = {"chats": {}, "stats": {}}
        if "chats" not in data:
            data["chats"] = {}
        if "stats" not in data:
            data["stats"] = {}
        
        return data
    
    def _save(self) -> None:
        """Сохраняет данные на диск."""
        safe_write_json(self.file_path, self._data)
    
    def _ensure_chat(self, chat_id: int | str) -> ChatData:
        """Убеждается, что чат существует в хранилище."""
        key = str(chat_id)
        if key not in self._data["chats"]:
            self._data["chats"][key] = {
                "mode": self.DEFAULT_MODE,
                "messages": []
            }
        return self._data["chats"][key]
    
    # === Работа с сообщениями ===
    
    def get_messages(self, chat_id: int | str) -> list[Message]:
        """
        Возвращает историю сообщений для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Список сообщений в формате OpenAI
        """
        chat = self._ensure_chat(chat_id)
        return chat["messages"].copy()
    
    def add_message(self, chat_id: int | str, role: str, content: str) -> None:
        """
        Добавляет сообщение в историю чата.
        Автоматически обрезает историю до лимита пар.
        
        Args:
            chat_id: ID чата
            role: "user" или "assistant"
            content: Текст сообщения
        """
        chat = self._ensure_chat(chat_id)
        chat["messages"].append({"role": role, "content": content})
        
        # Обрезаем до максимума (сохраняем только последние N пар)
        if len(chat["messages"]) > self.max_messages:
            chat["messages"] = chat["messages"][-self.max_messages:]
        
        self._save()
    
    def add_exchange(self, chat_id: int | str, user_content: str, assistant_content: str) -> None:
        """
        Добавляет пару сообщений (user + assistant) в историю.
        Удобный метод для добавления полного обмена.
        
        Args:
            chat_id: ID чата
            user_content: Сообщение пользователя
            assistant_content: Ответ ассистента
        """
        chat = self._ensure_chat(chat_id)
        chat["messages"].append({"role": "user", "content": user_content})
        chat["messages"].append({"role": "assistant", "content": assistant_content})
        
        # Обрезаем до максимума
        if len(chat["messages"]) > self.max_messages:
            chat["messages"] = chat["messages"][-self.max_messages:]
        
        self._save()
    
    def clear_messages(self, chat_id: int | str) -> None:
        """
        Очищает историю сообщений чата (режим сохраняется).
        
        Args:
            chat_id: ID чата
        """
        chat = self._ensure_chat(chat_id)
        chat["messages"] = []
        self._save()
    
    # === Работа с режимами ===
    
    def get_mode(self, chat_id: int | str) -> str:
        """
        Возвращает текущий режим чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Ключ режима (например, "assistant", "programmer")
        """
        chat = self._ensure_chat(chat_id)
        return chat["mode"]
    
    def set_mode(self, chat_id: int | str, mode: str) -> None:
        """
        Устанавливает режим для чата.
        
        Args:
            chat_id: ID чата
            mode: Ключ режима из prompts.json
        """
        chat = self._ensure_chat(chat_id)
        chat["mode"] = mode
        self._save()
    
    # === Статистика (заготовка для billing) ===
    
    def get_stats(self) -> dict:
        """
        Возвращает статистику (для будущего billing).
        
        Returns:
            Словарь со статистикой
        """
        return self._data["stats"].copy()
    
    def update_stats(self, chat_id: int | str, usage_meta: dict) -> None:
        """
        Обновляет статистику использования (для будущего billing).
        
        TODO: Реализовать накопление статистики по чатам:
        - Количество токенов (prompt_tokens, completion_tokens)
        - Количество запросов
        - Стоимость в USD/RUB
        
        Args:
            chat_id: ID чата
            usage_meta: Метаданные использования от OpenAI
        """
        # Заготовка — пока просто сохраняем последний usage
        key = str(chat_id)
        if "by_chat" not in self._data["stats"]:
            self._data["stats"]["by_chat"] = {}
        
        if key not in self._data["stats"]["by_chat"]:
            self._data["stats"]["by_chat"][key] = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "request_count": 0,
            }
        
        chat_stats = self._data["stats"]["by_chat"][key]
        
        # Накапливаем токены, если есть в meta
        if "prompt_tokens" in usage_meta:
            chat_stats["total_prompt_tokens"] += usage_meta["prompt_tokens"]
        if "completion_tokens" in usage_meta:
            chat_stats["total_completion_tokens"] += usage_meta["completion_tokens"]
        
        chat_stats["request_count"] += 1
        
        self._save()
