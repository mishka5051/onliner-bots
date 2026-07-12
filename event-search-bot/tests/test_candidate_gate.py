import pytest

from event_search_bot.pipeline.candidate_gate import (
    extract_query_tokens,
    is_actionable_event_candidate,
    is_catalog_provenance_snippet,
    query_relevance_score,
)


def test_extract_query_tokens_includes_short_it():
    assert extract_query_tokens("Конференция it") == ["it"]


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


def test_query_relevance_requires_token_match():
    assert query_relevance_score(
        "Конференция it",
        title="ОСЕННЯЯ ФЛОРА",
        url="https://expomap.ru/expo/osennyaya-flora/2026",
    ) == 0
    assert query_relevance_score(
        "Конференция it",
        title="IT конференция в Минске",
        url="https://example.by/it-conf-2026",
        page_text="digital developers conference",
    ) >= 30
