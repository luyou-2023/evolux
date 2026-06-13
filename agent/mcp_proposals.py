"""Pending MCP server proposals awaiting user approval."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from evolux_constants import get_evolux_home


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MCPProposal:
    name: str
    transport: str
    reason: str = ""
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    status: str = "pending"
    created_at: str = field(default_factory=_utc_now)


class MCPProposalStore:
    def __init__(self, home: Path | None = None):
        self.home = home or get_evolux_home()
        self.path = self.home / "state" / "mcp_proposals.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_proposals(self, *, status: str | None = "pending") -> list[MCPProposal]:
        items = []
        for raw in self._read():
            proposal = MCPProposal(**raw)
            if status is None or proposal.status == status:
                items.append(proposal)
        return items

    def add_proposal(self, proposal: MCPProposal) -> MCPProposal:
        items = self._read()
        items = [item for item in items if item.get("name") != proposal.name]
        items.append(asdict(proposal))
        self._write(items)
        return proposal

    def set_status(self, name: str, status: str) -> MCPProposal | None:
        items = self._read()
        found: MCPProposal | None = None
        for idx, raw in enumerate(items):
            if raw.get("name") != name:
                continue
            raw["status"] = status
            items[idx] = raw
            found = MCPProposal(**raw)
            break
        if found is None:
            return None
        self._write(items)
        return found

    def get(self, name: str) -> MCPProposal | None:
        for raw in self._read():
            if raw.get("name") == name:
                return MCPProposal(**raw)
        return None


def proposal_to_server_config(proposal: MCPProposal) -> dict[str, Any]:
    if proposal.transport == "http":
        if not proposal.url:
            raise ValueError("url is required for http transport")
        return {"url": proposal.url, "enabled": True}
    if not proposal.command:
        raise ValueError("command is required for stdio transport")
    return {"command": proposal.command, "args": list(proposal.args or []), "enabled": True}


def persist_mcp_server_to_config(home: Path, name: str, config: dict[str, Any]) -> None:
    config_path = home / "config.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded
    servers = raw.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        servers = {}
        raw["mcp_servers"] = servers
    servers[name] = dict(config)
    config_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
