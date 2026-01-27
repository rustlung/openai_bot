"""
Обработчики команд и сообщений Telegram бота.

Команды:
- /start — приветствие и справка
- /help — полный список команд
- /mode — выбор режима (system prompt)
- /reset — очистка истории диалога
- /cost — показать статистику расходов
- /reset_cost — сбросить статистику расходов
- /image <prompt> — генерация изображения
- /video <prompt> — генерация видео
- Текстовые сообщения — обработка через OpenAI
"""

import json
import os
import sys
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from config import config
from storage import MemoryStore
from services import generate_text, generate_image, generate_video, get_usd_to_rub

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
    first_key = next(iter(prompts))
    return prompts[first_key].get("system_prompt", "")


def format_cost_line(cost_usd: float, cost_rub: float) -> str:
    """Форматирует строку стоимости."""
    return f"~{cost_usd:.6f} USD (~{cost_rub:.2f} ₽)"


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
        "/help — полный список команд\n"
        "/mode — выбрать режим общения\n"
        "/reset — очистить историю диалога\n"
        "/cost — посмотреть расходы\n"
        "/image &lt;описание&gt; — сгенерировать картинку\n"
        "/video &lt;описание&gt; — сгенерировать видео\n\n"
        "Просто напишите сообщение, и я отвечу!"
    )
    
    await message.answer(text, parse_mode="HTML")


