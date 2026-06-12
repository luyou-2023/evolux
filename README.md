# evolux

A self-evolving multi-agent runtime: orchestrator coordinates domain expert sub-agents.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
evolux version
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
| Phase 4 Extensions | Planned |

## Phase 2 highlights

- Skill Router (keyword + vector) + SubAgent vector index
- `fuse_routing()` triple-route fusion
- Context compression (keep recent 10 turns)
- Memory snapshot (MEMORY/USER)
- Orchestrator tools: `identify_skills`, `search_subagents`, `dispatch_subagent`, `create_subagent`
- `EvoluxAgent.prepare_routing()` integrated into turns

## Phase 3 highlights

- `build_session_key` with `assistant_id` isolation
- `AssistantRegistry` multi-assistant config
- `GatewayRunner` asyncio + thread pool bridge
- Feishu webhook parser + end-to-end gateway test
- CLI: `evolux setup`, `assistant bind/list`, `gateway start`

## CLI

```bash
evolux setup
evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret>
evolux assistant list
evolux gateway start
```
