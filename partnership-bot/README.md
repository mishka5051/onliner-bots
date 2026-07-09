# Partnership Bot

Автономный Telegram-бот для приёма заявок на инфопартнёрство Onlíner.

**Не зависит от основного веб-сервиса** — заявки и черновики хранятся в локальном SQLite.

## Бот

[@onliner_partnership_bot](https://t.me/onliner_partnership_bot) — команды `/apply`, `/status`, `/cancel`.

## Запуск

```bash
cp .env.example .env
# TELEGRAM_BOT_TOKEN=...

docker compose up -d --build
```

## Переменные

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота заявок |
| `NOTIFY_TELEGRAM_IDS` | ID сотрудников для push о новых заявках |
| `BOT_DATA_DIR` | Каталог SQLite (по умолчанию `data`) |

Данные: `data/partnership.sqlite3` (volume `partnership-leads-data`, общий с event-search-bot).

## Отдельно от других компонентов

| Компонент | Папка | Роль |
|-----------|-------|------|
| **Этот бот** | `partnership-bot/` | Приём заявок |
| **Поиск** | `event-search-bot/` | Поиск мероприятий |
| **Веб-сервис** | `2/` | API, админка, веб-форма (опционально) |

Три проекта независимы. Боты связаны только через volume `partnership-leads-data`.
