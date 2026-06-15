from app.domain.services.deduplication import DeduplicationService


def test_normalize_url_removes_utm_and_lowercases_domain():
    service = DeduplicationService()
    url = "HTTPS://WWW.Example.BY/event/path?utm_source=google&utm_medium=cpc&id=1"
    normalized = service.normalize_url(url)
    assert normalized == "https://example.by/event/path?id=1"


def test_duplicate_key_is_stable_for_equivalent_urls():
    service = DeduplicationService()
    url_a = "https://example.by/event?utm_source=a"
    url_b = "https://www.example.by/event?utm_campaign=b"
    assert service.compute_duplicate_key(url_a) == service.compute_duplicate_key(url_b)


def test_duplicate_key_differs_for_different_paths():
    service = DeduplicationService()
    key_a = service.compute_duplicate_key("https://example.by/event-a")
    key_b = service.compute_duplicate_key("https://example.by/event-b")
    assert key_a != key_b
