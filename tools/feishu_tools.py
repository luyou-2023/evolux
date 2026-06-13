"""Feishu platform tools for messaging and documents."""

from __future__ import annotations

import json
from typing import Any

from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu_api import build_feishu_client
from tools.registry import registry, tool_error


def _resolve_client(assistant_id: str = "default"):
    cfg = AssistantRegistry().get(assistant_id)
    if cfg is None:
        return None, tool_error(f"unknown assistant: {assistant_id}")
    client = build_feishu_client(cfg.platforms.get("feishu") or {})
    if client is None:
        return None, tool_error("Feishu credentials missing; run `evolux assistant bind feishu`")
    return client, None


def feishu_message(*, chat_id: str, text: str, assistant_id: str = "default") -> str:
    chat_id = (chat_id or "").strip()
    text = (text or "").strip()
    if not chat_id or not text:
        return tool_error("chat_id and text are required")
    client, err = _resolve_client(assistant_id)
    if err:
        return err
    try:
        body = client.send_text(chat_id, text)
    except Exception as exc:
        return tool_error(f"feishu_message failed: {exc}")
    return json.dumps({"success": True, "message_id": (body.get("data") or {}).get("message_id")}, ensure_ascii=False)


def feishu_doc_read(*, document_id: str, assistant_id: str = "default") -> str:
    document_id = (document_id or "").strip()
    if not document_id:
        return tool_error("document_id is required")
    client, err = _resolve_client(assistant_id)
    if err:
        return err
    try:
        body = client.read_doc_raw(document_id)
    except Exception as exc:
        return tool_error(f"feishu_doc_read failed: {exc}")
    data = body.get("data") or {}
    return json.dumps(
        {"success": True, "document_id": document_id, "content": data.get("content", "")},
        ensure_ascii=False,
    )


def feishu_doc_create(*, title: str, folder_token: str | None = None, assistant_id: str = "default") -> str:
    title = (title or "").strip()
    if not title:
        return tool_error("title is required")
    client, err = _resolve_client(assistant_id)
    if err:
        return err
    try:
        body = client.create_doc(title, folder_token=folder_token)
    except Exception as exc:
        return tool_error(f"feishu_doc_create failed: {exc}")
    doc = (body.get("data") or {}).get("document") or {}
    return json.dumps(
        {
            "success": True,
            "document_id": doc.get("document_id"),
            "title": doc.get("title") or title,
        },
        ensure_ascii=False,
    )


def feishu_doc_append(*, document_id: str, text: str, assistant_id: str = "default") -> str:
    document_id = (document_id or "").strip()
    text = (text or "").strip()
    if not document_id or not text:
        return tool_error("document_id and text are required")
    client, err = _resolve_client(assistant_id)
    if err:
        return err
    try:
        body = client.append_doc_text(document_id, text)
    except Exception as exc:
        return tool_error(f"feishu_doc_append failed: {exc}")
    return json.dumps({"success": True, "document_id": document_id, "result": body.get("data")}, ensure_ascii=False)


def check_feishu_requirements() -> bool:
    return True


def check_feishu_setup_available() -> bool:
    import sys

    from cli.feishu_setup import feishu_register_app_available

    return feishu_register_app_available() and sys.stdin.isatty()


def feishu_setup(
    *,
    assistant_id: str = "default",
    mode: str = "auto",
    app_name: str = "",
) -> str:
    """Run Feishu scan/URL wizard and bind credentials to an assistant."""
    from cli.feishu_setup import feishu_register_app_available, run_feishu_app_wizard
    from evolux_constants import get_evolux_home

    if not feishu_register_app_available():
        return tool_error("Feishu setup requires: pip install 'evolux[gateway]' (lark-oapi>=1.5.5)")
    import sys

    if not sys.stdin.isatty():
        return tool_error("Feishu scan setup must run in interactive CLI; use /feishu setup")

    registry = AssistantRegistry(home=get_evolux_home())
    registry.ensure_assistant(assistant_id)
    try:
        result = run_feishu_app_wizard(
            registry,
            assistant_id=assistant_id,
            app_name=app_name or None,
            mode=mode,
            open_browser=True,
        )
    except KeyboardInterrupt:
        return tool_error("Feishu setup cancelled")
    except Exception as exc:
        return tool_error(f"Feishu setup failed: {exc}")

    return json.dumps(
        {
            "success": True,
            "assistant_id": result.assistant_id,
            "app_id": result.app_id,
            "mode": result.mode,
            "message": "Feishu app created and bound. shared_hermes: keep Hermes gateway running.",
        },
        ensure_ascii=False,
    )


