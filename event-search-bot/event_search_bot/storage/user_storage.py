from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class HistoryEntry:
    id: int
    user_id: int
    query: str
    mode: str
    created_at: datetime
    job_id: str | None = None
    summary_text: str | None = None


class UserStorage:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from event_search_bot.config import get_settings

            path = Path(get_settings().bot_data_dir) / "bot.sqlite3"
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
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    job_id TEXT,
                    summary_text TEXT
                );
                CREATE TABLE IF NOT EXISTS bot_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._migrate(conn)
            conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(search_history)")}
        if "job_id" not in columns:
            conn.execute("ALTER TABLE search_history ADD COLUMN job_id TEXT")
        if "summary_text" not in columns:
            conn.execute("ALTER TABLE search_history ADD COLUMN summary_text TEXT")

    def add_search(self, user_id: int, query: str, mode: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO search_history (user_id, query, mode, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, query.strip(), mode, now),
            )
            entry_id = int(cursor.lastrowid)
            conn.execute(
                """
                DELETE FROM search_history
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM search_history WHERE user_id = ? ORDER BY id DESC LIMIT 10
                )
                """,
                (user_id, user_id),
            )
            conn.commit()
        return entry_id

    def update_history_result(
        self,
        entry_id: int,
        *,
        job_id: str | None = None,
        summary_text: str | None = None,
    ) -> None:
        with self._connect() as conn:
            if job_id is not None:
                conn.execute(
                    "UPDATE search_history SET job_id = ? WHERE id = ?",
                    (job_id, entry_id),
                )
            if summary_text is not None:
                conn.execute(
                    "UPDATE search_history SET summary_text = ? WHERE id = ?",
                    (summary_text[:8000], entry_id),
                )
            conn.commit()

    def clear_history(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
            conn.commit()

    def get_search(self, user_id: int, entry_id: int) -> HistoryEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, query, mode, created_at, job_id, summary_text
                FROM search_history WHERE user_id = ? AND id = ?
                """,
                (user_id, entry_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_history(self, user_id: int, limit: int = 10) -> list[HistoryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, query, mode, created_at, job_id, summary_text
                FROM search_history WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            user_id=row["user_id"],
            query=row["query"],
            mode=row["mode"],
            created_at=datetime.fromisoformat(row["created_at"]),
            job_id=row["job_id"],
            summary_text=row["summary_text"],
        )

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM bot_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bot_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def add_lead_watcher(self, user_id: int) -> None:
        raw = self.get_meta("lead_watchers")
        watchers: list[int] = []
        if raw:
            try:
                watchers = [int(value) for value in json.loads(raw)]
            except Exception:
                watchers = []
        if user_id not in watchers:
            watchers.append(user_id)
            self.set_meta("lead_watchers", json.dumps(watchers))

    def list_lead_watchers(self) -> list[int]:
        raw = self.get_meta("lead_watchers")
        if not raw:
            return []
        try:
            return [int(value) for value in json.loads(raw)]
        except Exception:
            return []


user_storage = UserStorage()
