from urllib.parse import urlparse

from app.application.ports.search_provider import SearchResult


class FakeSearchProvider:
    _CATALOG: list[SearchResult] = [
        SearchResult(
            title="Белорусская IT-конференция 2026",
            snippet="Крупнейшая IT-конференция в Минске. Ищем инфопартнёров.",
            link="https://example.by/events/it-conf-2026?utm_source=google",
            source_domain="example.by",
        ),
        SearchResult(
            title="Бизнес-форум Беларуси",
            snippet="Ежегодный бизнес-форум для предпринимателей.",
            link="https://bizforum.by/2026",
            source_domain="bizforum.by",
        ),
        SearchResult(
            title="Образовательный форум Минск",
            snippet="Форум для педагогов и EdTech-компаний.",
            link="https://eduforum.by/minsk",
            source_domain="eduforum.by",
        ),
        SearchResult(
            title="Выставка инноваций Беларусь 2026",
            snippet="Международная выставка технологий и стартапов.",
            link="https://innovations.by/expo-2026",
            source_domain="innovations.by",
        ),
        SearchResult(
            title="Фестиваль городских инициатив",
            snippet="Городской фестиваль с партнёрскими программами.",
            link="https://cityfest.by/partners",
            source_domain="cityfest.by",
        ),
    ]

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        query_lower = query.lower()
        matched = [
            result
            for result in self._CATALOG
            if any(token in result.title.lower() or token in (result.snippet or "").lower()
                   for token in query_lower.split() if len(token) > 2)
        ]
        if not matched:
            matched = self._CATALOG[:2]

        results: list[SearchResult] = []
        for index, result in enumerate(matched[:limit]):
            parsed = urlparse(result.link)
            domain = parsed.netloc.lower().removeprefix("www.")
            results.append(
                SearchResult(
                    title=f"{result.title} [{query[:30]}]",
                    snippet=result.snippet,
                    link=result.link,
                    source_domain=domain,
                )
            )
            if index == 0 and "?" not in result.link:
                results.append(
                    SearchResult(
                        title=result.title,
                        snippet=result.snippet,
                        link=f"{result.link}?utm_source=test",
                        source_domain=domain,
                    )
                )
        return results[:limit]
