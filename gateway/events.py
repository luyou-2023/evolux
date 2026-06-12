"""Gateway message events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway.session import SessionSource


@dataclass
class MessageEvent:
    assistant_id: str
    source: SessionSource
    text: str
    message_id: str | None = None
    is_card_action: bool = False
    card_action_option: str | None = None
    card_action_question: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
