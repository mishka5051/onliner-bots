# Event Search Service

Сервис для поиска мероприятий в Минске и Беларуси, подходящих для инфопартнёрств Onliner. Маркетинг запускает поиск по сохранённым запросам, получает обогащённые карточки с оценкой 0–100 и работает с shortlist через веб-интерфейс.

**Стек:** FastAPI, PostgreSQL, SearXNG (метапоиск), Jinja2 UI.

---

## Как это работает

```
Поисковые запросы → SearXNG / SerpAPI / fake
        ↓
Сохранение кандидатов (дедупликация по URL)
        ↓
Обогащение: загрузка страницы, парсинг, доп. поиск
        ↓
Скоринг по правилам (config/scoring_rules.yaml)
        ↓
Shortlist и ручной review
```

**При поиске и обогащении автоматически:**

- пропускаются страницы-каталоги (афиши, расписания, списки);
- с каталогов извлекаются ссылки на отдельные события (до 15 шт.);
- отсекаются мероприятия не из Минска/Беларуси;
- считается score по критериям: город, масштаб, бесплатность, тематика Onliner, партнёрство, запас по датам.

---

## Быстрый старт (Docker)

```powershell
cd 2
copy .env.example .env
docker compose up --build -d
```

| Сервис | URL |
|--------|-----|
| Web UI | http://localhost:8001/events |
| API (Swagger) | http://localhost:8001/docs |
| SearXNG | http://localhost:8080 |
| PostgreSQL | `localhost:5433` (user/pass/db: `events` / `events` / `event_search`) |

Остановка:

```powershell
docker compose down
```

Данные БД сохраняются в Docker volume. Полная очистка: `docker compose down -v`.

---

## Работа через интерфейс

1. **Запросы** — http://localhost:8001/search-queries  
   В БД уже есть 7 примеров запросов. Можно добавить свои или отключить лишние.

2. **Поиск** — кнопка «Запустить все активные».  
   Результаты сохраняются, затем автоматически обогащаются и получают score.

3. **Мероприятия** — http://localhost:8001/events  
   Фильтры: статус, score, город, тип, дата. Пустой `min_score` в форме — допустим.

4. **Shortlist** — http://localhost:8001/events/shortlist  
   Кандидаты с score ≥ 50, в Минске, не отклонённые.

5. **Review** — на карточке мероприятия: одобрить / отклонить с комментарием.

6. **Дообогащение** — на странице запросов: «Обогатить ожидающие», если часть карточек осталась в статусе pending/failed.

---

## Провайдеры поиска

| Значение `SEARCH_PROVIDER` | Когда использовать |
|----------------------------|-------------------|
| `searxng` | По умолчанию в Docker. Бесплатно, без API-ключей |
| `serpapi` | Стабильнее SearXNG, нужен ключ на [serpapi.com](https://serpapi.com/) |
| `fake` | Тесты UI и разработка без внешнего поиска |

**SearXNG** — свой метапоиск в Docker (`config/searxng/settings.yml`).  
Проверка: http://localhost:8080 или

```powershell
curl "http://localhost:8080/search?q=конференция+Минск+2026&format=json"
```

**SerpAPI** — в `.env`:

```env
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=ваш_ключ
```

---

## Настройки (.env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | PostgreSQL | см. `.env.example` |
| `SEARCH_PROVIDER` | `fake` / `searxng` / `serpapi` | `searxng` |
| `SEARXNG_BASE_URL` | URL SearXNG | `http://localhost:8080` |
| `SERPAPI_API_KEY` | Ключ SerpAPI | пусто |
| `SEARCH_RESULTS_LIMIT` | Результатов на один запрос | `10` |
| `ENRICHMENT_ENABLED` | Автообогащение после поиска | `true` |
| `SUPPLEMENTARY_SEARCH_ENABLED` | Доп. поиск по названию | `true` |
| `SHORTLIST_MIN_SCORE` | Порог shortlist | `50` |
| `LLM_PROVIDER` | `none` или `openai` (код есть, в пайплайн не подключён) | `none` |
| `SCHEDULER_ENABLED` | Еженедельный cron (код есть, в `main.py` не запущен) | `false` |

Правила скоринга: `config/scoring_rules.yaml`.

---

## REST API

```
GET    /api/v1/health
GET    /api/v1/search-queries
POST   /api/v1/search-queries
PATCH  /api/v1/search-queries/{id}
DELETE /api/v1/search-queries/{id}
POST   /api/v1/search-runs              # все активные запросы
POST   /api/v1/search-runs/{query_id}   # один запрос
GET    /api/v1/search-runs
GET    /api/v1/search-runs/{run_id}
GET    /api/v1/events
GET    /api/v1/events/{event_id}
POST   /api/v1/events/{event_id}/enrich
PATCH  /api/v1/events/{event_id}/review
```

Пример — запуск поиска:

```powershell
curl -X POST http://localhost:8001/api/v1/search-runs
```

---

## Локальная разработка (без Docker)

Требуется Python 3.12+ и отдельный PostgreSQL.

```powershell
cd 2
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Тесты:

```powershell
pytest
```

---

## Структура проекта

```
app/
  core/              конфиг, логирование
  domain/            сущности, дедупликация, детекторы (Минск, каталог)
  application/       use cases, enrichment pipeline
  infrastructure/    БД, SearXNG/SerpAPI, парсеры страниц
  presentation/      REST API и веб-интерфейс
config/
  scoring_rules.yaml правила скоринга
  searxng/           настройки SearXNG
```

---

## Частые проблемы

| Симптом | Что проверить |
|---------|---------------|
| 0 результатов поиска | SearXNG: `docker compose ps`, открыть http://localhost:8080. Движки Google/Bing иногда отдают CAPTCHA |
| Мало карточек в shortlist | На вкладке «Мероприятия» больше записей — shortlist только score ≥ 50, Минск, не rejected |
| В выдаче каталоги | Часть отсекается при поиске; остальные помечаются rejected при обогащении, ссылки с каталога добавляются как новые кандидаты |
| Обогащение failed | Битая ссылка, PDF, таймаут. Кнопка «Обогатить ожидающие» или `POST .../enrich` по карточке |

---

## Production

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

Перед выкладкой: смените `secret_key` в `config/searxng/settings.yml`, задайте внешний `DATABASE_URL`.
