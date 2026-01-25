# Telegram AI Bot

Минималистичный Telegram-бот на Python с поддержкой OpenAI API.

## Возможности

- 💬 **Диалог с AI** — общение через OpenAI GPT модели
- 🎭 **Режимы** — разные персонажи/стили ответов (настраиваются в `prompts.json`)
- 🧠 **Память** — бот помнит контекст диалога (последние N пар сообщений)
- 💾 **Persistence** — история сохраняется в файл и переживает перезапуск

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

Обязательные переменные:
- `TELEGRAM_BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
- `OPENAI_API_KEY` — API ключ от [OpenAI](https://platform.openai.com/api-keys)

### 3. Запуск

```bash
python main.py
```

## Конфигурация

### Переменные окружения (.env)

| Переменная | Обязательная | По умолчанию | Описание |
|------------|--------------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Токен Telegram бота |
| `OPENAI_API_KEY` | ✅ | — | API ключ OpenAI |
| `OPENAI_MODEL` | ❌ | `gpt-4` | Модель OpenAI |
| `HISTORY_PAIRS_LIMIT` | ❌ | `5` | Количество пар сообщений в памяти |
| `MEMORY_FILE_PATH` | ❌ | `data/memory.json` | Путь к файлу памяти |
| `USD_RUB_RATE` | ❌ | `92.50` | Курс для расчёта стоимости |

### Режимы (prompts.json)

Файл `prompts.json` определяет доступные режимы бота:

```json
{
  "assistant": {
    "name": "Ассистент",
    "description": "Универсальный помощник",
    "system_prompt": "Ты — полезный AI-ассистент. Отвечай кратко и по делу."
  },
  "programmer": {
    "name": "Программист",
    "description": "Помощь с кодом",
    "system_prompt": "Ты — опытный программист. Помогай с кодом, объясняй концепции."
  }
}
```

Каждый режим содержит:
- `name` — отображаемое имя
- `description` — описание для меню
- `system_prompt` — системный промпт для OpenAI

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и справка |
| `/mode` | Выбор режима общения |
| `/reset` | Очистка истории диалога |

## Структура проекта

```
openai_bot/
├── main.py              # Точка входа
├── config.py            # Конфигурация из .env
├── prompts.json         # Режимы бота
├── requirements.txt     # Зависимости
├── .env.example         # Пример конфигурации
├── README.md            # Документация
├── bot/
│   ├── __init__.py
│   └── handlers.py      # Обработчики команд и сообщений
├── storage/
│   ├── __init__.py
│   └── memory_store.py  # Хранилище памяти (JSON)
├── services/
│   ├── __init__.py
│   └── openai_client.py # Клиент OpenAI API
├── utils/
│   ├── __init__.py
│   └── file_utils.py    # Утилиты работы с файлами
└── data/
    └── memory.json      # Память (создаётся автоматически)
```

## Архитектура

### Модули

- **config.py** — загрузка и валидация конфигурации
- **bot/handlers.py** — роутеры aiogram, обработка команд
- **storage/memory_store.py** — персистентное хранилище диалогов
- **services/openai_client.py** — взаимодействие с OpenAI API
- **utils/file_utils.py** — безопасная работа с файлами

### Расширяемость

Проект подготовлен для добавления:

1. **Генерация изображений** — заглушка `generate_image()` в `services/openai_client.py`
2. **Генерация видео** — заглушка `generate_video()` в `services/openai_client.py`
3. **Billing** — функция `estimate_cost()` и статистика в `MemoryStore`

Все функции генерации возвращают `(result, meta)`, где `meta` содержит данные для billing.

## Память диалогов

- Хранится в `data/memory.json` (путь настраивается)
- Для каждого чата сохраняются последние N пар сообщений
- N настраивается через `HISTORY_PAIRS_LIMIT` (по умолчанию 5)
- Режим чата сохраняется отдельно от истории
- При `/reset` очищается только история, режим сохраняется

## Лицензия

MIT
