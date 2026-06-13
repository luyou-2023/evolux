# Evolux Implementation Plan

> Version: v0.1  
> Prerequisites: [Architecture](./01-architecture.md), [Detailed design](./02-detailed-design.md)  
> Mode: TDD → green pytest → commit → push

**Languages:** **English** · [简体中文](../../design/03-实施计划.md)

---

## Milestone overview

| Milestone | Phase | Goal | Status |
|-----------|-------|------|--------|
| M0 | — | Architecture & design docs | ✅ Done |
| M1 | Phase 1 | Core runtime MVP | ✅ Done |
| M2 | Phase 2 | Triple routing + compression | ✅ Done |
| M3 | Phase 3 | Gateway + multi-assistant + Feishu | ✅ Done |
| M4 | Phase 4 | MCP / cron / polish | ✅ Done |
| M5 | Phase 5 | Skills CLI / MCP tools / cron jobs | ✅ Done |
| M6 | Phase 6 | Feishu tools / ACP progress | ✅ Done |
| M7 | Phase 7 | SQLite vectors / streaming / CI | ✅ Done |
| M8 | Phase 8 | LLM tools wiring / sub-agent MCP subset | ✅ Done |
| M9 | Phase 9 | Dashboard SSE / routing tool trim | ✅ Done |
| M10 | Phase 10 | Live dashboard UI / tool_choice / parallel tools | ✅ Done |
| M11 | Phase 11 | sqlite-vec / tool-call integration tests | ✅ Done |

---

## Post-phase deliverables (complete)

| Track | Highlights | Status |
|-------|------------|--------|
| Hermes alignment | Tools, MCP, ACP, slash commands, clarify cards | ✅ |
| Session Monitor | `/help`, `/compress`, `/goal`, `/cron`, Feishu cards | ✅ |
| Autonomous planning | Orchestrator prompt, `plan_task`, sedimentation | ✅ |
| P1 memory | FTS5, compression chain, post-turn MEMORY | ✅ |
| P2 goals & experts | `/goal`, expert auto-promotion, MCP proposals | ✅ |
| Cron Hermes | `jobs.json`, `cronjob` tool, gateway tick | ✅ |
| Install & migration | curl `install.sh`, `migrate from-hermes`, uninstall | ✅ |
| i18n docs | English + 简体中文 documentation | ✅ |

---

## Phase summaries

### Phase 1 — Core runtime ✅

- `EvoluxAgent` facade, orchestrator + sub-agent loops
- `AgentRegistry`, basic dispatch
- SessionDB, CLI chat

### Phase 2 — Triple routing & compression ✅

- `SkillRouter`, `SubAgentIndex`, `fuse_routing`
- Context compression (keep recent turns)
- Orchestrator tools: dispatch / create / search

### Phase 3 — Gateway & multi-assistant ✅

- Feishu webhook, assistant registry
- Session keys with `assistant_id`
- Dashboard skeleton

### Phase 4–5 — MCP, cron, skills ✅

- MCP lazy discovery, real stdio client
- Cron scheduler + CLI
- `evolux skills install/reindex`

### Phase 6–11 — Production hardening ✅

- Feishu doc tools, ACP tool progress stream
- SQLite + sqlite-vec vector backends
- Dashboard SSE, parallel tool execution
- Live UI, integration tests, CI (`not live` vs `live` markers)

---

## Current test baseline

```bash
pytest -m "not live"   # 209+ tests
pytest -m live         # DeepSeek live tests (optional)
```

---

## Risks & dependencies

| Risk | Mitigation |
|------|------------|
| Hermes GPL alignment | Interface compatibility; attribute Hermes-derived patterns |
| Vector native deps | Fallback to sqlite/json backends |
| Session schema drift from Hermes | Archive on migration; fresh Evolux sessions |

---

## Next steps (optional future work)

- Full English translation of extended Chinese architecture sections
- Telegram / Discord platform adapters from Hermes
- Feishu cron delivery (currently writes to `cron/output/`)
- Kanban / MOA voting (explicit non-goals in v0.1)

For sprint-level task tables and Git commit history, see [03-实施计划.md](../../design/03-实施计划.md).
