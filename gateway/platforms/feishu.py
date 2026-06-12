"""Simplified Feishu/Lark webhook adapter for Evolux gateway."""

from __future__ import annotations

import hashlib
import hmac
import json
from base64 import b64encode
from dataclasses import dataclass
from typing import Any

from gateway.events import MessageEvent
from gateway.session import SessionSource


@dataclass
class FeishuConfig:
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    mode: str = "webhook"


def parse_feishu_webhook(payload: dict[str, Any], *, assistant_id: str) -> MessageEvent | dict[str, Any] | None:
    """Parse Feishu webhook payload into MessageEvent or challenge response."""
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    header = payload.get("header") or {}
    event = payload.get("event") or {}
    if header.get("event_type") != "im.message.receive_v1":
        return None

    message = event.get("message") or {}
    sender = event.get("sender") or {}
    sender_id = (sender.get("sender_id") or {}) if isinstance(sender.get("sender_id"), dict) else {}

    text = _extract_text(message.get("content", ""))
    chat_type = _normalize_chat_type(message.get("chat_type"))
    source = SessionSource(
        platform="feishu",
        chat_type=chat_type,
        chat_id=str(message.get("chat_id", "")),
        user_id=str(sender_id.get("open_id") or sender_id.get("user_id") or ""),
        user_id_alt=str(sender_id.get("union_id") or "") or None,
        thread_id=str(message.get("thread_id") or "") or None,
    )
    return MessageEvent(
        assistant_id=assistant_id,
        source=source,
        text=text,
        message_id=str(message.get("message_id") or "") or None,
        raw=payload,
    )


def build_feishu_text_reply(chat_id: str, text: str) -> dict[str, Any]:
    return {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }


def verify_feishu_signature(timestamp: str, nonce: str, body: bytes, secret: str, signature: str) -> bool:
    if not secret:
        return True
    base = f"{timestamp}{nonce}{secret}".encode("utf-8") + body
    digest = b64encode(hashlib.sha256(base).digest()).decode("utf-8")
    return hmac.compare_digest(digest, signature)


def _extract_text(content: Any) -> str:
    if isinstance(content, dict):
        return str(content.get("text", ""))
    if not content:
        return ""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content
        if isinstance(parsed, dict):
            return str(parsed.get("text", content))
        return content
    return str(content)


def _normalize_chat_type(raw: Any) -> str:
    value = str(raw or "p2p").lower()
    if value in {"p2p", "private"}:
        return "dm"
    if value in {"group", "topic_group"}:
        return "group"
    return value
