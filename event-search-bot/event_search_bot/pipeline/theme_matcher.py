from __future__ import annotations

import re

from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules


class ThemeMatcherService:
    """Keyword-based theme matching (same rules as the main service)."""

    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def match_themes(self, text: str) -> list[tuple[str, float]]:
        hits = self._keyword_themes(text)
        return [(theme, 1.0) for theme in hits]

    def compute_fit_score(self, text: str) -> tuple[int, list[str]]:
        matches = self.match_themes(text)
        if not matches:
            return 0, []

        themes = [theme for theme, _ in matches]
        base = min(100, 20 + 10 * (len(themes) - 1))
        return base, themes

    def _keyword_themes(self, text: str) -> list[str]:
        lowered = text.lower()
        hits: list[str] = []
        for theme, keywords in self._rules.onliner_theme_keywords.items():
            for keyword in keywords:
                kw = keyword.lower()
                if kw == "it":
                    if re.search(r"\b(it|ит)\b", lowered[:4000]) and re.search(
                        r"(конференц|conference|tech|digital|разработ|devops|software|программ)",
                        lowered[:4000],
                        re.IGNORECASE,
                    ):
                        hits.append(theme)
                        break
                    continue
                if len(kw) < 4:
                    if re.search(rf"\b{re.escape(kw)}\b", lowered):
                        hits.append(theme)
                        break
                elif kw in lowered:
                    hits.append(theme)
                    break
        return hits
