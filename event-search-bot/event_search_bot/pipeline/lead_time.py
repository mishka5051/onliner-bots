from datetime import datetime, timezone

from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules


class LeadTimeValidator:
    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def evaluate(
        self, event_date: datetime | None, *, now: datetime | None = None
    ) -> tuple[int | None, bool | None]:
        if event_date is None:
            return None, None

        reference = now or datetime.now(timezone.utc)
        if event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)

        lead_time_days = (event_date - reference).days
        min_days = self._rules.min_lead_time_weeks * 7
        return lead_time_days, lead_time_days >= min_days
