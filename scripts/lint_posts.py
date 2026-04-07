#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Линтер постов блога
Проверяет все посты на корректность frontmatter и формата
Запускается ДО генерации ленты для быстрой обратной связи
"""

import re
import sys
import logging
from datetime import datetime
from pathlib import Path

try:
    import frontmatter
except ImportError:
    print("❌ Отсутствует библиотека python-frontmatter")
    print("   Установите: pip install python-frontmatter")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Пути
ROOT_DIR = Path(__file__).parent.parent
POSTS_DIR = ROOT_DIR / "posts"

# Паттерн имени файла: YYYY-MM-DD_slug.md
FILENAME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}_.+\.md$')

# Обязательные поля frontmatter
REQUIRED_FIELDS = ['title', 'date', 'preview', 'tags']

# Рекомендуемая минимальная длина превью
MIN_PREVIEW_LENGTH = 50

# Максимальная длина заголовка
MAX_TITLE_LENGTH = 100


def validate_filename(filepath):
    """Проверяет формат имени файла"""
    filename = Path(filepath).name
    errors = []

    if not FILENAME_PATTERN.match(filename):
        errors.append(
            f"Некорректный формат имени файла: '{filename}'.\n"
            f"  Ожидается: YYYY-MM-DD_описание.md\n"
            f"  Пример: 2026-04-07_мой-пост.md"
        )

    return errors


def validate_date_consistency(filepath, metadata):
    """Проверяет совпадение даты в имени файла и frontmatter"""
    filename = Path(filepath).name
    errors = []

    # Извлекаем дату из имени файла
    match = re.match(r'^(\d{4}-\d{2}-\d{2})_', filename)
    if match:
        try:
            file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
            frontmatter_date = metadata.get('date')

            # Нормализуем к datetime
            if isinstance(frontmatter_date, str):
                frontmatter_date = datetime.strptime(frontmatter_date, '%Y-%m-%d')
            elif hasattr(frontmatter_date, 'year'):
                # datetime.date -> datetime
                frontmatter_date = datetime(frontmatter_date.year, frontmatter_date.month, frontmatter_date.day)
            else:
                errors.append(f"Некорректный тип даты в frontmatter: {type(frontmatter_date)}")
                return errors

            if file_date != frontmatter_date:
                errors.append(
                    f"Дата в имени файла ({file_date.strftime('%Y-%m-%d')}) "
                    f"не совпадает с frontmatter ({frontmatter_date.strftime('%Y-%m-%d')})"
                )
        except ValueError as e:
            errors.append(f"Ошибка парсинга даты: {e}")

    return errors


def validate_fields(metadata, filename):
    """Проверяет наличие и корректность обязательных полей"""
    errors = []

    # Обязательные поля
    for field in REQUIRED_FIELDS:
        if field not in metadata:
            errors.append(f"Отсутствует обязательное поле: '{field}'")

    # Валидация title
    title = metadata.get('title', '')
    if not title or not title.strip():
        errors.append("Поле 'title' пустое")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(
            f"Заголовок слишком длинный ({len(title)} символов, макс. {MAX_TITLE_LENGTH})"
        )

    # Валидация date
    date_val = metadata.get('date')
    if date_val:
        if isinstance(date_val, str):
            try:
                datetime.strptime(date_val, '%Y-%m-%d')
            except ValueError:
                errors.append(
                    f"Некорректный формат даты: '{date_val}'. Ожидается YYYY-MM-DD"
                )
        elif isinstance(date_val, datetime):
            pass  # datetime OK
        elif hasattr(date_val, 'year'):
            pass  # datetime.date OK (has year/month/day)
        else:
            errors.append(f"Поле 'date' должно быть датой, получено: {type(date_val)}")

    # Валидация preview
    preview = metadata.get('preview', '')
    if not preview or not preview.strip():
        errors.append("Поле 'preview' пустое")
    elif len(preview) < MIN_PREVIEW_LENGTH:
        errors.append(
            f"Превью слишком короткое ({len(preview)} символов, рек. {MIN_PREVIEW_LENGTH}+)"
        )

    # Валидация tags
    tags = metadata.get('tags', [])
    if tags:
        if not isinstance(tags, list):
            errors.append(f"Поле 'tags' должно быть списком, получено: {type(tags)}")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(f"Тег должен быть строкой: {tag}")

    return errors


def validate_body(metadata, filepath):
    """Проверяет содержимое поста"""
    errors = []
    filename = Path(filepath).name

    # Проверяем что файл не пустой
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Проверяем наличие frontmatter
        if not content.startswith('---'):
            errors.append("Файл не начинается с '---' (frontmatter)")

        parts = content.split('---', 2)
        if len(parts) < 3:
            errors.append("Некорректный frontmatter (отсутствует закрывающий '---')")

        body = parts[2].strip() if len(parts) >= 3 else ''

        # Проверяем что тело поста не пустое
        if not body:
            errors.append("Тело поста пустое")
        elif len(body) < 100:
            errors.append(
                f"Тело поста слишком короткое ({len(body)} символов). "
                f"Может стоит добавить больше контента?"
            )

    except UnicodeDecodeError:
        errors.append("Файл не является UTF-8 текстом")
    except Exception as e:
        errors.append(f"Ошибка чтения файла: {e}")

    return errors


def lint_post(filepath):
    """Полная проверка одного поста"""
    filename = Path(filepath).name
    all_errors = []

    # 1. Проверка имени файла
    all_errors.extend(validate_filename(filepath))

    # 2. Парсинг frontmatter
    try:
        post = frontmatter.load(filepath)
        metadata = dict(post.metadata)
    except Exception as e:
        all_errors.append(f"Ошибка парсинга frontmatter: {e}")
        return all_errors  # Не можем продолжить без метаданных

    # 3. Проверка обязательных полей
    all_errors.extend(validate_fields(metadata, filename))

    # 4. Проверка совпадения дат
    all_errors.extend(validate_date_consistency(filepath, metadata))

    # 5. Проверка содержимого
    all_errors.extend(validate_body(metadata, filepath))

    return all_errors


def lint_all_posts():
    """Проверяет все посты и выводит отчёт"""
    logger.info("🔍 Запуск линтера постов...")

    if not POSTS_DIR.exists():
        logger.error(f"❌ Папка постов не найдена: {POSTS_DIR}")
        sys.exit(1)

    post_files = sorted(POSTS_DIR.glob("*.md"))

    if not post_files:
        logger.warning("⚠️  Посты не найдены")
        return

    total_errors = 0
    files_checked = 0

    for filepath in post_files:
        errors = lint_post(filepath)
        files_checked += 1

        if errors:
            total_errors += len(errors)
            logger.error(f"\n❌ {filepath.name}")
            for err in errors:
                logger.error(f"  • {err}")
        else:
            logger.info(f"✅ {filepath.name}")

    # Итоговый отчёт
    logger.info(f"\n{'='*50}")
    logger.info(f"Проверено файлов: {files_checked}")
    logger.info(f"Найдено ошибок: {total_errors}")

    if total_errors > 0:
        logger.error(f"{'='*50}")
        logger.error("❌ Линтер нашёл ошибки. Исправьте их перед коммитом!")
        sys.exit(1)
    else:
        logger.info(f"{'='*50}")
        logger.info("✨ Все посты корректны!")


if __name__ == "__main__":
    lint_all_posts()
