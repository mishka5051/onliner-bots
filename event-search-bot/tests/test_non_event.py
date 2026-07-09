from event_search_bot.pipeline.non_event import is_non_event_page, looks_like_real_event


def test_rejects_coworking_and_wedding() -> None:
    assert is_non_event_page("Коворкинг в Минске: арендовать помещение")
    assert is_non_event_page("Renaissance Minsk - ресторан для свадьбы, Минск")
    assert is_non_event_page("Организация мероприятий в Минске под ключ")


def test_keeps_conference() -> None:
    assert not is_non_event_page("IT конференция Минск 2026")
    assert looks_like_real_event(event_type="conference", event_date=None)
    assert looks_like_real_event(event_type="other", event_date="2026-05-20")
