"""Vector store backends — JSON file and SQLite."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Protocol


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


def create_vector_store(home: Path, name: str, *, backend: str = "json") -> VectorStore:
    """Create a vector store under ``home/vector/``."""
    directory = home / "vector"
    directory.mkdir(parents=True, exist_ok=True)
    if backend == "sqlite":
        stem = Path(name).stem
        return SqliteVectorStore(directory / f"{stem}.db")
    return JsonVectorStore(directory / name)


class SqliteVectorStore:
    """SQLite-backed vector store (stdlib only; vectors stored as JSON blobs)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
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
        self._conn.execute(
            """
            INSERT INTO vectors (item_id, vector, metadata) VALUES (?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET vector=excluded.vector, metadata=excluded.metadata
            """,
            (item_id, json.dumps(vector), json.dumps(metadata)),
        )
        self._conn.commit()

    def delete(self, item_id: str) -> None:
        self._conn.execute("DELETE FROM vectors WHERE item_id = ?", (item_id,))
        self._conn.commit()

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        results: list[tuple[str, float, dict[str, Any]]] = []
        for item_id, vector_raw, metadata_raw in self._conn.execute(
            "SELECT item_id, vector, metadata FROM vectors"
        ):
            metadata = json.loads(metadata_raw)
            if metadata_filter and not _match_filter(metadata, metadata_filter):
                continue
            vector = json.loads(vector_raw)
            score = cosine_similarity(query_vector, vector)
            results.append((item_id, score, metadata))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]
