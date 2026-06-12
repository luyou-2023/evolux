"""ACP CLI commands."""

from __future__ import annotations

from acp.entry import main as acp_main


def run_acp_start(*, foreground: bool = True) -> int:
    if not foreground:
        return acp_main(["--check"])
    return acp_main([])
