from app.infrastructure.enrichment.html_metadata_extractor import (
    extract_event_date_from_html,
    extract_header_text,
)


def test_extract_date_from_numeric_header():
    html = """
    <html><body>
    <h1>Digital Минск 2026</h1>
    <div class="date">01.03.2026 09:40 ВС</div>
    <p>Весной 2026 года в Минске состоится конференция.</p>
    <section>Похожие мероприятия</section>
    <div>04 июня 2026 / Москва</div>
    </body></html>
    """
    result = extract_event_date_from_html(html)
    assert result is not None
    assert result.day == 1
    assert result.month == 3
    assert result.year == 2026


def test_extract_header_text_excludes_similar_events():
    html = "<div>01.03.2026</div><section>Похожие мероприятия</section><div>04.06.2026</div>"
    header = extract_header_text(html)
    assert "01.03.2026" in header
    assert "04.06.2026" not in header


def test_parser_uses_html_for_digital_minsk_style_page():
    from app.infrastructure.enrichment.page_parser import EventPageParser

    html = """
    <html><body>
    <h1>Digital Минск 2026</h1>
    <div>Платные</div>
    <div>01.03.2026 09:40</div>
    <p>Весной 2026 года в Минске состоится конференция.</p>
    </body></html>
    """
    parser = EventPageParser()
    parsed = parser.parse(
        title="Конференция Digital Минск 2026",
        page_text="Весной 2026 года в Минске состоится конференция.",
        html=html,
    )
    assert parsed.event_date is not None
    assert parsed.event_date.day == 1
    assert parsed.event_date.month == 3
    assert parsed.city == "Минск"
