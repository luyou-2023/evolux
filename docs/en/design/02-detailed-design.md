# Evolux Detailed Design

> Version: v0.1  
> Prerequisite: [01-architecture.md](./01-architecture.md)  
> Audience: core developers

**Languages:** **English** · [简体中文](../../design/02-详细设计文档.md)

---

## 1. Module overview

```
run_agent.EvoluxAgent          # Facade: Session + Registry + routing + orchestrator
├── agent/
│   ├── orchestrator.py        # Orchestrator turn + routing_context injection
│   ├── subagent.py            # Sub-agent execution
│   ├── conversation_loop.py   # Shared LLM ↔ tool loop
│   ├── routing.py             # fuse_routing, RoutingContext
│   ├── skill_router.py        # Skill L1/L2 identification
│   ├── context_compressor.py  # Keep recent turns + summary
│   ├── memory_manager.py      # MEMORY/USER snapshots
│   ├── sedimentation.py       # Post-turn MEMORY / SOLUTIONS
│   ├── expert_promotion.py    # Repeat-task expert creation
│   ├── goals_manager.py       # /goal cross-session objectives
│   ├── planning_state.py      # Per-turn dispatch state
│   └── agent_registry.py      # Sub-agent JSON registry
├── vector/
│   ├── embedder.py
│   ├── store.py               # sqlite-vec / sqlite / json
│   ├── skill_index.py
│   └── subagent_index.py
├── tools/
│   ├── orchestrator_tools.py  # dispatch/create/search/plan_task/cronjob
│   └── registry.py
├── gateway/                   # Async entry, platforms, dashboard
├── cron/                      # Hermes-aligned scheduler + jobs.json
├── mcp/                       # MCP manager + registry bridge
└── evolux_state.py            # SessionDB + FTS5
```

**Dependency rule:** `run_agent` → `agent` → `vector`; `gateway` → `agent`; no upward imports.

---

## 2. Core data structures

### 2.1 Routing

```python
@dataclass
class SkillCandidate:
    skill_name: str
    score: float
    match_source: str  # keyword | vector

@dataclass
class SubAgentCandidate:
    agent_id: str
    vector_score: float
    skills: list[str]

@dataclass
class FusionWeights:
    vector_weight: float = 0.5
    skill_overlap_weight: float = 0.4
    recency_weight: float = 0.1

@dataclass
class RoutingContext:
    skill_candidates: list[SkillCandidate]
    subagent_candidates: list[SubAgentCandidate]
    fused_ranking: list[FusedCandidate]
    prompt_block: str  # injected into orchestrator system prompt
```

Fusion score:

```python
overlap = len(set(agent.skills) & skill_names) / max(len(skill_names), 1)
final = α * vector_score + β * overlap + γ * recency_boost
```

### 2.2 AgentDefinition

Stored in `agents/registry.json`: `agent_id`, `name`, `domain`, `description`, `skills`, `toolsets`, `system_prompt`, `stats`.

### 2.3 SessionDB

```python
# sessions: session_id, session_key, assistant_id, platform, parent_session_id, title
# messages: role, content, created_at
# messages_fts: FTS5 shadow (schema v3+)
# compression_log: parent/child session linkage
```

---

## 3. Key module APIs

| Module | Entry points |
|--------|--------------|
| `agent/routing.py` | `fuse_routing()`, `RoutingContext` |
| `agent/skill_router.py` | `identify()`, `scan_skills()`, `load_for_execution()` |
| `vector/subagent_index.py` | `search()`, `upsert()`, `remove()` |
| `tools/orchestrator_tools.py` | `dispatch_subagent`, `create_subagent`, `plan_task`, `cronjob` |
| `run_agent.EvoluxAgent` | `run_orchestrator_turn()`, `create_subagent()`, `dispatch_subagent()` |
| `cron/store.py` | `CronJobStore` — Hermes-compatible `jobs.json` |
| `cli/hermes_migration.py` | `migrate_from_hermes()` |

---

## 4. Config schema (excerpt)

```yaml
orchestrator:
  max_iterations: 30
  max_concurrent_subagents: 3
subagent:
  max_iterations: 90
routing:
  fusion:
    vector_weight: 0.5
    skill_overlap_weight: 0.4
    recency_weight: 0.1
llm:
  provider: deepseek
  model: deepseek-chat
mcp_servers: {}
sedimentation:
  enabled: true
  memory_after_turn: true
expert_promotion:
  enabled: true
  min_repeat: 2
cron:
  tick_seconds: 60
assistants:
  default:
    platforms:
      cli: {}
```

Loaded by `agent/settings.py::load_settings()`.

---

## 5. Routing sequence (implementation)

1. `prepare_routing(message)` — parallel Skill ID + sub-agent search
2. `fuse_routing()` — weighted merge
3. Inject `routing_context.prompt_block` into orchestrator system prompt
4. Orchestrator tools execute dispatch/create based on LLM + preflight

---

## 6. Error handling & degradation

| Failure | Behavior |
|---------|----------|
| Vector backend unavailable | Fall back to sqlite or json |
| Skill vector miss | Keyword/BM25 only |
| MCP server down | Tool error returned; turn continues |
| Sub-agent budget exhausted | Summary returned to orchestrator |

---

## 7. Test mapping

| Area | Tests |
|------|-------|
| Routing fusion | `test/agent/test_routing.py` |
| Skill router | `test/agent/test_skill_router.py` |
| Cron Hermes | `test/cron/test_hermes_cron.py` |
| Hermes migration | `test/cli/test_hermes_migration.py` |
| Gateway / Feishu | `test/gateway/` |

Run: `pytest -m "not live"`

---

## Appendix: Skill MD parsing

Skills use YAML frontmatter in `SKILL.md`:

```yaml
---
name: git
description: Git operations helper
---
```

Parsed by `agent/skill_router.py::parse_skill_md()`.

For the full Chinese edition with extended schema tables, see [02-详细设计文档.md](../../design/02-详细设计文档.md).
