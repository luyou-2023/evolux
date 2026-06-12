"""SQLite session store for orchestrator main sessions."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from evolux_constants import get_evolux_home

SCHEMA_VERSION = 1


class SessionDB:
    """Minimal persistent session storage for Phase 1."""

    def __init__(self, home: Path | None = None):
        self.home = home or get_evolux_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.db_path = self.home / "state.db"
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                session_key TEXT UNIQUE NOT NULL,
                assistant_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                parent_session_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            """
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

    def create_session(
        self,
        session_key: str,
        assistant_id: str,
        platform: str,
        parent_session_id: str | None = None,
    ) -> str:
        session_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO sessions(session_id, session_key, assistant_id, platform, parent_session_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, session_key, assistant_id, platform, parent_session_id),
        )
        self._conn.commit()
        return session_id

    def get_session_id_by_key(self, session_key: str) -> str | None:
        row = self._conn.execute(
            "SELECT session_id FROM sessions WHERE session_key = ?",
            (session_key,),
        ).fetchone()
        return row["session_id"] if row else None

    def get_or_create_session(
        self,
        session_key: str,
        assistant_id: str,
        platform: str,
    ) -> str:
        existing = self.get_session_id_by_key(session_key)
        if existing:
            return existing
        return self.create_session(session_key, assistant_id, platform)

    def append_message(self, session_id: str, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        self._conn.commit()

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
