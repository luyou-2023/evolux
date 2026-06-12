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
- [Design index](docs/design/README.md)

## Phase 1 (current)

- Orchestrator loop (max 30 iterations)
- Sub-agent loop (max 90 iterations)
- AgentRegistry (JSON)
- SessionDB (SQLite)
- EvoluxAgent facade + CLI stub
