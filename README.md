# evolux

A self-evolving multi-agent runtime: orchestrator coordinates domain expert sub-agents.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gateway]"

evolux setup
export OPENAI_API_KEY=sk-...   # or put in ~/.evolux/.env

evolux chat                      # local orchestrator REPL
evolux gateway start             # Feishu webhook server :8787
pytest
```

## Architecture

```
Client (CLI / Feishu / …)
    → Gateway (async + thread pool)
    → Orchestrator Agent (30 iter) — triple routing
    → Sub Agents (90 iter) — domain execution
    → Tools / MCP / Skills / Vector index
```

## Docs

- [System architecture](docs/design/01-系统架构文档.md)
- [Detailed design](docs/design/02-详细设计文档.md)
- [Implementation plan](docs/design/03-实施计划.md)

## Progress

| Phase | Status |
|-------|--------|
| Phase 1 Core runtime | Done |
| Phase 2 Triple routing + compression | Done |
| Phase 3 Gateway + multi-assistant | Done |
| Phase 3.1 Webhook HTTP server | Done |
| Phase 4 MCP / Cron / polish | Partial |

## CLI

| Command | Description |
|---------|-------------|
| `evolux setup` | Init `~/.evolux` config and dirs |
| `evolux chat` | Interactive orchestrator session |
| `evolux assistant list` | List assistants |
| `evolux assistant bind feishu …` | Bind Feishu app to assistant |
| `evolux gateway start` | Run webhook server |
| `evolux gateway start --check` | Validate config only |

## Feishu webhook

Configure assistant then point Feishu event subscription to:

```
http://<host>:8787/webhook/feishu/<assistant_id>
```

## Config (`~/.evolux/config.yaml`)

- `orchestrator.max_iterations` — default 30
- `subagent.max_iterations` — default 90
- `llm.model` / `llm.base_url` — OpenAI-compatible API
- `gateway.host` / `gateway.port` — default `0.0.0.0:8787`
- `mcp_servers` — MCP lazy-load config (discovery stub)

Secrets: `~/.evolux/.env` (`OPENAI_API_KEY`, `EVOLUX_API_KEY`)

## Tests

61 pytest cases — TDD workflow, CI on push.
