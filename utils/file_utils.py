"""
Утилиты для работы с файловой системой.
Обеспечивают безопасное создание директорий и запись JSON.
"""

import json
import os
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """
    Создаёт директорию, если она не существует.
    
    Args:
        path: Путь к директории
        
    Returns:
        Path объект созданной/существующей директории
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def ensure_file(path: str | Path, default_content: Any = None) -> Path:
    """
    Создаёт файл с дефолтным содержимым, если он не существует.
    Также создаёт родительские директории при необходимости.
    
    Args:
        path: Путь к файлу
        default_content: Содержимое по умолчанию (для JSON — dict/list)
        
    Returns:
        Path объект файла
    """
    file_path = Path(path)
    
    # Создаём родительскую директорию
    ensure_dir(file_path.parent)
    
    # Создаём файл, если не существует
    if not file_path.exists():
        if default_content is not None:
            safe_write_json(file_path, default_content)
        else:
            file_path.touch()
    
    return file_path


def safe_write_json(path: str | Path, data: Any, indent: int = 2) -> bool:
    """
    Безопасно записывает данные в JSON файл.
    Использует временный файл для атомарной записи (защита от повреждения при сбое).
    
    Args:
        path: Путь к файлу
        data: Данные для записи
        indent: Отступ для форматирования JSON
        
    Returns:
        True если запись успешна, False при ошибке
    """
    file_path = Path(path)
    temp_path = file_path.with_suffix(".json.tmp")
    
    try:
        # Убедимся, что директория существует
        ensure_dir(file_path.parent)
        
        # Пишем во временный файл
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        
        # Атомарно заменяем оригинал
        temp_path.replace(file_path)
        return True
        
    except Exception as e:
        print(f"Ошибка записи JSON в {path}: {e}")
        # Удаляем временный файл при ошибке
        if temp_path.exists():
            temp_path.unlink()
        return False


def safe_read_json(path: str | Path, default: Any = None) -> Any:
    """
    Безопасно читает JSON файл.
    
    Args:
        path: Путь к файлу
        default: Значение по умолчанию, если файл не существует или повреждён
        
    Returns:
        Распарсенные данные или default при ошибке
    """
    file_path = Path(path)
    
    if not file_path.exists():
        return default
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON из {path}: {e}")
        return default
    except Exception as e:
        print(f"Ошибка чтения {path}: {e}")
        return default
