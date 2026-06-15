from app.infrastructure.enrichment.page_parser import EventPageParser


def test_parser_detects_minsk_free_and_attendance():
    parser = EventPageParser()
    text = """
    VII ежегодный IT форум в г. Минск
    Дата: 15.09.2026
    Более 3500 участников
    Вход бесплатный
    Станьте партнёром или спонсором мероприятия
    """
    parsed = parser.parse(title="IT Forum Minsk", page_text=text)
    assert parsed.is_minsk is True
    assert parsed.is_free is True
    assert parsed.estimated_attendance == 3500
    assert parsed.partner_participation_possible is True
    assert parsed.is_recurring is True
