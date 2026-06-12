# evolux

A self-evolving multi-agent runtime: orchestrator coordinates domain expert sub-agents.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gateway]"

evolux setup
# put DEEPSEEK_API_KEY in ~/.evolux/.env

evolux skills install git       # install bundled skill
evolux skills reindex           # rebuild skill vector index
evolux cron list                # show scheduled jobs
evolux cron start               # run cron scheduler
evolux tui                       # terminal status UI
evolux dashboard start           # web dashboard :8787/dashboard
evolux gateway start             # Feishu webhook + dashboard
pytest
pytest -m live                   # DeepSeek live tests (needs API key)
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
| Phase 4 MCP / Cron / Dashboard / Feishu reply | Done |
| Phase 5 Skills / MCP tools / Cron jobs | Done |

## CLI

| Command | Description |
|---------|-------------|
| `evolux setup` | Init `~/.evolux` config and dirs |
| `evolux chat` | Interactive orchestrator session |
| `evolux skills list/install/reindex` | Manage Skill definitions |
| `evolux cron list/start` | Scheduled orchestrator jobs |
| `evolux tui` | Terminal assistant/session browser |
| `evolux dashboard start` | Web dashboard (assistants + sessions) |
| `evolux assistant list` | List assistants |
| `evolux assistant bind feishu …` | Bind Feishu app to assistant |
| `evolux gateway start` | Run webhook server + dashboard |
| `evolux gateway start --check` | Validate config only |

## Feishu webhook

Configure assistant then point Feishu event subscription to:

```
http://<host>:8787/webhook/feishu/<assistant_id>
```

When `app_id` and `app_secret` are configured, Evolux automatically sends the orchestrator reply back to Feishu via Open API.

## Config (`~/.evolux/config.yaml`)

- `orchestrator.max_iterations` — default 30
- `subagent.max_iterations` — default 90
- `llm.provider` / `llm.model` — default DeepSeek
- `gateway.host` / `gateway.port` — default `0.0.0.0:8787`
- `mcp_servers` — MCP stdio servers (lazy discovery, tools prefixed `mcp_*`)
- `cron.jobs` — scheduled orchestrator prompts
- `vector.embedding` — `hash` (default) or `openai`
- `evolux acp start --check` — validate editor tool wiring (Hermes-compatible)
- `assistants.<id>.routing.fusion` — per-assistant fusion weights

### Hermes-aligned surface

| Area | Evolux | Hermes parity |
|------|--------|---------------|
| Tools | `skills_list`, `skill_view`, `memory`, `session_search`, `read_file`, `write_file`, `todo` | same names + toolsets |
| MCP | `mcp_{server}_{tool}` registered in central registry | same prefix |
| Skills | bundled `native-mcp`, `github-auth`, `plan`, `git` | copied from Hermes catalog |
| ACP | `evolux acp start --check`, `hermes-acp` toolset alias | adapter skeleton |

Secrets: `~/.evolux/.env` (`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`)

## Tests

81 pytest cases — TDD workflow, CI on push. Live DeepSeek tests: `pytest -m live`.
