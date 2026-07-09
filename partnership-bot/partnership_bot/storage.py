from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


class BotStorage:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from partnership_bot.config import get_settings

            path = Path(get_settings().bot_data_dir) / "partnership.sqlite3"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bot_sessions (
                    telegram_user_id INTEGER PRIMARY KEY,
                    step TEXT NOT NULL,
                    draft_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS partnership_leads (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'new',
                    source TEXT NOT NULL DEFAULT 'telegram',
                    event_title TEXT NOT NULL,
                    telegram_user_id INTEGER,
                    telegram_username TEXT,
                    contact_name TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    event_date TEXT,
                    city TEXT,
                    event_url TEXT,
                    event_format TEXT,
                    audience_range TEXT,
                    partnership_types_json TEXT,
                    comment TEXT,
                    auto_score INTEGER,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS approved_events (
                    lead_id TEXT PRIMARY KEY,
                    event_title TEXT NOT NULL,
                    city TEXT,
                    event_date TEXT,
                    event_url TEXT,
                    approved_at TEXT NOT NULL,
                    FOREIGN KEY(lead_id) REFERENCES partnership_leads(id)
                );
                """
            )
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(partnership_leads)").fetchall()
            }
            if "approved_at" not in columns:
                conn.execute("ALTER TABLE partnership_leads ADD COLUMN approved_at TEXT")
            if "deleted_at" not in columns:
                conn.execute("ALTER TABLE partnership_leads ADD COLUMN deleted_at TEXT")
            conn.commit()

    def get_session(self, telegram_user_id: int) -> tuple[str, dict[str, Any]] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT step, draft_json FROM bot_sessions WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
        if row is None:
            return None
        return row["step"], json.loads(row["draft_json"])

    def save_session(self, telegram_user_id: int, *, step: str, draft: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_sessions (telegram_user_id, step, draft_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    step = excluded.step,
                    draft_json = excluded.draft_json,
                    updated_at = excluded.updated_at
                """,
                (telegram_user_id, step, json.dumps(draft, ensure_ascii=False), now),
            )
            conn.commit()

    def clear_session(self, telegram_user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM bot_sessions WHERE telegram_user_id = ?", (telegram_user_id,))
            conn.commit()

    def create_lead(self, draft: dict[str, Any], *, telegram_user_id: int, username: str | None) -> PartnershipLead:
        lead_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        event_date: datetime | None = None
        if draft.get("event_date"):
            event_date = datetime.fromisoformat(draft["event_date"])

        lead = PartnershipLead(
            id=lead_id,
            status="new",
            source="telegram",
            event_title=draft["event_title"],
            created_at=now,
            telegram_user_id=telegram_user_id,
            telegram_username=username or draft.get("telegram_username"),
            contact_name=draft.get("contact_name"),
            contact_email=draft.get("contact_email"),
            contact_phone=draft.get("contact_phone") or draft.get("contact"),
            event_date=event_date,
            city=draft.get("city"),
            event_url=draft.get("event_url"),
            event_format=draft.get("event_format"),
            audience_range=draft.get("audience_range"),
            partnership_types=list(draft.get("partnership_types") or []),
            comment=draft.get("comment"),
            auto_score=None,
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO partnership_leads (
                    id, status, source, event_title, telegram_user_id, telegram_username,
                    contact_name, contact_email, contact_phone, event_date, city, event_url,
                    event_format, audience_range, partnership_types_json, comment, auto_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead.id,
                    lead.status,
                    lead.source,
                    lead.event_title,
                    lead.telegram_user_id,
                    lead.telegram_username,
                    lead.contact_name,
                    lead.contact_email,
                    lead.contact_phone,
                    lead.event_date.isoformat() if lead.event_date else None,
                    lead.city,
                    lead.event_url,
                    lead.event_format,
                    lead.audience_range,
                    json.dumps(lead.partnership_types, ensure_ascii=False),
                    lead.comment,
                    lead.auto_score,
                    lead.created_at.isoformat(),
                ),
            )
            conn.commit()
        return lead

    def list_leads(self, limit: int = 50) -> list[PartnershipLead]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM partnership_leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_lead(row) for row in rows]

    def get_lead(self, lead_id: str) -> PartnershipLead | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM partnership_leads WHERE id = ?", (lead_id,)).fetchone()
        return self._row_to_lead(row) if row else None

    @staticmethod
    def _row_to_lead(row: sqlite3.Row) -> PartnershipLead:
        event_date = None
        if row["event_date"]:
            event_date = datetime.fromisoformat(row["event_date"])
        types = json.loads(row["partnership_types_json"] or "[]")
        return PartnershipLead(
            id=row["id"],
            status=row["status"],
            source=row["source"],
            event_title=row["event_title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            telegram_user_id=row["telegram_user_id"],
            telegram_username=row["telegram_username"],
            contact_name=row["contact_name"],
            contact_email=row["contact_email"],
            contact_phone=row["contact_phone"],
            event_date=event_date,
            city=row["city"],
            event_url=row["event_url"],
            event_format=row["event_format"],
            audience_range=row["audience_range"],
            partnership_types=types,
            comment=row["comment"],
            auto_score=row["auto_score"],
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        )


storage = BotStorage()
