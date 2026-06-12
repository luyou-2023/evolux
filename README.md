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
| Phase 3 Gateway + multi-assistant | Planned |
| Phase 4 Extensions | Planned |

## Phase 2 highlights

- Skill Router (keyword + vector) + SubAgent vector index
- `fuse_routing()` triple-route fusion
- Context compression (keep recent 10 turns)
- Memory snapshot (MEMORY/USER)
- Orchestrator tools: `identify_skills`, `search_subagents`, `dispatch_subagent`, `create_subagent`
- `EvoluxAgent.prepare_routing()` integrated into turns
