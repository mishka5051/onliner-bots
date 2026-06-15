from enum import StrEnum


class SearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RelevanceStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(StrEnum):
    CONFERENCE = "conference"
    FESTIVAL = "festival"
    EXHIBITION = "exhibition"
    MEETUP = "meetup"
    CONCERT = "concert"
    URBAN = "urban"
    OTHER = "other"
