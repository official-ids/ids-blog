---
title: "CipherNest — Telegram-бот для криптографии"
date: 2026-04-07
tags: [проект, разработка]
preview: "Self-hosted Telegram-бот с 25+ алгоритмами шифрования: AES, RSA, ChaCha20, Argon2id — всё в одном боте..."
---

# CipherNest — Telegram Crypto Bot 🔐

Self-hosted Telegram-бот для криптографических операций и кодирования данных.

## 🛠️ Стек

- **Python** + **aiogram 3**
- **cryptography**, **argon2-cffi**
- **Docker** & **Docker Compose**

## ⚡ Возможности

- **25+ алгоритмов**: AES-256-GCM, ChaCha20, RSA-2048, Ed25519, SHA-2/3, BLAKE2b, Argon2id, JWT decode, ZLIB и другие
- **Chain Mode** — последовательное преобразование данных через цепочку алгоритмов
- **Автоопределение формата** входных данных

## 🔒 Приватность

- Stateless обработка только в RAM
- Нулевое логирование на диск
- Rate limit: 10 запросов/мин

## 🚀 Деплой

```bash
docker compose up -d
```

Optional: Redis для сессий. 44 юнит-теста, MIT License.

🔗 [Репозиторий →](https://github.com/official-ids/CipherNest-Telegram-Crypto-Bot)

---

*Опубликовано: 7 апреля 2026*
