import re

from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules

OTHER_CITY_PATTERN = re.compile(
    r"\b(москва|moscow|санкт-петербург|spb|петербург|казань|новосибирск|екатеринбург|"
    r"киев|kyiv|варшава|warsaw|вильнюс|vilnius|феодосия|feodosia|крым|crimea|"
    r"севастополь|сочи|краснодар|ростов|самара|воронеж|краков|krakow)\b",
    re.IGNORECASE,
)


class MinskDetector:
    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def evaluate(
        self,
        *,
        city: str | None,
        country: str | None,
        text: str | None,
        title: str | None = None,
        is_catalog: bool = False,
    ) -> str:
        if is_catalog:
            return "unlikely"

        title_text = (title or "").lower()
        if OTHER_CITY_PATTERN.search(title_text):
            if "минск" not in title_text and "minsk" not in title_text:
                return "unlikely"

        scope_text = self._scope_text(
            title=title,
            city=city,
            country=country,
            text=text,
            is_catalog=is_catalog,
        )
        combined = scope_text.lower()

        has_minsk = any(
            keyword in combined for keyword in self._rules.minsk_keywords if keyword in {"минск", "minsk"}
        )
        has_belarus = any(keyword in combined for keyword in ("беларус", "belarus", "белорус"))
        has_belarus_city = any(keyword in combined for keyword in self._rules.belarus_city_keywords)
        has_foreign = any(keyword in combined for keyword in self._rules.foreign_city_keywords)

        if city:
            city_lower = city.lower().strip()
            if "минск" in city_lower or "minsk" in city_lower:
                return "confirmed"
            if any(keyword in city_lower for keyword in self._rules.belarus_city_keywords):
                return "likely"
            if self._city_is_foreign(city_lower):
                return "unlikely"
            if not self._city_is_belarus(city_lower):
                return "uncertain"

        if country:
            country_lower = country.lower()
            if country_lower in {"by", "blr", "belarus", "беларусь", "беларус"}:
                if has_minsk:
                    return "confirmed"
                if city and self._city_is_belarus(city.lower()):
                    return "likely"
                if not city:
                    return "likely"
                return "uncertain"
            if country_lower in {"ru", "rus", "russia", "россия", "рф", "ua", "ukraine", "украина"}:
                return "unlikely"

        if has_foreign and not has_minsk and not has_belarus_city:
            return "unlikely"

        if has_minsk:
            return "confirmed"

        if has_belarus_city:
            return "likely"

        if has_belarus and not has_foreign:
            return "uncertain"

        return "uncertain"

    def _city_is_foreign(self, city_lower: str) -> bool:
        if OTHER_CITY_PATTERN.search(city_lower):
            return True
        return any(keyword in city_lower for keyword in self._rules.foreign_city_keywords)

    def _city_is_belarus(self, city_lower: str) -> bool:
        if "минск" in city_lower or "minsk" in city_lower:
            return True
        return any(keyword in city_lower for keyword in self._rules.belarus_city_keywords)

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
