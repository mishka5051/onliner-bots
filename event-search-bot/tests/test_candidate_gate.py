import pytest

from event_search_bot.pipeline.candidate_gate import (
    MIN_QUERY_RELEVANCE,
    extract_query_tokens,
    is_actionable_event_candidate,
    is_catalog_provenance_snippet,
    query_relevance_score,
)


def test_extract_query_tokens_includes_short_it():
    assert extract_query_tokens("Конференция it") == ["it"]


def test_extract_query_tokens_treats_generic_event_words_as_stopwords():
    assert extract_query_tokens("Выставка Минск 2026") == []


def test_rejects_navigation_and_catalog_urls():
    assert not is_actionable_event_candidate(
        user_query="Конференция it",
        title="Выставки по тематикам",
        url="https://expomap.ru/expo/theme",
    )
    assert not is_actionable_event_candidate(
        user_query="Конференция it",
        title="Для конференций",
        url="https://all-events.ru/ploshadki-dlya-konferenciji",
    )


def test_accepts_it_conference_card():
    assert is_actionable_event_candidate(
        user_query="Конференция it",
        title="IT Space 2026 Минск",
        url="https://digital-calendar.ru/it_space_2026_minsk/",
    )


def test_catalog_snippet_detection():
    assert is_catalog_provenance_snippet("Каталог Expomap IT Минск (tier A)")
    assert not is_catalog_provenance_snippet("Форум для разработчиков")


def test_accepts_known_it_event_by_name_hint():
    assert is_actionable_event_candidate(
        user_query="Конференция it",
        title="ProductCamp Belarus 2026",
        url="https://example.by/productcamp-2026/",
    )


def test_accepts_catalog_event_without_literal_query_word():
    assert is_actionable_event_candidate(
        user_query="Выставка Минск 2026",
        title="Национальная безопасность Беларусь 2026",
        url="https://expomap.ru/expo/security-belarus-2026/",
        tier="A",
        source="catalog",
    )


def test_query_relevance_accepts_synonym_rich_page():
    score = query_relevance_score(
        "Конференция it",
        title="Форум разработчиков",
        url="https://example.by/dev-forum",
        page_text="digital software conference for developers in Minsk",
    )
    assert score >= MIN_QUERY_RELEVANCE
