from event_search_bot.pipeline.scoring_config import ScoringRules, get_scoring_rules


class EventTypeClassifier:
    def __init__(self, rules: ScoringRules | None = None) -> None:
        self._rules = rules or get_scoring_rules()

    def classify(self, *texts: str | None) -> str:
        combined = " ".join(text.lower() for text in texts if text).strip()
        if not combined:
            return "other"

        for event_type, keywords in self._rules.event_type_keywords.items():
            if any(keyword.lower() in combined for keyword in keywords):
                return event_type
        return "other"
