from event_search_bot.search.filter import rank_results
from event_search_bot.search.models import SearchResult


def test_rank_prefers_event_and_minsk():
    results = [
        SearchResult(
            title="Random blog post",
            snippet="About cooking",
            link="https://example.com/blog/cooking",
            source_domain="example.com",
        ),
        SearchResult(
            title="IT конференция в Минске 2026",
            snippet="Форум для разработчиков, инфопартнёрство",
            link="https://events.example.by/it-conf",
            source_domain="events.example.by",
        ),
    ]
    ranked = rank_results(results, limit=5)
    assert ranked[0].title.startswith("IT конференция")


def test_rank_blocks_social():
    results = [
        SearchResult(
            title="Event page",
            snippet="конференция минск",
            link="https://facebook.com/event/1",
            source_domain="facebook.com",
        ),
    ]
    ranked = rank_results(results, limit=5)
    assert ranked == []