# === Команда /help ===

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help — полный список команд."""
    text = (
        "📖 <b>Список команд:</b>\n\n"
        "<b>Основные:</b>\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/mode — выбрать режим (стиль ответов)\n"
        "/reset — очистить историю диалога\n\n"
        "<b>Генерация:</b>\n"
        "/image &lt;описание&gt; — сгенерировать картинку\n"
        "/video &lt;описание&gt; — сгенерировать видео (Sora 2)\n\n"
        "<b>Статистика:</b>\n"
        "/cost — посмотреть расходы по чату\n"
        "/reset_cost — сбросить счётчик расходов\n\n"
        "<b>Текстовые сообщения</b> — я отвечу с учётом контекста диалога."
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
        "Статистика расходов сохранена (см. /cost).\n"
        "Начните новый разговор!",
        parse_mode="HTML"
    )


# === Команда /cost ===

@router.message(Command("cost"))
async def cmd_cost(message: Message) -> None:
    """Обработчик команды /cost — показывает статистику расходов."""
    chat_id = message.chat.id
    billing = memory.get_billing(chat_id)
    
    # Получаем актуальный курс
    rate, rate_meta = await get_usd_to_rub()
    rate_status = "📦 кеш" if rate_meta.get("cached") else "🔄 обновлён"
    rate_source = rate_meta.get("source", "unknown")
    
    # Извлекаем данные
    total_usd = billing.get("total_cost_usd", 0.0)
    total_rub = billing.get("total_cost_rub", 0.0)
    total_requests = billing.get("total_requests", 0)
    input_tokens = billing.get("total_input_tokens", 0)
    output_tokens = billing.get("total_output_tokens", 0)
    
    breakdown = billing.get("breakdown", {})
    text_stats = breakdown.get("text", {})
    image_stats = breakdown.get("image", {})
    video_stats = breakdown.get("video", {})
    
    # Формируем текст
    text = (
        "💰 <b>Статистика расходов</b>\n\n"
        f"<b>Всего потрачено:</b>\n"
        f"  💵 {total_usd:.6f} USD\n"
        f"  💴 {total_rub:.2f} ₽\n\n"
        f"<b>Запросов:</b> {total_requests}\n\n"
        f"<b>Детализация:</b>\n"
    )
    
    # Текст
    text_count = text_stats.get("count", 0)
    if text_count > 0:
        text_cost = text_stats.get("cost_usd", 0.0)
        text_tokens = text_stats.get("tokens", 0)
        text += (
            f"  📝 Текст: {text_count} запросов\n"
            f"     • Токены: {input_tokens:,} вход / {output_tokens:,} выход\n"
            f"     • Стоимость: {text_cost:.6f} USD\n"
        )
    
    # Изображения
    img_count = image_stats.get("count", 0)
    if img_count > 0:
        img_cost = image_stats.get("cost_usd", 0.0)
        text += (
            f"  🖼 Изображения: {img_count} шт.\n"
            f"     • Стоимость: {img_cost:.6f} USD\n"
        )
    
    # Видео
    vid_count = video_stats.get("count", 0)
    if vid_count > 0:
        vid_cost = video_stats.get("cost_usd", 0.0)
        vid_seconds = video_stats.get("seconds", 0)
        text += (
            f"  🎬 Видео: {vid_count} шт. ({vid_seconds} сек)\n"
            f"     • Стоимость: {vid_cost:.6f} USD\n"
        )
    
    if total_requests == 0:
        text += "  Пока нет запросов.\n"
    
    text += (
        f"\n<b>Курс USD/RUB:</b> {rate:.2f} ({rate_status}, {rate_source})\n\n"
        f"<i>Сбросить статистику: /reset_cost</i>"
    )
    
    await message.answer(text, parse_mode="HTML")


# === Команда /reset_cost ===

@router.message(Command("reset_cost"))
async def cmd_reset_cost(message: Message) -> None:
    """Обработчик команды /reset_cost — сбрасывает статистику расходов."""
    chat_id = message.chat.id
    memory.clear_billing(chat_id)
    
    await message.answer(
        "🗑 <b>Статистика расходов сброшена.</b>\n\n"
        "Счётчик начинается с нуля.",
        parse_mode="HTML"
    )


# === Команда /image ===

@router.message(Command("image"))
async def cmd_image(message: Message, command: CommandObject) -> None:
    """Обработчик команды /image — генерация изображения."""
    chat_id = message.chat.id
    prompt = command.args
    
    if not prompt or not prompt.strip():
        await message.answer(
            "🖼 <b>Генерация изображения</b>\n\n"
            "Использование: /image &lt;описание&gt;\n\n"
            "Пример: /image космический кот в скафандре",
            parse_mode="HTML"
        )
        return
    
    prompt = prompt.strip()
    
    # Отправляем индикатор
    await message.bot.send_chat_action(chat_id, "upload_photo")
    status_msg = await message.answer("🎨 Генерирую изображение...")
    
    try:
        # Генерируем изображение
        image_bytes, meta = await generate_image(prompt)
        
        # Получаем курс и обновляем billing
        rate, _ = await get_usd_to_rub()
        memory.update_billing(chat_id, meta, rate)
        
        # Формируем caption
        cost_usd = meta.get("cost_usd", 0.0)
        cost_rub = cost_usd * rate
        
        caption = f"🖼 <b>Готово!</b>\n<i>{prompt[:200]}</i>"
        
        if config.show_cost_each_reply:
            caption += f"\n\n💰 Стоимость: {format_cost_line(cost_usd, cost_rub)}"
        
        # Удаляем статус
        await status_msg.delete()
        
        # Отправляем изображение
        photo = BufferedInputFile(image_bytes, filename="image.png")
        await message.answer_photo(photo, caption=caption, parse_mode="HTML")
        
    except Exception as e:
        print(f"Ошибка генерации изображения для chat_id={chat_id}: {e}")
        
        await status_msg.edit_text(
            "⚠️ <b>Ошибка генерации изображения</b>\n\n"
            "Попробуйте изменить описание или повторить позже.",
            parse_mode="HTML"
        )


# === Команда /video ===
# Флаг для включения/выключения функционала видео
# Верификация пройдена — функционал включён
VIDEO_ENABLED = True


@router.message(Command("video"))
async def cmd_video(message: Message, command: CommandObject) -> None:
    """Обработчик команды /video — генерация видео (временно отключено)."""
    
    # Проверяем, включена ли функция
    if not VIDEO_ENABLED:
        await message.answer(
            "🎬 <b>Генерация видео временно отключена</b>\n\n"
            "<i>Пока можете использовать /image для генерации изображений.</i>",
            parse_mode="HTML"
        )
        return
    
    # === Код ниже будет работать когда VIDEO_ENABLED = True ===
    
    chat_id = message.chat.id
    prompt = command.args
    
    if not prompt or not prompt.strip():
        await message.answer(
            "🎬 <b>Генерация видео</b>\n\n"
            f"Использование: /video &lt;описание&gt;\n\n"
            f"Параметры: {config.video_seconds} сек, {config.video_size}\n\n"
            "Пример: /video плавный полёт над горами на рассвете",
            parse_mode="HTML"
        )
        return
    
    prompt = prompt.strip()
    
    # Отправляем статус
    status_msg = await message.answer(
        f"🎬 <b>Генерирую видео...</b>\n\n"
        f"Это может занять до {config.video_max_wait_seconds // 60} мин.\n"
        f"Параметры: {config.video_seconds} сек, модель {config.video_model}",
        parse_mode="HTML"
    )
    
    await message.bot.send_chat_action(chat_id, "upload_video")
    
    try:
        # Генерируем видео
        video_bytes, meta = await generate_video(prompt)
        
        # Получаем курс и обновляем billing
        rate, _ = await get_usd_to_rub()
        memory.update_billing(chat_id, meta, rate)
        
        # Формируем caption
        cost_usd = meta.get("cost_usd", 0.0)
        cost_rub = cost_usd * rate
        seconds = meta.get("seconds", config.video_seconds)
        
        caption = f"🎬 <b>Готово!</b> ({seconds} сек)\n<i>{prompt[:200]}</i>"
        
        if config.show_cost_each_reply:
            caption += f"\n\n💰 Стоимость: {format_cost_line(cost_usd, cost_rub)}"
        
        # Сохраняем временно если нужно, иначе отправляем напрямую
        video_id = meta.get("video_id", "video")
        
        if config.debug_keep_media:
            # Сохраняем в data/tmp/
            tmp_dir = Path("data/tmp")
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / f"{video_id}.mp4"
            tmp_path.write_bytes(video_bytes)
            print(f"Видео сохранено: {tmp_path}")
        
        # Удаляем статус
        await status_msg.delete()
        
        # Отправляем видео
        video_file = BufferedInputFile(video_bytes, filename=f"{video_id}.mp4")
        await message.answer_video(video_file, caption=caption, parse_mode="HTML")
        
    except TimeoutError as e:
        await status_msg.edit_text(
            "⏱ <b>Превышено время ожидания</b>\n\n"
            f"Генерация видео заняла слишком много времени.\n"
            "Попробуйте упростить описание или повторить позже.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"Ошибка генерации видео для chat_id={chat_id}: {e}")
        
        await status_msg.edit_text(
            "⚠️ <b>Ошибка генерации видео</b>\n\n"
            "Попробуйте изменить описание или повторить позже.\n"
            f"<code>{str(e)[:100]}</code>",
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
        
        # Получаем курс и обновляем billing
        rate, _ = await get_usd_to_rub()
        memory.update_billing(chat_id, meta, rate)
        
        # Формируем ответ
        response_text = assistant_text
        
        if config.show_cost_each_reply:
            cost_usd = meta.get("cost_usd", 0.0)
            cost_rub = cost_usd * rate
            response_text += f"\n\n<i>💰 {format_cost_line(cost_usd, cost_rub)}</i>"
            await message.answer(response_text, parse_mode="HTML")
        else:
            await message.answer(response_text)
        
    except Exception as e:
        # Логируем ошибку
        print(f"Ошибка OpenAI для chat_id={chat_id}: {e}")
        
        # Отправляем аккуратное сообщение пользователю
        await message.answer(
            "⚠️ Извините, произошла ошибка при обработке запроса.\n"
            "Попробуйте ещё раз или измените сообщение."
        )
