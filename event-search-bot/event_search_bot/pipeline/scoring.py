from dataclasses import dataclass
from typing import Any

from event_search_bot.pipeline.models import EventRecord
from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules
from event_search_bot.pipeline.theme_matcher import ThemeMatcherService


@dataclass(frozen=True)
class ScoreResult:
    relevance_score: int
    score_breakdown: dict[str, Any]
    onliner_fit_score: int
    score_explanations: dict[str, str]


class EventScoringService:
    def __init__(
        self,
        rules: ScoringRules | None = None,
        *,
        theme_matcher: ThemeMatcherService | None = None,
    ) -> None:
        self._rules = rules or get_scoring_rules()
        self._theme_matcher = theme_matcher or ThemeMatcherService(self._rules)

    def score(self, event: EventRecord) -> ScoreResult:
        breakdown: dict[str, Any] = {}
        explanations: dict[str, str] = {}
        total = 0
        weights = self._rules.weights
        labels = self._rules.score_labels

        minsk_confidence = (event.score_breakdown or {}).get("minsk_confidence", "unknown")

        if event.is_minsk:
            points = weights.get("minsk", 0)
            if minsk_confidence == "likely":
                points = max(10, points // 2)
            breakdown["minsk"] = points
            explanations["minsk"] = self._label(
                "minsk",
                f"+{points}: {'Минск подтверждён' if minsk_confidence == 'confirmed' else 'вероятно Беларусь/Минск'}",
            )
            total += points
        elif minsk_confidence == "uncertain":
            penalty = -8
            breakdown["uncertain_minsk_penalty"] = penalty
            explanations["uncertain_minsk_penalty"] = self._label(
                "uncertain_minsk_penalty",
                f"{penalty}: город не подтверждён, нужна ручная проверка",
            )
            total += penalty

        if event.estimated_attendance is not None:
            if event.estimated_attendance >= 3000:
                points = weights.get("large_event_3000_plus", 0)
                breakdown["large_event_3000_plus"] = points
                explanations["large_event_3000_plus"] = self._label(
                    "large_event_3000_plus",
                    f"+{points}: ожидаемая посещаемость {event.estimated_attendance}+",
                )
                total += points
            elif event.estimated_attendance >= 1000:
                points = weights.get("large_event_1000_plus", 0)
                breakdown["large_event_1000_plus"] = points
                explanations["large_event_1000_plus"] = self._label(
                    "large_event_1000_plus",
                    f"+{points}: посещаемость {event.estimated_attendance}",
                )
                total += points

        if event.is_recurring:
            points = weights.get("recurring", 0)
            breakdown["recurring"] = points
            explanations["recurring"] = self._label("recurring", f"+{points}: повторяющееся событие")
            total += points

        if event.is_free:
            points = weights.get("free_entry", 0)
            breakdown["free_entry"] = points
            explanations["free_entry"] = self._label("free_entry", f"+{points}: бесплатный вход")
            total += points

        onliner_fit, matched_themes = self._compute_onliner_fit(event)
        if onliner_fit >= 25:
            points = min(weights.get("onliner_theme", 0), onliner_fit)
            breakdown["onliner_theme"] = points
            theme_list = ", ".join(matched_themes) if matched_themes else "—"
            explanations["onliner_theme"] = self._label(
                "onliner_theme",
                f"+{points}: тематика Onliner ({theme_list})",
            )
            total += points

        if event.partner_participation_possible:
            points = weights.get("partner_slot", 0)
            breakdown["partner_slot"] = points
            explanations["partner_slot"] = self._label(
                "partner_slot",
                f"+{points}: на странице есть признаки партнёрства",
            )
            total += points

        if event.is_enough_lead_time:
            points = weights.get("enough_lead_time", 0)
            breakdown["enough_lead_time"] = points
            explanations["enough_lead_time"] = self._label(
                "enough_lead_time",
                f"+{points}: до события {event.lead_time_days or '—'} дн.",
            )
            total += points

        if (event.trend_score or 0) > 0:
            points = weights.get("trend_bonus", 0)
            breakdown["trend_bonus"] = points
            explanations["trend_bonus"] = self._label(
                "trend_bonus",
                f"+{points}: доп. упоминания в поиске",
            )
            total += points

        if event.is_free is False:
            breakdown["paid_penalty"] = -10
            explanations["paid_penalty"] = self._label("paid_penalty", "−10: платный вход")
            total -= 10

        if event.is_minsk is False and minsk_confidence == "unlikely":
            breakdown["not_minsk_penalty"] = -15
            explanations["not_minsk_penalty"] = self._label("not_minsk_penalty", "−15: не Минск/Беларусь")
            total -= 15

        if event.is_enough_lead_time is False:
            breakdown["short_lead_time_penalty"] = -20
            explanations["short_lead_time_penalty"] = self._label(
                "short_lead_time_penalty",
                "−20: мало времени до события",
            )
            total -= 20

        if minsk_confidence != "unknown":
            breakdown["minsk_confidence"] = minsk_confidence

        total = max(0, min(100, total))
        return ScoreResult(
            relevance_score=total,
            score_breakdown=breakdown,
            onliner_fit_score=onliner_fit,
            score_explanations=explanations,
        )

    def _compute_onliner_fit(self, event: EventRecord) -> tuple[int, list[str]]:
        if event.theme_tags:
            return min(100, 15 * len(event.theme_tags)), list(event.theme_tags)

        combined = " ".join(
            filter(
                None,
                [event.title, event.description, event.page_text],
            )
        )
        return self._theme_matcher.compute_fit_score(combined)

    def _label(self, key: str, fallback: str) -> str:
        return self._rules.score_labels.get(key, fallback)
