#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор ленты блога для GitHub
Сканирует папку /posts, парсит frontmatter и генерирует:
- feed.json (индекс всех постов)
- README.md (красивая лента)
"""

import os
import re
import json
import glob
from datetime import datetime
from pathlib import Path

# Пути к файлам
ROOT_DIR = Path(__file__).parent.parent
POSTS_DIR = ROOT_DIR / "posts"
CONFIG_FILE = ROOT_DIR / "config.json"
FEED_FILE = ROOT_DIR / "feed.json"
README_FILE = ROOT_DIR / "README.md"
README_TEMPLATE = ROOT_DIR / "templates" / "README.template.md"


def load_config():
    """Загружает конфигурацию из config.json"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_frontmatter(filepath):
    """
    Парсит frontmatter из Markdown файла
    Возвращает dict с метаданными и содержимым поста
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем наличие frontmatter (должен начинаться с ---)
    if not content.startswith('---'):
        raise ValueError(f"Файл {filepath.name} не имеет frontmatter (должен начинаться с ---)")
    
    # Находим конец frontmatter
    parts = content.split('---', 2)
    if len(parts) < 3:
        raise ValueError(f"Файл {filepath.name} имеет некорректный frontmatter (отсутствует закрывающий ---)")
    
    frontmatter_str = parts[1].strip()
    body = parts[2].strip()
    
    # Парсим поля frontmatter
    metadata = {}
    for line in frontmatter_str.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Поддержка списков (tags: [tag1, tag2])
        list_match = re.match(r'^(\w+):\s*\[(.*?)\]$', line)
        if list_match:
            key = list_match.group(1)
            values = [v.strip().strip('"\'') for v in list_match.group(2).split(',')]
            metadata[key] = values
            continue
        
        # Поддержка строковых и числовых значений
        kv_match = re.match(r'^(\w+):\s*(.+)$', line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip().strip('"\'')
            
            # Пробуем распознать дату
            if key == 'date':
                try:
                    value = datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    pass
            
            metadata[key] = value
    
    # Валидация обязательных полей
    required_fields = ['title', 'date', 'preview']
    for field in required_fields:
        if field not in metadata:
            raise ValueError(f"Файл {filepath.name} отсутствует обязательное поле: {field}")
    
    # Если tags не указан, ставим пустой список
    if 'tags' not in metadata:
        metadata['tags'] = []
    
    metadata['body'] = body
    metadata['filename'] = filepath.name
    # Используем forward slashes для совместимости с GitHub
    metadata['filepath'] = str(filepath.relative_to(ROOT_DIR)).replace('\\', '/')
    
    return metadata


def scan_posts():
    """Сканирует папку posts и возвращает отсортированный список постов"""
    post_files = glob.glob(str(POSTS_DIR / "*.md"))
    posts = []
    
    for filepath in post_files:
        try:
            metadata = parse_frontmatter(Path(filepath))
            posts.append(metadata)
        except Exception as e:
            print(f"⚠️  Ошибка парсинга {Path(filepath).name}: {e}")
            raise  # Падаем, чтобы GitHub Action показал ошибку
    
    # Сортируем по дате (новые сверху)
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def generate_feed_json(posts):
    """Генерирует feed.json с метаданными всех постов"""
    feed = {
        "version": "1.0",
        "generated": datetime.now().isoformat(),
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
    
    # Используем shields.io для бейджей
    return f"![{tag}](https://img.shields.io/badge/{tag.replace(' ', '%20')}-{color})"


def generate_readme(posts, config):
    """Генерирует красивый README с лентой постов"""
    blog_config = config.get('blog', {})
    theme_config = config.get('theme', {})
    features = config.get('features', {})
    
    title = blog_config.get('title', '🎵 Мой Блог')
    description = blog_config.get('description', '')
    author = blog_config.get('author', 'Unknown')
    posts_per_page = blog_config.get('posts_per_page', 10)
    show_tags = blog_config.get('show_tags', True)
    show_preview = blog_config.get('show_preview', True)
    
    # Заголовок с бейджем последнего обновления
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    header = f"""# {title}

{description}

---

"""
    
    # Бейджи статистики (кодируем пробелы для shields.io)
    badges = []
    if features.get('last_updated_badge'):
        badges.append(f"![Last Updated](https://img.shields.io/badge/updated-{now_str.replace('.', '-').replace(' ', '%20')}-blue)")
    if features.get('post_count_badge'):
        badges.append(f"![Posts](https://img.shields.io/badge/posts-{len(posts)}-green)")
    
    if badges:
        header += " | ".join(badges) + "\n\n"
    
    # Ссылка на случайный пост
    if features.get('random_post_link') and posts:
        import random
        random_post = random.choice(posts)
        header += f"\n🎲 [Случайный пост]({random_post['filepath']})\n\n"
    
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
                tag_colors = theme_config.get('tag_colors', {})
                color = tag_colors.get(tag, '6c757d')
                badge = f"[![{tag} {count}](https://img.shields.io/badge/{tag.replace(' ', '%20')}-{count}-{color})]({tag})"
                tag_badges.append(badge)
            header += " ".join(tag_badges) + "\n\n"
    
    header += "---\n\n"
    
    # Лента постов
    posts_section = "## 📝 Лента постов\n\n"
    
    for i, post in enumerate(posts[:posts_per_page]):
        date_str = post['date'].strftime('%d.%m.%Y') if isinstance(post['date'], datetime) else str(post['date'])
        title_post = post['title']
        preview = post.get('preview', '')
        filepath = post['filepath']
        tags = post.get('tags', [])
        
        # Заголовок поста
        posts_section += f"### 📌 {date_str} | {title_post}\n\n"
        
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
        if i < min(len(posts), posts_per_page) - 1:
            posts_section += "---\n\n"
    
    # Футер
    footer = f"""---

💬 *Автор: {author}* | 🔄 *Лента обновляется автоматически через GitHub Actions*

"""
    
    return header + posts_section + footer


def main():
    """Основная функция"""
    print("🚀 Запуск генератора ленты блога...")
    
    # Загружаем конфиг
    config = load_config()
    print(f"✅ Загружен конфиг: {config['blog']['title']}")
    
    # Сканируем посты
    print(f"📂 Сканирование папки {POSTS_DIR}...")
    posts = scan_posts()
    print(f"✅ Найдено постов: {len(posts)}")
    
    if not posts:
        print("⚠️  Посты не найдены. Создайте хотя бы один пост в папке /posts")
        return
    
    # Генерируем feed.json
    print("📄 Генерация feed.json...")
    feed_data = generate_feed_json(posts)
    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        json.dump(feed_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранён: {FEED_FILE}")
    
    # Генерируем README.md
    print("📄 Генерация README.md...")
    readme_content = generate_readme(posts, config)
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✅ Сохранён: {README_FILE}")
    
    print("\n✨ Генерация завершена успешно!")


if __name__ == "__main__":
    main()