FEISHU_SETUP_SCHEMA = {
    "name": "feishu_setup",
    "description": (
        "Create and bind a Feishu bot via scan/URL (official register_app). "
        "Use when the user asks to integrate Feishu in CLI chat. "
        "Opens a link/QR in the terminal; user confirms in Feishu app. "
        "mode=auto picks shared_hermes when Hermes gateway runs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "assistant_id": {
                "type": "string",
                "description": "Evolux assistant id to bind (default: current assistant)",
            },
            "mode": {
                "type": "string",
                "enum": ["auto", "shared_hermes", "websocket", "webhook"],
                "description": "Feishu transport mode",
            },
            "app_name": {
                "type": "string",
                "description": "Preset Feishu app display name",
            },
        },
    },
}

FEISHU_MESSAGE_SCHEMA = {
    "name": "feishu_message",
    "description": "Send a text message to a Feishu chat.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["chat_id", "text"],
    },
}

FEISHU_DOC_READ_SCHEMA = {
    "name": "feishu_doc_read",
    "description": "Read raw text content from a Feishu document.",
    "parameters": {
        "type": "object",
        "properties": {"document_id": {"type": "string"}},
        "required": ["document_id"],
    },
}

FEISHU_DOC_CREATE_SCHEMA = {
    "name": "feishu_doc_create",
    "description": "Create a new Feishu document.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "folder_token": {"type": "string"},
        },
        "required": ["title"],
    },
}

FEISHU_DOC_APPEND_SCHEMA = {
    "name": "feishu_doc_append",
    "description": "Append a paragraph to an existing Feishu document.",
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["document_id", "text"],
    },
}


registry.register(
    "feishu_message",
    lambda args, **kwargs: feishu_message(
        chat_id=str(args.get("chat_id", "")),
        text=str(args.get("text", "")),
        assistant_id=str(kwargs.get("assistant_id", "default")),
    ),
    FEISHU_MESSAGE_SCHEMA,
    toolset="feishu",
    check_fn=check_feishu_requirements,
)
registry.register(
    "feishu_doc_read",
    lambda args, **kwargs: feishu_doc_read(
        document_id=str(args.get("document_id", "")),
        assistant_id=str(kwargs.get("assistant_id", "default")),
    ),
    FEISHU_DOC_READ_SCHEMA,
    toolset="feishu",
    check_fn=check_feishu_requirements,
)
registry.register(
    "feishu_doc_create",
    lambda args, **kwargs: feishu_doc_create(
        title=str(args.get("title", "")),
        folder_token=args.get("folder_token"),
        assistant_id=str(kwargs.get("assistant_id", "default")),
    ),
    FEISHU_DOC_CREATE_SCHEMA,
    toolset="feishu",
    check_fn=check_feishu_requirements,
)
registry.register(
    "feishu_doc_append",
    lambda args, **kwargs: feishu_doc_append(
        document_id=str(args.get("document_id", "")),
        text=str(args.get("text", "")),
        assistant_id=str(kwargs.get("assistant_id", "default")),
    ),
    FEISHU_DOC_APPEND_SCHEMA,
    toolset="feishu",
    check_fn=check_feishu_requirements,
)
registry.register(
    "feishu_setup",
    lambda args, **kwargs: feishu_setup(
        assistant_id=str(args.get("assistant_id") or kwargs.get("assistant_id") or "default"),
        mode=str(args.get("mode") or "auto"),
        app_name=str(args.get("app_name") or ""),
    ),
    FEISHU_SETUP_SCHEMA,
    toolset="feishu",
    check_fn=check_feishu_setup_available,
)
