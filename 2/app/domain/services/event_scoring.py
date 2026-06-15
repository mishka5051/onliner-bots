from dataclasses import dataclass
from typing import Any

from app.core.scoring_config import ScoringRules, get_scoring_rules
from app.domain.entities import EventCandidateEntity


@dataclass(frozen=True)
class ScoreResult:
    relevance_score: int
    score_breakdown: dict[str, Any]
    onliner_fit_score: int


class EventScoringService:
    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def score(self, event: EventCandidateEntity) -> ScoreResult:
        breakdown: dict[str, Any] = {}
        total = 0
        weights = self._rules.weights

        if event.is_minsk:
            points = weights.get("minsk", 0)
            breakdown["minsk"] = points
            total += points

        if event.estimated_attendance is not None:
            if event.estimated_attendance >= 3000:
                points = weights.get("large_event_3000_plus", 0)
                breakdown["large_event_3000_plus"] = points
                total += points
            elif event.estimated_attendance >= 1000:
                points = weights.get("large_event_1000_plus", 0)
                breakdown["large_event_1000_plus"] = points
                total += points

        if event.is_recurring:
            points = weights.get("recurring", 0)
            breakdown["recurring"] = points
            total += points

        if event.is_free:
            points = weights.get("free_entry", 0)
            breakdown["free_entry"] = points
            total += points

        onliner_fit = self._compute_onliner_fit(event)
        if onliner_fit > 0:
            points = min(weights.get("onliner_theme", 0), onliner_fit)
            breakdown["onliner_theme"] = points
            total += points

        if event.partner_participation_possible:
            points = weights.get("partner_slot", 0)
            breakdown["partner_slot"] = points
            total += points

        if event.is_enough_lead_time:
            points = weights.get("enough_lead_time", 0)
            breakdown["enough_lead_time"] = points
            total += points

        if (event.trend_score or 0) > 0:
            points = weights.get("trend_bonus", 0)
            breakdown["trend_bonus"] = points
            total += points

        if event.is_free is False:
            breakdown["paid_penalty"] = -10
            total -= 10

        if event.is_minsk is False:
            breakdown["not_minsk_penalty"] = -15
            total -= 15

        if event.is_enough_lead_time is False:
            breakdown["short_lead_time_penalty"] = -20
            total -= 20

        total = max(0, min(100, total))
        return ScoreResult(
            relevance_score=total,
            score_breakdown=breakdown,
            onliner_fit_score=onliner_fit,
        )

    def _compute_onliner_fit(self, event: EventCandidateEntity) -> int:
        if event.theme_tags:
            return min(100, 15 * len(event.theme_tags))

        combined = " ".join(
            filter(
                None,
                [event.title, event.description, event.page_text, event.category],
            )
        ).lower()
        matched_themes: list[str] = []
        for theme, keywords in self._rules.onliner_theme_keywords.items():
            if any(keyword.lower() in combined for keyword in keywords):
                matched_themes.append(theme)
        if not matched_themes:
            return 0
        return min(100, 20 + 10 * (len(matched_themes) - 1))
