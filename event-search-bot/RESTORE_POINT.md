# Точка отката — до рефакторинга точности поиска

**Дата:** 2026-07-12  
**Git:** откат к коммиту `f5004fe` (сразу перед рефакторингом)

## Состояние до изменений

- Глубокий поиск: SearXNG (80) + 11 доверенных каталогов без жёсткой привязки к запросу
- `event_matches_query`: при пустых токенах пропускает все ссылки из каталогов
- Размножение каталогов: до 18 ссылок × бюджет 150, без фильтра запроса на дочерних URL
- Сниппет `Каталог Expomap …` наследуется дочерними карточками → ложный Минск
- `soft_reject_minsk=True` — сомнительная гео не отсекается
- Порог отчёта: score ≥ 25 (`supplementary_borderline_min`)
- Тема `technology` срабатывает на голое `it` в URL/сниппете

## Восстановление

```powershell
cd D:\Onliner_2
git log --oneline -5
git checkout f5004fe -- event-search-bot/
cd event-search-bot
docker compose up -d --build
```

Или откат всей ветки: `git revert <commit-hash-precision-gate>`
