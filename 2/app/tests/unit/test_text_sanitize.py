from app.infrastructure.enrichment.text_sanitize import sanitize_page_text


def test_sanitize_page_text_removes_null_bytes():
    raw = "Минск\x00конференция"
    assert "\x00" not in sanitize_page_text(raw)
    assert "Минск" in sanitize_page_text(raw)
