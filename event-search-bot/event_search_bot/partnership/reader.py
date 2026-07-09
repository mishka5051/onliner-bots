from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from event_search_bot.config import get_settings
from event_search_bot.partnership.models import ApprovedPartnershipEvent, PartnershipLead


class PartnershipLeadStore:
    """Работает с общей SQLite базой partnership-bot для чтения и модерации."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def is_available(self) -> bool:
        return self._path.is_file()

    def ensure_schema(self) -> None:
        if not self.is_available():
            return
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approved_events (
                    lead_id TEXT PRIMARY KEY,
                    event_title TEXT NOT NULL,
                    city TEXT,
                    event_date TEXT,
                    event_url TEXT,
                    approved_at TEXT NOT NULL,
                    FOREIGN KEY(lead_id) REFERENCES partnership_leads(id)
                )
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

    def count_leads(self, status: str | None = None) -> int:
        if not self.is_available():
            return 0
        self.ensure_schema()
        with self._connect() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM partnership_leads WHERE status = ?",
                    (status,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS count FROM partnership_leads").fetchone()
        return int(row["count"]) if row else 0

    def count_approved_events(self) -> int:
        if not self.is_available():
            return 0
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM approved_events").fetchone()
        return int(row["count"]) if row else 0

    def list_leads(self, *, status: str = "new", limit: int = 5, offset: int = 0) -> list[PartnershipLead]:
        if not self.is_available():
            return []
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM partnership_leads
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset),
            ).fetchall()
        return [self._row_to_lead(row) for row in rows]

    def list_recent_leads(self, limit: int = 30) -> list[PartnershipLead]:
        if not self.is_available():
            return []
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM partnership_leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_lead(row) for row in rows]

    def list_approved_events(self, *, limit: int = 5, offset: int = 0) -> list[ApprovedPartnershipEvent]:
        if not self.is_available():
            return []
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approved_events
                ORDER BY approved_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def get_lead_by_short_id(self, short_id: str) -> PartnershipLead | None:
        if not self.is_available():
            return None
        self.ensure_schema()
        prefix = short_id.replace("-", "")[:8]
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM partnership_leads ORDER BY created_at DESC LIMIT 300").fetchall()
        for row in rows:
            lead = self._row_to_lead(row)
            if lead.short_id == prefix:
                return lead
        return None

    def get_approved_event_by_short_id(self, short_id: str) -> ApprovedPartnershipEvent | None:
        if not self.is_available():
            return None
        self.ensure_schema()
        prefix = short_id.replace("-", "")[:8]
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM approved_events ORDER BY approved_at DESC LIMIT 300").fetchall()
        for row in rows:
            event = self._row_to_event(row)
            if event.short_id == prefix:
                return event
        return None

    def approve_lead(self, short_id: str) -> PartnershipLead | None:
        lead = self.get_lead_by_short_id(short_id)
        if lead is None:
            return None
        approved_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE partnership_leads
                SET status = 'approved', approved_at = ?, deleted_at = NULL
                WHERE id = ?
                """,
                (approved_at, lead.id),
            )
            conn.execute(
                """
                INSERT INTO approved_events (lead_id, event_title, city, event_date, event_url, approved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(lead_id) DO UPDATE SET
                    event_title = excluded.event_title,
                    city = excluded.city,
                    event_date = excluded.event_date,
                    event_url = excluded.event_url,
                    approved_at = excluded.approved_at
                """,
                (
                    lead.id,
                    lead.event_title,
                    lead.city,
                    lead.event_date.isoformat() if lead.event_date else None,
                    lead.event_url,
                    approved_at,
                ),
            )
            conn.commit()
        return self.get_lead_by_short_id(short_id)

    def delete_lead(self, short_id: str) -> PartnershipLead | None:
        lead = self.get_lead_by_short_id(short_id)
        if lead is None:
            return None
        deleted_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE partnership_leads
                SET status = 'deleted', deleted_at = ?
                WHERE id = ?
                """,
                (deleted_at, lead.id),
            )
            conn.execute("DELETE FROM approved_events WHERE lead_id = ?", (lead.id,))
            conn.commit()
        return self.get_lead_by_short_id(short_id)

    @staticmethod
    def _row_to_lead(row: sqlite3.Row) -> PartnershipLead:
        event_date = datetime.fromisoformat(row["event_date"]) if row["event_date"] else None
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

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> ApprovedPartnershipEvent:
        event_date = datetime.fromisoformat(row["event_date"]) if row["event_date"] else None
        return ApprovedPartnershipEvent(
            lead_id=row["lead_id"],
            event_title=row["event_title"],
            approved_at=datetime.fromisoformat(row["approved_at"]),
            city=row["city"],
            event_date=event_date,
            event_url=row["event_url"],
        )


@lru_cache
def get_lead_reader() -> PartnershipLeadStore:
    settings = get_settings()
    db_path = Path(settings.partnership_data_dir) / "partnership.sqlite3"
    return PartnershipLeadStore(db_path)
