"""Vector store backends — JSON file and SQLite."""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol


def _open_sqlite(path: Path) -> sqlite3.Connection:
    """Shared SQLite connection safe for orchestrator parallel tool threads."""
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class VectorStore(Protocol):
    def upsert(self, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None: ...

    def delete(self, item_id: str) -> None: ...

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class JsonVectorStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def upsert(self, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        data = self._read()
        data[item_id] = {"vector": vector, "metadata": metadata}
        self._write(data)

    def delete(self, item_id: str) -> None:
        data = self._read()
        data.pop(item_id, None)
        self._write(data)

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        results: list[tuple[str, float, dict[str, Any]]] = []
        for item_id, payload in self._read().items():
            metadata = payload.get("metadata", {})
            if metadata_filter and not _match_filter(metadata, metadata_filter):
                continue
            score = cosine_similarity(query_vector, payload["vector"])
            results.append((item_id, score, metadata))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]


def _match_filter(metadata: dict[str, Any], flt: dict[str, Any]) -> bool:
    return all(metadata.get(key) == value for key, value in flt.items())


DEFAULT_VECTOR_BACKEND = "sqlite-vec"
DEFAULT_VECTOR_DIM = 32


def normalize_vector_backend(backend: str) -> str:
    return backend.replace("_", "-")


def resolve_vector_backend(backend: str | None = None) -> str:
    """Resolve configured backend; fall back to stdlib sqlite when sqlite-vec is unavailable."""
    requested = normalize_vector_backend(backend or DEFAULT_VECTOR_BACKEND)
    if requested == "sqlite-vec" and not sqlite_vec_available():
        return "sqlite"
    return requested


def create_vector_store(home: Path, name: str, *, backend: str | None = None) -> VectorStore:
    """Create a vector store under ``home/vector/``."""
    directory = home / "vector"
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(name).stem
    resolved = resolve_vector_backend(backend)
    if resolved == "sqlite-vec":
        return SqliteVecStore(directory / f"{stem}.db")
    if resolved == "sqlite":
        return SqliteVectorStore(directory / f"{stem}.db")
    return JsonVectorStore(directory / name)


class SqliteVectorStore:
    """SQLite-backed vector store (stdlib only; vectors stored as JSON blobs)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = _open_sqlite(self.path)
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    item_id TEXT PRIMARY KEY,
                    vector TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def upsert(self, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO vectors (item_id, vector, metadata) VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET vector=excluded.vector, metadata=excluded.metadata
                """,
                (item_id, json.dumps(vector), json.dumps(metadata)),
            )
            self._conn.commit()

    def delete(self, item_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM vectors WHERE item_id = ?", (item_id,))
            self._conn.commit()

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        with self._lock:
            rows = list(
                self._conn.execute("SELECT item_id, vector, metadata FROM vectors")
            )
        results: list[tuple[str, float, dict[str, Any]]] = []
        for item_id, vector_raw, metadata_raw in rows:
            metadata = json.loads(metadata_raw)
            if metadata_filter and not _match_filter(metadata, metadata_filter):
                continue
            vector = json.loads(vector_raw)
            score = cosine_similarity(query_vector, vector)
            results.append((item_id, score, metadata))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]


def sqlite_vec_available() -> bool:
    try:
        import sqlite_vec  # noqa: F401
    except ImportError:
        return False
    conn = sqlite3.connect(":memory:")
    if not hasattr(conn, "enable_load_extension"):
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("SELECT vec_version()").fetchone()
        return True
    except Exception:
        return False


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    import sqlite_vec

    if not hasattr(conn, "enable_load_extension"):
        raise RuntimeError("Python sqlite3 was built without extension loading support")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


class SqliteVecStore:
    """SQLite + sqlite-vec extension for cosine distance search."""

    def __init__(self, path: Path, dimensions: int = DEFAULT_VECTOR_DIM):
        self.path = path
        self.dimensions = dimensions
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = _open_sqlite(self.path)
        with self._lock:
            _load_sqlite_vec(self._conn)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    item_id TEXT PRIMARY KEY,
                    vector BLOB NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def _fit_vector(self, vector: list[float]) -> list[float]:
        if len(vector) == self.dimensions:
            return vector
        if len(vector) > self.dimensions:
            return vector[: self.dimensions]
        return vector + [0.0] * (self.dimensions - len(vector))

    def upsert(self, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        from sqlite_vec import serialize_float32

        blob = serialize_float32(self._fit_vector(vector))
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO vectors (item_id, vector, metadata) VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET vector=excluded.vector, metadata=excluded.metadata
                """,
                (item_id, blob, json.dumps(metadata)),
            )
            self._conn.commit()

    def delete(self, item_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM vectors WHERE item_id = ?", (item_id,))
            self._conn.commit()

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        from sqlite_vec import serialize_float32

        query_blob = serialize_float32(self._fit_vector(query_vector))
        with self._lock:
            rows = list(
                self._conn.execute(
                    "SELECT item_id, vec_distance_cosine(?, vector) AS dist, metadata FROM vectors",
                    (query_blob,),
                )
            )
        results: list[tuple[str, float, dict[str, Any]]] = []
        for item_id, distance, metadata_raw in rows:
            metadata = json.loads(metadata_raw)
            if metadata_filter and not _match_filter(metadata, metadata_filter):
                continue
            score = 1.0 - float(distance)
            results.append((item_id, score, metadata))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]
