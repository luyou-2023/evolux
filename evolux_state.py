"""SQLite session store for orchestrator main sessions."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from evolux_constants import get_evolux_home

SCHEMA_VERSION = 2


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
        self._migrate_schema()
        self._conn.commit()

    def _migrate_schema(self) -> None:
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "title" not in columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
        current = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if current and int(current["value"]) < SCHEMA_VERSION:
            self._conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(SCHEMA_VERSION),),
            )

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

    def get_session_row(self, session_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT session_id, session_key, assistant_id, platform, title, created_at "
            "FROM sessions WHERE session_key = ?",
            (session_key,),
        ).fetchone()
        return dict(row) if row else None

    def set_session_title(self, session_key: str, title: str) -> bool:
        row = self.get_session_row(session_key)
        if row is None:
            return False
        self._conn.execute(
            "UPDATE sessions SET title = ? WHERE session_key = ?",
            (title.strip(), session_key),
        )
        self._conn.commit()
        return True

    def get_session_title(self, session_key: str) -> str:
        row = self.get_session_row(session_key)
        if row is None:
            return ""
        return str(row.get("title") or "").strip()

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

    def count_messages(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["c"])

    def get_last_user_message(self, session_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return str(row["content"]) if row else None

    def pop_last_exchange(self, session_id: str) -> bool:
        rows = self._conn.execute(
            "SELECT id, role FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 2",
            (session_id,),
        ).fetchall()
        if not rows:
            return False
        ids_to_delete: list[int] = []
        if rows[0]["role"] == "assistant":
            ids_to_delete.append(int(rows[0]["id"]))
            if len(rows) > 1 and rows[1]["role"] == "user":
                ids_to_delete.append(int(rows[1]["id"]))
        elif rows[0]["role"] == "user":
            ids_to_delete.append(int(rows[0]["id"]))
        if not ids_to_delete:
            return False
        placeholders = ",".join("?" for _ in ids_to_delete)
        self._conn.execute(
            f"DELETE FROM messages WHERE id IN ({placeholders})",
            ids_to_delete,
        )
        self._conn.commit()
        return True

    def reset_session(self, session_key: str, assistant_id: str, platform: str) -> str:
        session_id = self.get_session_id_by_key(session_key)
        if session_id:
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            self._conn.commit()
        return self.create_session(session_key, assistant_id, platform)

    def replace_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        for item in messages:
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
            self._conn.execute(
                "INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
        self._conn.commit()

    def list_sessions(
        self,
        *,
        assistant_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT session_id, session_key, assistant_id, platform, title, created_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s
        """
        params: list[Any] = []
        if assistant_id:
            query += " WHERE assistant_id = ?"
            params.append(assistant_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
