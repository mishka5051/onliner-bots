from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PartnershipLead:
    id: str
    status: str
    source: str
    event_title: str
    created_at: datetime
    telegram_user_id: int | None = None
    telegram_username: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    event_date: datetime | None = None
    city: str | None = None
    event_url: str | None = None
    event_format: str | None = None
    audience_range: str | None = None
    partnership_types: list[str] = field(default_factory=list)
    comment: str | None = None
    auto_score: int | None = None
    approved_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def short_id(self) -> str:
        return self.id.replace("-", "")[:8]


@dataclass
class ApprovedPartnershipEvent:
    lead_id: str
    event_title: str
    approved_at: datetime
    city: str | None = None
    event_date: datetime | None = None
    event_url: str | None = None

    @property
    def short_id(self) -> str:
        return self.lead_id.replace("-", "")[:8]
