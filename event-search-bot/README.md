# Event Search Bot

Автономный Telegram-бот для поиска мероприятий под инфопартнёрства Onliner.  
**Не зависит от основного веб-сервиса** — глубокий поиск выполняется внутри бота с той же логикой: SearXNG → загрузка страниц → каталоги → скоринг.

## Режимы

### 🔍 Быстрый поиск

Кнопка в меню, `/search` или текст в чате (после выбора режима).

SearXNG → ранжирование по ключевым словам → список ссылок за несколько секунд.

### 🔬 Глубокий поиск

Кнопка в меню или `/deep запрос`.

1. Расширенный поиск в SearXNG (больше страниц и лимитов, чем у сервиса в `../2`).
2. Обогащение страниц, разворачивание каталогов, скоринг по `scoring_rules.yaml`.
3. **Работает в фоне** — можно пользоваться другими функциями бота.
4. По завершении: выжимка + кнопки **Выгрузка** (фильтры → CSV/HTML), **Аналитика**, **Карточки**, **Отправить коллеге**.

### 🕐 История и шаблоны

- Последние 10 поисков с кнопкой «Повторить»
- Шаблоны: **IT Минск**, **E-commerce**, **Выставки 2026**

SearXNG теперь поднимается автоматически вместе с этим ботом (`docker compose up`).
Сервис на 8001 не требуется.

## Быстрый старт

### Для другого человека (с нуля)

Нужно только:
- Docker + Docker Compose
- токен @BotFather для каждого бота

Порядок запуска:

```bash
cd partnership-bot
cp .env.example .env
# TELEGRAM_BOT_TOKEN=...
docker compose up -d --build

cd ../event-search-bot
cp .env.example .env
# TELEGRAM_BOT_TOKEN=...
docker compose up -d --build
```

Почему такой порядок: `partnership-bot` создаёт общий Docker volume `partnership-leads-data`,
который использует `event-search-bot`.

### 1. Бот (локально)

```bash
cd event-search-bot
cp .env.example .env
# TELEGRAM_BOT_TOKEN=...

pip install -e .
event-search-bot
```

Docker (бот + встроенный SearXNG):

```bash
cp .env.example .env
docker compose up -d --build
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `SEARXNG_BASE_URL` | URL SearXNG (`http://searxng:8080` в docker-compose) |
| `SEARCH_RESULTS_LIMIT` | Результатов быстрого поиска (10) |
| `DEEP_SEARCH_RESULTS_LIMIT` | Ссылок из SearXNG в глубоком поиске (80) |
| `DEEP_SEARCH_PAGES_MAX` | Страниц SearXNG в глубоком поиске (4) |
| `DEEP_ENRICHMENT_MAX_EVENTS` | Макс. обработанных карточек за задание (400) |
| `DEEP_CATALOG_EXPANSION_MAX` | Лимит ссылок из каталогов (150) |
| `BOT_DATA_DIR` | Каталог SQLite (история поисков) |
| `PARTNERSHIP_DATA_DIR` | Путь к общей БД заявок (`partnership-data` в Docker) |
| `ALLOWED_TELEGRAM_IDS` | ID сотрудников (заявки + уведомления) |
| `LEADS_POLL_INTERVAL_SEC` | Опрос новых заявок (90) |

## Связь с partnership-ботом

Заявки пишет [@onliner_partnership_bot](https://t.me/onliner_partnership_bot) в SQLite.  
Search-бот **читает тот же файл** через общий Docker volume `partnership-leads-data` — **без веб-сервиса**.

```text
partnership-bot ──write──► partnership.sqlite3 ◄──read── event-search-bot
                              (shared volume)
```

Сначала поднимите partnership-bot (создаёт volume), затем search-bot.

Полный список — в `.env.example`.

## Команды и меню

- `/start` — главное меню с кнопками
- `/search` — быстрый поиск
- `/deep` — глубокий поиск (фон)
- `/help` — справка
- **📋 Мои задания** — статус фоновых поисков
- **🕐 История** — повторить прошлый запрос

После глубокого поиска: фильтры выгрузки, аналитика, карточки, пересылка коллеге.

## Отдельно от других компонентов

| Компонент | Папка |
|-----------|-------|
| **Заявки** | `partnership-bot/` | Пишет в общий SQLite |
| **Поиск** | `event-search-bot/` | Читает тот же SQLite |
| **Веб-сервис** | `2/` | API и админка (опционально) |

## Отличие от бота в `../2`

В основном проекте — бот **заявок на инфопартнёрство**. Этот бот — **поиск мероприятий** с собственным пайплайном.
