"""Embedding providers for vector search."""

from __future__ import annotations

import hashlib
import json
import math
import os
import ssl
import urllib.error
import urllib.request
from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic offline embedder for tests and local routing."""

    def __init__(self, dimensions: int = 32):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for i in range(self.dimensions):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class OpenAIEmbedder:
    """OpenAI-compatible embeddings API (optional; falls back caller-side)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimensions: int = 32,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.model, "input": text}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urlopen(request, timeout=60.0) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding API error {exc.code}: {detail}") from exc

        data = (body.get("data") or [{}])[0]
        vector = list(data.get("embedding") or [])
        if not vector:
            raise RuntimeError("Embedding API returned empty vector")
        if len(vector) > self.dimensions:
            vector = vector[: self.dimensions]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def create_embedder(*, provider: str = "hash", api_key: str | None = None, base_url: str | None = None) -> Embedder:
    if provider == "openai" and api_key:
        return OpenAIEmbedder(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
    return HashEmbedder()


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _urlopen(request: urllib.request.Request, timeout: float):
    if os.environ.get("EVOLUX_USE_SYSTEM_PROXY", "").lower() in {"1", "true", "yes"}:
        return urllib.request.urlopen(request, timeout=timeout)
    https_handler = urllib.request.HTTPSHandler(context=_ssl_context())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), https_handler)
    return opener.open(request, timeout=timeout)
