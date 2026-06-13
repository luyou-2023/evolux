"""SQLite session store for orchestrator main sessions."""

from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from evolux_constants import get_evolux_home

SCHEMA_VERSION = 3

_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content, session_id, role)
    VALUES (new.id, new.content, new.session_id, new.role);
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, session_id, role)
    VALUES ('delete', old.id, old.content, old.session_id, old.role);
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, session_id, role)
    VALUES ('delete', old.id, old.content, old.session_id, old.role);
    INSERT INTO messages_fts(rowid, content, session_id, role)
    VALUES (new.id, new.content, new.session_id, new.role);
END;
"""


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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compression_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_session_id TEXT NOT NULL,
                child_session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                messages_before INTEGER NOT NULL DEFAULT 0,
                messages_after INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_compression_child ON compression_log(child_session_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_compression_parent ON compression_log(parent_session_id)"
        )
        current = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if current and int(current["value"]) < SCHEMA_VERSION:
            self._conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(SCHEMA_VERSION),),
            )
        version = int(
            self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()["value"]
        )
        if version >= 3:
            self._ensure_fts()

    def _ensure_fts(self) -> None:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
        ).fetchone()
        if row is None:
            self._conn.executescript(
                """
                CREATE VIRTUAL TABLE messages_fts USING fts5(
                    content,
                    session_id UNINDEXED,
                    role UNINDEXED,
                    content='messages',
                    content_rowid='id'
                );
                """
                + _FTS_TRIGGERS
            )
            self._conn.execute(
                """
                INSERT INTO messages_fts(rowid, content, session_id, role)
                SELECT id, content, session_id, role FROM messages
                """
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
            WHERE session_key NOT LIKE '%::archived::%'
        """
        params: list[Any] = []
        if assistant_id:
            query += " AND assistant_id = ?"
            params.append(assistant_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def find_sessions_by_title(
        self,
        assistant_id: str,
        query: str,
        *,
        platform: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        sql = """
            SELECT session_id, session_key, assistant_id, platform, title, created_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s
            WHERE assistant_id = ? AND title != '' AND title LIKE ?
        """
        params: list[Any] = [assistant_id, pattern]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def list_titled_sessions(
        self,
        assistant_id: str,
        *,
        platform: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT session_id, session_key, assistant_id, platform, title, created_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s
            WHERE assistant_id = ? AND title != ''
        """
        params: list[Any] = [assistant_id]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_session_row_by_id(self, session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT session_id, session_key, assistant_id, platform, title, parent_session_id, created_at "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    def rotate_session_tip(
        self,
        *,
        session_key: str,
        assistant_id: str,
        platform: str,
        parent_session_id: str,
        title: str = "",
    ) -> str:
        archive_key = f"{session_key}::archived::{parent_session_id[:8]}"
        self._conn.execute(
            "UPDATE sessions SET session_key = ? WHERE session_id = ?",
            (archive_key, parent_session_id),
        )
        child_id = self.create_session(
            session_key,
            assistant_id,
            platform,
            parent_session_id=parent_session_id,
        )
        if title:
            self._conn.execute(
                "UPDATE sessions SET title = ? WHERE session_id = ?",
                (title.strip(), child_id),
            )
            self._conn.commit()
        return child_id

    def log_compression(
        self,
        *,
        parent_session_id: str,
        child_session_id: str,
        summary: str,
        messages_before: int,
        messages_after: int,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO compression_log(
                parent_session_id, child_session_id, summary, messages_before, messages_after
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (parent_session_id, child_session_id, summary, messages_before, messages_after),
        )
        self._conn.commit()

    def get_compression_log_for_child(self, child_session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT parent_session_id, child_session_id, summary, messages_before, messages_after, created_at
            FROM compression_log
            WHERE child_session_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (child_session_id,),
        ).fetchone()
        return dict(row) if row else None

    def load_history(self, session_key: str) -> list[dict[str, Any]]:
        session_id = self.get_session_id_by_key(session_key)
        if not session_id:
            return []
        prefix: list[dict[str, Any]] = []
        child_id = session_id
        while True:
            log = self.get_compression_log_for_child(child_id)
            if not log:
                break
            parent_id = str(log["parent_session_id"])
            if child_id != session_id:
                summary = str(log.get("summary") or "").strip()
                if summary:
                    prefix.insert(
                        0,
                        {
                            "role": "system",
                            "content": f"## 历史摘要（压缩链）\n{summary}",
                        },
                    )
            child_id = parent_id
        return prefix + self.get_messages(session_id)

    @staticmethod
    def _build_fts_query(query: str) -> str:
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", query.strip())
        if not tokens:
            return ""
        return " OR ".join(f'"{token}"' for token in tokens[:12])

    def search_messages_fts(
        self,
        query: str,
        *,
        assistant_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []
        if not self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
        ).fetchone():
            return []
        sql = """
            SELECT s.session_id, s.session_key, s.assistant_id, s.platform, s.title,
                   m.role, m.content, m.created_at
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.session_id = m.session_id
            WHERE messages_fts MATCH ?
              AND s.session_key NOT LIKE '%::archived::%'
        """
        params: list[Any] = [fts_query]
        if assistant_id:
            sql += " AND s.assistant_id = ?"
            params.append(assistant_id)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
