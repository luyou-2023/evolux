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
    mode: str = "websocket"


def feishu_connection_mode(platform_config: dict[str, Any]) -> str:
    """Return feishu transport mode (websocket default, Hermes-aligned)."""
    mode = str(platform_config.get("mode") or "websocket").lower()
    if mode not in {"websocket", "webhook"}:
        return "websocket"
    return mode


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


def build_card_action_ack(
    content: str = "已收到您的选择",
    *,
    toast_type: str = "success",
    card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Feishu card.action.trigger webhook response body."""
    body: dict[str, Any] = {"toast": {"type": toast_type, "content": content}}
    if card is not None:
        body["card"] = {"type": "raw", "data": card}
    return body


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
        card_action_question=question or None,
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


def parse_feishu_im_receive_sdk(data: Any, *, assistant_id: str) -> MessageEvent | None:
    """Convert lark-oapi P2ImMessageReceiveV1 into MessageEvent."""
    event = getattr(data, "event", None)
    if not event:
        return None
    message = getattr(event, "message", None)
    sender = getattr(event, "sender", None)
    if not message or not sender:
        return None

    sender_id = getattr(sender, "sender_id", None)
    open_id = str(getattr(sender_id, "open_id", "") or "") if sender_id else ""
    user_id = str(getattr(sender_id, "user_id", "") or "") if sender_id else ""
    union_id = str(getattr(sender_id, "union_id", "") or "") if sender_id else ""

    source = SessionSource(
        platform="feishu",
        chat_type=_normalize_chat_type(getattr(message, "chat_type", "p2p")),
        chat_id=str(getattr(message, "chat_id", "") or ""),
        user_id=open_id or user_id,
        user_id_alt=union_id or None,
        thread_id=str(getattr(message, "thread_id", "") or "") or None,
    )
    return MessageEvent(
        assistant_id=assistant_id,
        source=source,
        text=_extract_text(getattr(message, "content", "")),
        message_id=str(getattr(message, "message_id", "") or "") or None,
        raw={"transport": "websocket"},
    )


def parse_feishu_card_action_sdk(data: Any, *, assistant_id: str) -> MessageEvent:
    """Convert lark-oapi P2CardActionTrigger into MessageEvent."""
    event = getattr(data, "event", None) or {}
    action = getattr(event, "action", None)
    operator = getattr(event, "operator", None)
    context = getattr(event, "context", None)
    value = getattr(action, "value", None) if action else None
    if not isinstance(value, dict):
        value = {"option": str(value or "")}

    payload = {
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {
                "open_id": str(getattr(operator, "open_id", "") or "") if operator else "",
                "union_id": str(getattr(operator, "union_id", "") or "") if operator else "",
            },
            "action": {
                "tag": str(getattr(action, "tag", "") or "") if action else "",
                "value": value,
            },
            "context": {
                "open_chat_id": str(getattr(context, "open_chat_id", "") or "") if context else "",
                "open_message_id": str(getattr(context, "open_message_id", "") or "") if context else "",
                "chat_type": str(getattr(context, "chat_type", "") or "p2p") if context else "p2p",
            },
        },
    }
    return _parse_card_action_trigger(payload, payload["event"], assistant_id=assistant_id)
