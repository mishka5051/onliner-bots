from app.infrastructure.enrichment.page_fetcher import HttpPageFetcher


def test_html_to_text_extracts_visible_content():
    fetcher = HttpPageFetcher()
    html = "<html><body><h1>IT Forum Minsk</h1><p>Конференция в Минске</p></body></html>"
    text = fetcher._html_to_text(html)
    assert "IT Forum Minsk" in text
    assert "Минск" in text
