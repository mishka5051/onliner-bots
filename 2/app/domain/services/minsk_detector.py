import re

from app.core.scoring_config import ScoringRules, get_scoring_rules

OTHER_CITY_PATTERN = re.compile(
    r"\b(москва|moscow|санкт-петербург|spb|петербург|казань|новосибирск|екатеринбург)\b",
    re.IGNORECASE,
)


class MinskDetector:
    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def is_minsk(
        self,
        *,
        city: str | None,
        country: str | None,
        text: str | None,
        title: str | None = None,
        is_catalog: bool = False,
    ) -> bool:
        title_text = (title or "").lower()
        if OTHER_CITY_PATTERN.search(title_text):
            if "минск" not in title_text and "minsk" not in title_text:
                return False

        scope_text = self._scope_text(title=title, city=city, country=country, text=text, is_catalog=is_catalog)
        combined = scope_text.lower()
        has_minsk = any(keyword in combined for keyword in self._rules.minsk_keywords)
        if not has_minsk:
            return False

        if is_catalog:
            return False

        if city:
            city_lower = city.lower()
            if "минск" in city_lower or "minsk" in city_lower:
                return True
            if OTHER_CITY_PATTERN.search(city_lower):
                return False

        if title and OTHER_CITY_PATTERN.search(title_text):
            return "минск" in title_text or "minsk" in title_text

        return has_minsk

    def _scope_text(
        self,
        *,
        title: str | None,
        city: str | None,
        country: str | None,
        text: str | None,
        is_catalog: bool,
    ) -> str:
        if is_catalog:
            return " ".join(filter(None, [title, city, country]))
        return " ".join(filter(None, [title, city, country, text]))
