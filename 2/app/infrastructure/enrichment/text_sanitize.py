def sanitize_page_text(text: str, *, max_length: int = 20000) -> str:
    """Remove bytes PostgreSQL cannot store in UTF-8 text columns."""
    cleaned = text.replace("\x00", "")
    return cleaned.encode("utf-8", errors="ignore").decode("utf-8")[:max_length]
