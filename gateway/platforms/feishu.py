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
    event_type = header.get("event_type")
    if event_type == "card.action.trigger":
        return _parse_card_action_trigger(payload, event, assistant_id=assistant_id)
    if event_type != "im.message.receive_v1":
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


def build_card_action_ack(content: str = "已收到您的选择", *, toast_type: str = "success") -> dict[str, Any]:
    """Feishu card.action.trigger webhook response body."""
    return {"toast": {"type": toast_type, "content": content}}


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


def _parse_card_action_trigger(
    payload: dict[str, Any],
    event: dict[str, Any],
    *,
    assistant_id: str,
) -> MessageEvent:
    action = event.get("action") or {}
    value = action.get("value") or {}
    if not isinstance(value, dict):
        value = {"option": str(value)}

    option = str(value.get("option") or "").strip()
    question = str(value.get("question") or "").strip()
    if question and option:
        text = f"[确认] {question} → {option}"
    elif option:
        text = f"我选择：{option}"
    else:
        text = str(value)

    operator = event.get("operator") or {}
    context = event.get("context") or {}
    operator_id = operator.get("operator_id") if isinstance(operator.get("operator_id"), dict) else {}
    open_id = str(
        operator.get("open_id")
        or operator_id.get("open_id")
        or operator.get("user_id")
        or operator_id.get("user_id")
        or ""
    )

    source = SessionSource(
        platform="feishu",
        chat_type=_normalize_chat_type(context.get("chat_type") or "p2p"),
        chat_id=str(context.get("open_chat_id") or ""),
        user_id=open_id,
        user_id_alt=str(operator.get("union_id") or operator_id.get("union_id") or "") or None,
        thread_id=str(context.get("open_message_id") or "") or None,
    )
    return MessageEvent(
        assistant_id=assistant_id,
        source=source,
        text=text,
        message_id=str(context.get("open_message_id") or "") or None,
        is_card_action=True,
        card_action_option=option or None,
        raw=payload,
    )


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
