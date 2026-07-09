from __future__ import annotations

from dataclasses import dataclass

from event_search_bot.pipeline.models import EventRecord
from event_search_bot.pipeline.scoring_config import get_scoring_rules


@dataclass
class ExportFilters:
    minsk_only: bool = False
    min_score_50: bool = False
    partnership_only: bool = False

    def label(self) -> str:
        parts: list[str] = []
        if self.minsk_only:
            parts.append("Минск")
        if self.min_score_50:
            parts.append("score≥50")
        if self.partnership_only:
            parts.append("партнёрство")
        return ", ".join(parts) if parts else "без фильтров"


def apply_export_filters(events: list[EventRecord], filters: ExportFilters) -> list[EventRecord]:
    rules = get_scoring_rules()
    result: list[EventRecord] = []
    for event in events:
        if event.relevance_status != "scored":
            continue
        score = event.relevance_score or 0
        if score < rules.supplementary_borderline_min:
            continue
        if filters.minsk_only and not event.is_minsk:
            continue
        if filters.min_score_50 and score < rules.shortlist_min_score:
            continue
        if filters.partnership_only and not event.partner_participation_possible:
            continue
        result.append(event)
    return sorted(result, key=lambda item: item.relevance_score or 0, reverse=True)


def filter_scored_events(result_events: list[EventRecord]) -> list[EventRecord]:
    rules = get_scoring_rules()
    items = [
        event
        for event in result_events
        if event.relevance_status == "scored"
        and (event.relevance_score or 0) >= rules.supplementary_borderline_min
    ]
    return sorted(items, key=lambda item: item.relevance_score or 0, reverse=True)
