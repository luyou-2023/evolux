"""Simple JSON-backed vector store."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


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
