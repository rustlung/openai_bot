"""
Обработчики команд и сообщений Telegram бота.

Команды:
- /start — приветствие и справка
- /mode — выбор режима (system prompt)
- /reset — очистка истории диалога
- Текстовые сообщения — обработка через OpenAI
"""

import json
import sys
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import config
from storage import MemoryStore
from services import generate_text

# Роутер для регистрации хендлеров
router = Router()

# Хранилище памяти (инициализируется в setup_handlers)
memory: MemoryStore | None = None

# Промпты режимов (загружаются в setup_handlers)
prompts: dict = {}


def load_prompts(file_path: str = "prompts.json") -> dict:
    """
    Загружает промпты из JSON файла.
    Завершает программу с ошибкой, если файл не найден или повреждён.
    """
    path = Path(file_path)
    
    if not path.exists():
        print("=" * 50)
        print("ОШИБКА: Файл prompts.json не найден!")
        print("=" * 50)
        print(f"Ожидаемый путь: {path.absolute()}")
        print("Создайте файл prompts.json с режимами бота.")
        print("Пример структуры см. в README.md")
        print("=" * 50)
        sys.exit(1)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print("=" * 50)
        print("ОШИБКА: Файл prompts.json повреждён!")
        print("=" * 50)
        print(f"Ошибка парсинга: {e}")
        print("Проверьте синтаксис JSON в файле.")
        print("=" * 50)
        sys.exit(1)
    
    # Валидация структуры
    if not isinstance(data, dict) or len(data) == 0:
        print("=" * 50)
        print("ОШИБКА: prompts.json должен содержать хотя бы один режим!")
        print("=" * 50)
        sys.exit(1)
    
    for key, value in data.items():
        if not isinstance(value, dict):
            print(f"ОШИБКА: Режим '{key}' должен быть объектом")
            sys.exit(1)
        if "system_prompt" not in value:
            print(f"ОШИБКА: Режим '{key}' не содержит system_prompt")
            sys.exit(1)
    
    return data


def setup_handlers() -> None:
    """
    Инициализирует хендлеры: загружает промпты и создаёт хранилище.
    Вызывается перед запуском бота.
    """
    global memory, prompts
    
    # Загружаем промпты
    prompts = load_prompts()
    print(f"Загружено режимов: {len(prompts)}")
    for key, data in prompts.items():
        name = data.get("name", key)
        print(f"  - {key}: {name}")
    
    # Инициализируем хранилище
    memory = MemoryStore(
        file_path=config.memory_file_path,
        pairs_limit=config.history_pairs_limit
    )
    print(f"Память: {config.memory_file_path} (лимит: {config.history_pairs_limit} пар)")


def get_mode_name(mode_key: str) -> str:
    """Возвращает отображаемое имя режима."""
    if mode_key in prompts:
        return prompts[mode_key].get("name", mode_key)
    return mode_key


def get_system_prompt(mode_key: str) -> str:
    """Возвращает system prompt для режима."""
    if mode_key in prompts:
        return prompts[mode_key].get("system_prompt", "")
    # Fallback на первый доступный режим
    first_key = next(iter(prompts))
    return prompts[first_key].get("system_prompt", "")


# === Команда /start ===

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start — приветствие и справка."""
    chat_id = message.chat.id
    current_mode = memory.get_mode(chat_id)
    mode_name = get_mode_name(current_mode)
    
    text = (
        "👋 <b>Привет! Я AI-ассистент.</b>\n\n"
        f"🎭 Текущий режим: <b>{mode_name}</b>\n\n"
        "📝 <b>Команды:</b>\n"
        "/mode — выбрать режим общения\n"
        "/reset — очистить историю диалога\n\n"
        "Просто напишите сообщение, и я отвечу!"
    )
    
    await message.answer(text, parse_mode="HTML")


# === Команда /mode ===

@router.message(Command("mode"))
async def cmd_mode(message: Message) -> None:
    """Обработчик команды /mode — показывает список режимов."""
    chat_id = message.chat.id
    current_mode = memory.get_mode(chat_id)
    
    # Формируем inline-клавиатуру с режимами
    buttons = []
    for key, data in prompts.items():
        name = data.get("name", key)
        description = data.get("description", "")
        
        # Отмечаем текущий режим
        if key == current_mode:
            label = f"✅ {name}"
        else:
            label = name
        
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"mode:{key}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    text = (
        "🎭 <b>Выберите режим:</b>\n\n"
        + "\n".join(
            f"<b>{data.get('name', key)}</b> — {data.get('description', '')}"
            for key, data in prompts.items()
        )
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("mode:"))
async def callback_mode(callback: CallbackQuery) -> None:
    """Обработчик выбора режима через inline-кнопку."""
    chat_id = callback.message.chat.id
    mode_key = callback.data.split(":", 1)[1]
    
    if mode_key not in prompts:
        await callback.answer("Режим не найден", show_alert=True)
        return
    
    # Устанавливаем новый режим
    memory.set_mode(chat_id, mode_key)
    mode_name = get_mode_name(mode_key)
    
    await callback.answer(f"Выбран режим: {mode_name}")
    
    # Обновляем сообщение
    await callback.message.edit_text(
        f"✅ Режим изменён на: <b>{mode_name}</b>\n\n"
        f"Теперь я буду отвечать в этом стиле. Напишите что-нибудь!",
        parse_mode="HTML"
    )


# === Команда /reset ===

@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    """Обработчик команды /reset — очищает историю диалога."""
    chat_id = message.chat.id
    memory.clear_messages(chat_id)
    
    mode_name = get_mode_name(memory.get_mode(chat_id))
    
    await message.answer(
        "🗑 <b>История диалога очищена.</b>\n\n"
        f"Режим сохранён: <b>{mode_name}</b>\n"
        "Начните новый разговор!",
        parse_mode="HTML"
    )


# === Обработка текстовых сообщений ===

@router.message(F.text)
async def handle_text_message(message: Message) -> None:
    """
    Обработчик текстовых сообщений.
    Отправляет сообщение в OpenAI и возвращает ответ.
    """
    chat_id = message.chat.id
    user_text = message.text.strip()
    
    if not user_text:
        return
    
    # Получаем текущий режим и system prompt
    current_mode = memory.get_mode(chat_id)
    system_prompt = get_system_prompt(current_mode)
    
    # Получаем историю сообщений
    history = memory.get_messages(chat_id)
    
    # Формируем messages для OpenAI
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    
    # Отправляем индикатор "печатает"
    await message.bot.send_chat_action(chat_id, "typing")
    
    try:
        # Генерируем ответ
        assistant_text, meta = await generate_text(messages)
        
        # Сохраняем обмен в память
        memory.add_exchange(chat_id, user_text, assistant_text)
        
        # Обновляем статистику (для будущего billing)
        memory.update_stats(chat_id, meta)
        
        # Отправляем ответ
        await message.answer(assistant_text)
        
    except Exception as e:
        # Логируем ошибку
        print(f"Ошибка OpenAI для chat_id={chat_id}: {e}")
        
        # Отправляем аккуратное сообщение пользователю
        await message.answer(
            "⚠️ Извините, произошла ошибка при обработке запроса.\n"
            "Попробуйте ещё раз или измените сообщение."
        )
