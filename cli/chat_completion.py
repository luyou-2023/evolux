"""Interactive CLI chat slash-command tab completion."""

from __future__ import annotations

from agent.slash_catalog import slash_completions


def install_slash_completer() -> bool:
    try:
        import readline
    except ImportError:
        return False

    def _complete(text: str, state: int) -> str | None:
        buffer = readline.get_line_buffer()
        if not buffer.startswith("/"):
            return None
        end = readline.get_endidx()
        prefix = buffer[:end]
        candidates = slash_completions(prefix)
        if state >= len(candidates):
            return None
        return candidates[state]

    readline.set_completer(_complete)
    readline.parse_and_bind("tab: complete")
    return True
