"""Slash command catalog for help text and CLI tab completion."""

from __future__ import annotations

SLASH_ROOT_COMMANDS: tuple[str, ...] = (
    "help",
    "commands",
    "new",
    "reset",
    "clear",
    "stop",
    "status",
    "sessions",
    "title",
    "resume",
    "skills",
    "history",
    "compress",
    "model",
    "tools",
    "retry",
    "undo",
    "goal",
    "mcp",
)

SLASH_SUBCOMMANDS: dict[str, tuple[str, ...]] = {
    "skills": ("browse", "list"),
    "goal": ("add", "done", "clear", "list"),
    "mcp": ("list", "approve", "reject"),
}

CHAT_LOCAL_COMMANDS: tuple[str, ...] = ("exit", "quit")


def slash_completions(prefix: str) -> list[str]:
    """Return completion candidates for an in-chat slash prefix (includes leading /)."""
    raw = (prefix or "").strip()
    if not raw.startswith("/"):
        return []
    body = raw[1:]
    if not body or " " not in body:
        token = body.lower()
        matches = [f"/{name}" for name in SLASH_ROOT_COMMANDS if name.startswith(token)]
        matches.extend(f"/{name}" for name in CHAT_LOCAL_COMMANDS if name.startswith(token))
        return sorted(set(matches))
    command, rest = body.split(None, 1)
    command = command.lower()
    subcommands = SLASH_SUBCOMMANDS.get(command, ())
    if not subcommands:
        return []
    token = rest.lower()
    return sorted(f"/{command} {sub}" for sub in subcommands if sub.startswith(token))
