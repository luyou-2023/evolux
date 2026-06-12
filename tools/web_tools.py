"""Hermes-aligned web_search and web_extract tools."""

from __future__ import annotations

import json
import re
import ssl
import urllib.parse
import urllib.request
from html import unescape

from tools.registry import registry, tool_error


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _fetch(url: str, *, timeout: float = 20.0) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "evolux/0.4 (+https://github.com/luyou-2023/evolux)"},
    )
    https_handler = urllib.request.HTTPSHandler(context=_ssl_context())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), https_handler)
    with opener.open(request, timeout=timeout) as response:
        return response.read()


def web_search(*, query: str, limit: int = 5) -> str:
    query = (query or "").strip()
    if not query:
        return tool_error("query is required")
    limit = max(1, min(int(limit), 10))

    params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
    url = f"https://api.duckduckgo.com/?{params}"
    try:
        payload = json.loads(_fetch(url).decode("utf-8"))
    except Exception as exc:
        return tool_error(f"web search failed: {exc}")

    results = []
    abstract = str(payload.get("AbstractText") or "").strip()
    if abstract:
        results.append(
            {
                "title": payload.get("Heading") or query,
                "url": payload.get("AbstractURL") or "",
                "description": abstract,
            }
        )
    for topic in payload.get("RelatedTopics") or []:
        if len(results) >= limit:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(
                {
                    "title": str(topic.get("Text")).split(" - ", 1)[0],
                    "url": str(topic.get("FirstURL") or ""),
                    "description": str(topic.get("Text")),
                }
            )
    return json.dumps({"success": True, "query": query, "results": results[:limit]}, ensure_ascii=False)


def web_extract(*, urls: list[str] | str, max_chars: int = 8000) -> str:
    if isinstance(urls, str):
        urls = [urls]
    clean_urls = [str(u).strip() for u in urls if str(u).strip()]
    if not clean_urls:
        return tool_error("urls is required")

    extracted = []
    for url in clean_urls[:5]:
        try:
            body = _fetch(url).decode("utf-8", errors="replace")
        except Exception as exc:
            extracted.append({"url": url, "error": str(exc)})
            continue
        text = _strip_html(body)[:max_chars]
        extracted.append({"url": url, "title": _title_from_html(body), "content": text})
    return json.dumps({"success": True, "results": extracted}, ensure_ascii=False)


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<.*?>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text))
    return text.strip()


def _title_from_html(html: str) -> str:
    match = re.search(r"(?is)<title>(.*?)</title>", html)
    return unescape(match.group(1)).strip() if match else ""


def check_web_requirements() -> bool:
    return True


WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": "Search the web using DuckDuckGo (Hermes-compatible subset).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
}

WEB_EXTRACT_SCHEMA = {
    "name": "web_extract",
    "description": "Fetch and extract readable text from web pages.",
    "parameters": {
        "type": "object",
        "properties": {
            "urls": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
            "max_chars": {"type": "integer"},
        },
        "required": ["urls"],
    },
}

registry.register(
    "web_search",
    lambda args, **_: web_search(query=str(args.get("query", "")), limit=int(args.get("limit", 5))),
    WEB_SEARCH_SCHEMA,
    toolset="web",
    check_fn=check_web_requirements,
)
registry.register(
    "web_extract",
    lambda args, **_: web_extract(urls=args.get("urls", []), max_chars=int(args.get("max_chars", 8000))),
    WEB_EXTRACT_SCHEMA,
    toolset="web",
    check_fn=check_web_requirements,
)
