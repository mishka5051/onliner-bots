import pytest

from app.domain.services.catalog_page_detector import CatalogPageDetector
from app.domain.services.minsk_detector import MinskDetector
from app.infrastructure.enrichment.catalog_link_extractor import CatalogLinkExtractor


@pytest.fixture
def detector() -> CatalogPageDetector:
    return CatalogPageDetector()


def test_detects_catalog_in_title(detector: CatalogPageDetector) -> None:
    assert detector.is_catalog_search_result(
        url="https://example.com/page",
        title="Каталог инфопартнеров - Москва",
    )


def test_detects_moscow_in_title(detector: CatalogPageDetector) -> None:
    assert detector.is_foreign_city_in_title("Форум-выставка «ОТДЫХ» - Москва")


def test_minsk_detector_rejects_moscow_catalog_title() -> None:
    detector = MinskDetector()
    assert not detector.is_minsk(
        city="Минск",
        country="Беларусь",
        text="Минск Минск Минск расписание выставок",
        title="Каталог инфопартнеров - Москва",
        is_catalog=True,
    )


def test_minsk_detector_accepts_minsk_event() -> None:
    detector = MinskDetector()
    assert detector.is_minsk(
        city="Минск",
        country="Беларусь",
        text="IT конференция в Минске",
        title="IT Space 2026 Минск",
        is_catalog=False,
    )


def test_catalog_link_extractor_finds_event_links() -> None:
    html = """
    <html><body>
      <a href="/events/it-conf-2026-minsk-details">IT Conference 2026 in Minsk</a>
      <a href="/calendar/2026">Calendar</a>
    </body></html>
    """
    links = CatalogLinkExtractor().extract(html, "https://events.example.by/catalog")
    assert len(links) == 1
    assert "it-conf" in links[0].url
