from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScoringRules:
    min_lead_time_weeks: int = 4
    ideal_lead_time_weeks: int = 8
    weights: dict[str, int] = field(default_factory=dict)
    shortlist_min_score: int = 50
    shortlist_max_age_days: int = 30
    auto_reject_below: int = 20
    onliner_theme_keywords: dict[str, list[str]] = field(default_factory=dict)
    event_type_keywords: dict[str, list[str]] = field(default_factory=dict)
    minsk_keywords: list[str] = field(default_factory=list)
    free_keywords: list[str] = field(default_factory=list)
    paid_keywords: list[str] = field(default_factory=list)
    attendance_patterns: list[str] = field(default_factory=list)
    partner_keywords: list[str] = field(default_factory=list)


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "scoring_rules.yaml"


@lru_cache
def get_scoring_rules(path: str | None = None) -> ScoringRules:
    rules_path = Path(path) if path else _default_rules_path()
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))

    lead_time = data.get("lead_time", {})
    thresholds = data.get("thresholds", {})
    return ScoringRules(
        min_lead_time_weeks=int(lead_time.get("min_weeks", 4)),
        ideal_lead_time_weeks=int(lead_time.get("ideal_weeks", 8)),
        weights={str(key): int(value) for key, value in data.get("weights", {}).items()},
        shortlist_min_score=int(thresholds.get("shortlist_min_score", 50)),
        shortlist_max_age_days=int(thresholds.get("shortlist_max_age_days", 30)),
        auto_reject_below=int(thresholds.get("auto_reject_below", 20)),
        onliner_theme_keywords=data.get("onliner_themes", {}).get("keywords", {}),
        event_type_keywords=data.get("event_types", {}),
        minsk_keywords=[item.lower() for item in data.get("minsk_keywords", [])],
        free_keywords=[item.lower() for item in data.get("free_keywords", [])],
        paid_keywords=[item.lower() for item in data.get("paid_keywords", [])],
        attendance_patterns=list(data.get("attendance_patterns", [])),
        partner_keywords=[item.lower() for item in data.get("partner_keywords", [])],
    )
