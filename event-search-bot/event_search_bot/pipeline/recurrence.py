import re


class RecurrenceDetector:
    EDITION_PATTERN = re.compile(
        r"(?i)(?:^|\s)(?:[ivxlcdm]+|\d{1,2})(?:-?(?:й|я|ое|ая|е|th|st|nd|rd))?\s+"
        r"(?:ежегодн|annual|форум|фестивал|conference|summit|выставк)",
    )
    YEAR_PATTERN = re.compile(r"(20\d{2})")

    def detect_edition_label(self, title: str) -> str | None:
        match = re.search(r"(?i)([IVXLCDM]+|\d{1,2})(?:-?(?:й|я|ое|ая|е|th|st|nd|rd))", title)
        return match.group(0).strip() if match else None

    def looks_recurring(self, title: str, page_text: str | None = None) -> bool:
        combined = f"{title}\n{page_text or ''}"
        if self.EDITION_PATTERN.search(combined):
            return True
        recurring_markers = ("ежегодн", "annual", "второй год", "третий год", "уже проходил", "прошл")
        lowered = combined.lower()
        return any(marker in lowered for marker in recurring_markers)
