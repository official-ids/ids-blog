#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор ленты блога для GitHub
Сканирует папку /posts, парсит frontmatter и генерирует:
- feed.json (индекс всех постов)
- README.md (красивая лента)
- atom.xml (RSS-фид для RSS-ридеров)
"""

import os
import re
import sys
import json
import glob
import logging
from datetime import datetime, timezone, time
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

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

# Пути к файлам
ROOT_DIR = Path(__file__).parent.parent
POSTS_DIR = ROOT_DIR / "posts"
CONFIG_FILE = ROOT_DIR / "config.json"
FEED_FILE = ROOT_DIR / "feed.json"
README_FILE = ROOT_DIR / "README.md"
ATOM_FILE = ROOT_DIR / "atom.xml"


def load_config():
    """Загружает конфигурацию из config.json"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл конфига не найден: {CONFIG_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка JSON в конфиге: {e}")
        sys.exit(1)


def extract_date_from_filename(filename):
    """Извлекает дату из имени файла формата YYYY-MM-DD_..."""
    match = re.match(r'^(\d{4}-\d{2}-\d{2})_', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            return None
    return None


def parse_frontmatter(filepath):
    """
    Парсит frontmatter из Markdown файла с помощью python-frontmatter
    Возвращает dict с метаданными и содержимым поста
    """
    filename = Path(filepath).name

    # Парсим frontmatter
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
    except Exception as e:
        raise ValueError(f"Ошибка чтения файла {filename}: {e}")

    # Извлекаем метаданные
    metadata = dict(post.metadata)
    metadata['body'] = post.content
    metadata['filename'] = filename
    # Используем forward slashes для совместимости с GitHub
    metadata['filepath'] = str(Path(filepath).relative_to(ROOT_DIR)).replace('\\', '/')

    # Валидация обязательных полей
    required_fields = ['title', 'date', 'preview']
    for field in required_fields:
        if field not in metadata:
            raise ValueError(f"Отсутствует обязательное поле '{field}' в {filename}")

    # Если tags не указан, ставим пустой список
    if 'tags' not in metadata:
        metadata['tags'] = []
    elif not isinstance(metadata['tags'], list):
        # Если tags — строка, превращаем в список
        metadata['tags'] = [metadata['tags']]

    # Парсим дату если она строка или datetime.date
    if isinstance(metadata['date'], str):
        try:
            metadata['date'] = datetime.strptime(metadata['date'], '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Некорректный формат даты в {filename}. Ожидается YYYY-MM-DD")
    elif hasattr(metadata['date'], 'year') and not isinstance(metadata['date'], datetime):
        # datetime.date -> datetime
        from datetime import time
        metadata['date'] = datetime.combine(metadata['date'], time.min)

    # Валидация: дата в имени файла совпадает с frontmatter
    file_date = extract_date_from_filename(filename)
    if file_date and file_date != metadata['date']:
        logger.warning(
            f"⚠️  Дата в имени файла ({file_date.strftime('%Y-%m-%d')}) не совпадает "
            f"с датой в frontmatter ({metadata['date'].strftime('%Y-%m-%d')}) в {filename}"
        )

    return metadata


def scan_posts():
    """Сканирует папку posts и возвращает отсортированный список постов"""
    post_files = glob.glob(str(POSTS_DIR / "*.md"))

    if not post_files:
        logger.warning("Посты не найдены в папке /posts")
        return []

    posts = []
    errors = []

    for filepath in post_files:
        try:
            metadata = parse_frontmatter(filepath)
            posts.append(metadata)
        except Exception as e:
            error_msg = f"Ошибка парсинга {Path(filepath).name}: {e}"
            logger.error(f"❌ {error_msg}")
            errors.append(error_msg)

    # Если есть ошибки — показываем сводку
    if errors:
        logger.error(f"\n{'='*50}")
        logger.error(f"НАЙДЕНО ОШИБОК: {len(errors)}")
        logger.error(f"{'='*50}")
        for err in errors:
            logger.error(f"  • {err}")
        logger.error(f"{'='*50}")
        logger.error("Исправьте ошибки перед коммитом!")
        sys.exit(1)

    # Сортируем по дате (новые сверху)
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def generate_feed_json(posts):
    """Генерирует feed.json с метаданными всех постов"""
    feed = {
        "version": "1.1",
        "generated": datetime.now().isoformat(),
        "posts_count": len(posts),
        "posts": []
    }

    for post in posts:
        feed_post = {
            "title": post['title'],
            "date": post['date'].strftime('%Y-%m-%d') if isinstance(post['date'], datetime) else str(post['date']),
            "tags": post.get('tags', []),
            "preview": post['preview'],
            "filename": post['filename'],
            "filepath": post['filepath']
        }
        feed["posts"].append(feed_post)

    return feed


def get_tag_badge(tag, config):
    """Генерирует Markdown бейдж для тега с цветом из конфига"""
    tag_colors = config.get('theme', {}).get('tag_colors', {})
    color = tag_colors.get(tag, '6c757d')  # Дефолтный серый цвет

    # shields.io принимает кириллицу напрямую, но URL должен быть safe
    # Используем оригинальный текст для label — shields.io рендерит кириллицу
    return f"![{tag}](https://img.shields.io/badge/{tag}-{color})"


def get_tag_badge_with_count(tag, count, config):
    """Генерирует бейдж тега со счётчиком и ссылкой на тег"""
    tag_colors = config.get('theme', {}).get('tag_colors', {})
    color = tag_colors.get(tag, '6c757d')

    # Ссылка на тег — оригинальный текст (GitHub рендерит кириллицу)
    return f"[![{tag} {count}](https://img.shields.io/badge/{tag}%20{count}-{color})]({tag})"


def generate_readme(posts, config):
    """Генерирует красивый README с лентой постов"""
    blog_config = config.get('blog', {})
    theme_config = config.get('theme', {})
    features = config.get('features', {})

    title = blog_config.get('title', '🎵 Мой Блог')
    description = blog_config.get('description', '')
    author = blog_config.get('author', 'Unknown')
    posts_limit = blog_config.get('posts_per_page', 10)
    show_tags = blog_config.get('show_tags', True)
    show_preview = blog_config.get('show_preview', True)
    show_image_preview = blog_config.get('show_image_preview', True)

    # Заголовок с бейджами статистики
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    header = f"""# {title}

{description}

---

"""

    # Бейджи статистики
    badges = []
    if features.get('last_updated_badge'):
        badges.append(f"![Updated](https://img.shields.io/badge/Updated-{now_str.replace(' ', '%20')}-blue)")
    if features.get('post_count_badge'):
        badges.append(f"![Posts](https://img.shields.io/badge/Posts-{len(posts)}-green)")

    if badges:
        header += " | ".join(badges) + "\n\n"

    # Ссылка на «пост дня» — детерминированный выбор на основе текущей даты
    if features.get('random_post_link') and posts:
        import hashlib
        today_str = datetime.now().strftime('%Y-%m-%d')
        hash_val = int(hashlib.md5(today_str.encode()).hexdigest(), 16)
        selected_post = posts[hash_val % len(posts)]
        header += f"\n🎲 [Пост дня →]({selected_post['filepath']})\n\n"

    # Облако тегов
    if features.get('tag_cloud'):
        all_tags = {}
        for post in posts:
            for tag in post.get('tags', []):
                all_tags[tag] = all_tags.get(tag, 0) + 1

        if all_tags:
            header += "### 🏷️ Облако тегов\n\n"
            tag_badges = []
            for tag, count in sorted(all_tags.items(), key=lambda x: x[1], reverse=True):
                badge = get_tag_badge_with_count(tag, count, config)
                tag_badges.append(badge)
            header += " ".join(tag_badges) + "\n\n"

    header += "---\n\n"

    # Лента постов
    posts_section = "## 📝 Лента постов\n\n"

    for i, post in enumerate(posts[:posts_limit]):
        date_str = post['date'].strftime('%d.%m.%Y') if isinstance(post['date'], datetime) else str(post['date'])
        post_title = post['title']
        preview = post.get('preview', '')
        filepath = post['filepath']
        tags = post.get('tags', [])
        body = post.get('body', '')

        # Заголовок поста
        posts_section += f"### 📌 {date_str} | {post_title}\n\n"

        # Извлекаем первое изображение из поста для превью (если включено)
        if show_image_preview and body:
            image_match = re.search(r'!\[.*?\]\((.*?)\)', body)
            if image_match:
                img_url = image_match.group(1)
                posts_section += f'<img src="{img_url}" width="150" align="right" style="margin: 0 0 8px 12px; max-width: 100%; height: auto; border-radius: 8px;">\n\n'

        # Превью
        if show_preview and preview:
            posts_section += f"> {preview}\n\n"

        # Теги
        if show_tags and tags:
            tag_badges = [get_tag_badge(tag, config) for tag in tags]
            posts_section += " ".join(tag_badges) + "\n\n"

        # Ссылка на полный текст
        posts_section += f"🔗 [Читать полностью →]({filepath})\n\n"

        # Разделитель (не для последнего поста)
        if i < min(len(posts), posts_limit) - 1:
            posts_section += "---\n\n"

    # Футер
    footer = f"""---

💬 *Автор: {author}* | 🔄 *Лента обновляется автоматически через GitHub Actions*

"""

    return header + posts_section + footer


def generate_atom_xml(posts, config):
    """Генерирует Atom XML фид для RSS-ридеров"""
    blog_config = config.get('blog', {})
    title = blog_config.get('title', '🎵 Мой Блог')
    description = blog_config.get('description', '')
    author = blog_config.get('author', 'Unknown')

    # Базовый URL (GitHub Pages)
    repo_url = os.environ.get('REPO_URL', 'https://github.com/your-username/VoiceBot')

    # Atom namespace
    NS = 'http://www.w3.org/2005/Atom'
    ET.register_namespace('', NS)

    # Создаём корневой элемент
    feed = ET.Element('feed', xmlns=NS)

    # Метаданные фида
    ET.SubElement(feed, 'title').text = title
    ET.SubElement(feed, 'subtitle').text = description
    ET.SubElement(feed, 'link', href=repo_url, rel='alternate')
    ET.SubElement(feed, 'link', href=f'{repo_url}/atom.xml', rel='self')
    ET.SubElement(feed, 'updated').text = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    ET.SubElement(feed, 'id').text = repo_url

    author_elem = ET.SubElement(feed, 'author')
    ET.SubElement(author_elem, 'name').text = author

    # Добавляем посты
    for post in posts[:20]:  # Последние 20 постов
        date_str = post['date'].strftime('%Y-%m-%d') if isinstance(post['date'], datetime) else str(post['date'])
        post_title = post['title']
        preview = post.get('preview', '')
        filepath = post.get('filepath', '')
        body = post.get('body', '')
        tags = post.get('tags', [])

        # URL поста
        post_url = f"{repo_url}/{filepath}"

        entry = ET.SubElement(feed, 'entry')
        ET.SubElement(entry, 'title').text = post_title
        ET.SubElement(entry, 'link', href=post_url, rel='alternate')
        ET.SubElement(entry, 'id').text = post_url
        ET.SubElement(entry, 'updated').text = f"{date_str}T00:00:00Z"
        ET.SubElement(entry, 'published').text = f"{date_str}T00:00:00Z"

        # Контент (превью + тело)
        content_text = f"<p>{preview}</p>\n\n{body}"
        ET.SubElement(entry, 'content', type='html').text = content_text

        # Теги как категории
        for tag in tags:
            ET.SubElement(entry, 'category', term=tag)

        # Автор
        entry_author = ET.SubElement(entry, 'author')
        ET.SubElement(entry_author, 'name').text = author

    # Форматируем XML красиво
    rough_string = ET.tostring(feed, encoding='unicode')
    parsed = minidom.parseString(rough_string)
    return parsed.toprettyxml(indent="  ", encoding=None)


def main():
    """Основная функция"""
    logger.info("🚀 Запуск генератора ленты блога...")

    # Загружаем конфиг
    config = load_config()
    logger.info(f"✅ Загружен конфиг: {config['blog']['title']}")

    # Проверяем папку posts
    if not POSTS_DIR.exists():
        logger.error(f"❌ Папка постов не найдена: {POSTS_DIR}")
        sys.exit(1)

    # Сканируем посты
    logger.info(f"📂 Сканирование папки {POSTS_DIR}...")
    posts = scan_posts()
    logger.info(f"✅ Найдено постов: {len(posts)}")

    if not posts:
        logger.warning("⚠️  Посты не найдены. Создайте хотя бы один пост в папке /posts")
        return

    # Генерируем feed.json
    logger.info("📄 Генерация feed.json...")
    feed_data = generate_feed_json(posts)
    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        json.dump(feed_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Сохранён: {FEED_FILE}")

    # Генерируем README.md
    logger.info("📄 Генерация README.md...")
    readme_content = generate_readme(posts, config)
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    logger.info(f"✅ Сохранён: {README_FILE}")

    # Генерируем atom.xml
    logger.info("📄 Генерация atom.xml...")
    atom_content = generate_atom_xml(posts, config)
    with open(ATOM_FILE, 'w', encoding='utf-8') as f:
        f.write(atom_content)
    logger.info(f"✅ Сохранён: {ATOM_FILE}")

    logger.info("\n✨ Генерация завершена успешно!")


if __name__ == "__main__":
    main()
