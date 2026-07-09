from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

import yaml


@dataclass(frozen=True)
class ScoringRules:
    min_lead_time_weeks: int = 4
    ideal_lead_time_weeks: int = 8
    weights: dict[str, int] = field(default_factory=dict)
    shortlist_min_score: int = 50
    shortlist_max_age_days: int = 30
    auto_reject_below: int = 20
    supplementary_borderline_min: int = 25
    supplementary_borderline_max: int = 65
    score_labels: dict[str, str] = field(default_factory=dict)
    onliner_theme_keywords: dict[str, list[str]] = field(default_factory=dict)
    onliner_theme_descriptions: dict[str, str] = field(default_factory=dict)
    event_type_keywords: dict[str, list[str]] = field(default_factory=dict)
    minsk_keywords: list[str] = field(default_factory=list)
    belarus_city_keywords: list[str] = field(default_factory=list)
    foreign_city_keywords: list[str] = field(default_factory=list)
    free_keywords: list[str] = field(default_factory=list)
    paid_keywords: list[str] = field(default_factory=list)
    free_false_positive_phrases: list[str] = field(default_factory=list)
    attendance_patterns: list[str] = field(default_factory=list)
    partner_keywords: list[str] = field(default_factory=list)
    enrichment_priority_high: list[str] = field(default_factory=list)
    enrichment_priority_medium: list[str] = field(default_factory=list)
    pre_fetch_blocked_domains: list[str] = field(default_factory=list)
    pre_fetch_blocked_path_markers: list[str] = field(default_factory=list)


def _load_rules_yaml() -> dict:
    raw = resources.files("event_search_bot.pipeline.config").joinpath("scoring_rules.yaml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(raw)


@lru_cache
def get_scoring_rules(path: str | None = None) -> ScoringRules:
    if path:
        from pathlib import Path

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    else:
        data = _load_rules_yaml()

    lead_time = data.get("lead_time", {})
    thresholds = data.get("thresholds", {})
    onliner_themes = data.get("onliner_themes", {})
    priority = data.get("enrichment_priority_keywords", {})

    return ScoringRules(
        min_lead_time_weeks=int(lead_time.get("min_weeks", 4)),
        ideal_lead_time_weeks=int(lead_time.get("ideal_weeks", 8)),
        weights={str(key): int(value) for key, value in data.get("weights", {}).items()},
        shortlist_min_score=int(thresholds.get("shortlist_min_score", 50)),
        shortlist_max_age_days=int(thresholds.get("shortlist_max_age_days", 30)),
        auto_reject_below=int(thresholds.get("auto_reject_below", 20)),
        supplementary_borderline_min=int(thresholds.get("supplementary_borderline_min", 25)),
        supplementary_borderline_max=int(thresholds.get("supplementary_borderline_max", 65)),
        score_labels={str(k): str(v) for k, v in data.get("score_labels", {}).items()},
        onliner_theme_keywords=onliner_themes.get("keywords", {}),
        onliner_theme_descriptions=onliner_themes.get("descriptions", {}),
        event_type_keywords=data.get("event_types", {}),
        minsk_keywords=[item.lower() for item in data.get("minsk_keywords", [])],
        belarus_city_keywords=[item.lower() for item in data.get("belarus_city_keywords", [])],
        foreign_city_keywords=[item.lower() for item in data.get("foreign_city_keywords", [])],
        free_keywords=[item.lower() for item in data.get("free_keywords", [])],
        paid_keywords=[item.lower() for item in data.get("paid_keywords", [])],
        free_false_positive_phrases=[
            item.lower() for item in data.get("free_false_positive_phrases", [])
        ],
        attendance_patterns=list(data.get("attendance_patterns", [])),
        partner_keywords=[item.lower() for item in data.get("partner_keywords", [])],
        enrichment_priority_high=[item.lower() for item in priority.get("high", [])],
        enrichment_priority_medium=[item.lower() for item in priority.get("medium", [])],
        pre_fetch_blocked_domains=[
            item.lower() for item in data.get("pre_fetch_blocked_domains", [])
        ],
        pre_fetch_blocked_path_markers=[
            item.lower() for item in data.get("pre_fetch_blocked_path_markers", [])
        ],
    )
