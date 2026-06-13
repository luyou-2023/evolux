# Evolux System Architecture

> Version: v0.1  
> Audience: architects, core contributors  
> Baseline: [Hermes Agent](https://github.com/NousResearch/hermes-agent), extended for orchestrator + domain experts

**Languages:** **English** · [简体中文](../../design/01-系统架构文档.md) (full Chinese edition)

---

## Plain-language overview (read this first)

Evolux is a **self-hosted, evolvable multi-agent system**. Users talk via Feishu, CLI, or editors; Gateway hands work to an **orchestrator** that understands intent, picks experts, and coordinates; **sub-agents** (domain experts) do the deep work.

### Evolux vs Hermes

| Dimension | Hermes Agent | Evolux |
|-----------|--------------|--------|
| Conversation owner | Single agent + on-demand `delegate_task` | **Persistent orchestrator** + **expert sub-agent pool** |
| Sub-agents | Ephemeral workers, no domain identity | **Reusable domain experts** with registry + embeddings |
| Routing | Model decides delegation | **Skill ID + vector retrieval + orchestrator fusion** |
| Multi-assistant | Profile isolation (`-p`) | **Multiple assistants per platform**, isolated scope |
| Iteration caps | Default 90 | Orchestrator **30** / sub-agent **90** (configurable) |

```
User → Client (Feishu / CLI / …) → Gateway → Orchestrator (coordinate, memory, triple routing)
                                                    ↓
                                         Sub-agent pool (Skills preload, execute)
```

---

## 1. System overview

### 1.1 Product positioning

**Evolux** is a self-hosted **multi-agent collaboration runtime**. It separates the user-facing orchestrator from domain sub-agents. Gateway connects clients; the orchestrator coordinates, remembers, and evolves; sub-agents execute with focused toolsets.

### 1.2 Design goals

| Goal | Approach |
|------|----------|
| Separation of concerns | Orchestrator coordinates; sub-agents execute one domain |
| Smart routing | Skill ID + vector sub-agent search + LLM decision; create on miss |
| Long conversations | Main session persistence; compression (keep recent turns + summary) |
| Unified entry | Gateway: Feishu, CLI, ACP, dashboard |
| Multi-assistant | Per-assistant sessions, memory, routing |
| Extensibility | Tool registry, MCP, Skills (Hermes model) |
| Cost control | Tiered iteration budgets, compression, prefix-cache friendly memory |

### 1.3 Non-goals

- Not a general DAG workflow engine (orchestrator coordinates in-turn)
- Not multi-tenant SaaS (single-process gateway + thread pool)
- Sub-agents are not long-lived background daemons (spawn on demand; cron for schedules)

### 1.4 Code principles

- **Minimal diff** — only change what the task needs
- **YAGNI** — no speculative abstractions
- **Config over hardcoding** — iteration limits, fusion weights, compression in `config.yaml`
- **Explicit extension points** — tools, platforms, vector backends via registry/ABC
- **Graceful degradation** — vector/skill failures fall back; orchestrator turn continues
- **Readable code** — typed public APIs; English identifiers; user-facing logs may be localized

### 1.5 Development mode

TDD: write failing test → implement → `pytest -m "not live"` green → commit → push.

---

## 2. Logical architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Clients: CLI · Feishu · TUI · Dashboard · ACP · …           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  Gateway (asyncio + thread pool)                              │
│  Platform adapters · auth · slash commands · multi-assistant  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  Orchestrator Agent (default max 30 iterations)               │
│  Main session · memory · tools · MCP · Skills · compression   │
└────────────────────────────┬─────────────────────────────────┘
                             │ dispatch / create
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  Sub-agent pool (default max 90 iterations each)              │
│  Domain experts · isolated context · result summaries         │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
        Tools · MCP · Skills · Vector indexes · ~/.evolux/
```

---

## 3. Core concepts

### 3.1 Orchestrator

The **only agent that talks to the user** directly. Holds the **main session**.

Responsibilities:

1. Intent understanding
2. Triple routing (§4.4)
3. Create sub-agents when no match
4. Coordinate parallel/serial dispatch
5. Summarize results for the user

Default **30 iterations** — enough to plan, delegate, and reply.

### 3.2 Sub-agent (domain expert)

Execution unit with **persistent identity** (`agent_id`, domain, embedding).

- Isolated context (task slice from orchestrator, not full main history)
- Independent toolsets and per-agent MEMORY
- Cannot spawn sub-agents (v0.1)
- Returns structured summary to orchestrator

Lifecycle: create/register → vector index → spawn on dispatch → destroy instance → keep registry for reuse.

### 3.3 Main session vs sub-session

| Type | Purpose | Persistence |
|------|---------|-------------|
| Main | User ↔ orchestrator | Permanent (compression chain) |
| Sub | Single dispatch | Task-scoped; optional archive to agent MEMORY |

Session key format:

```
orchestrator:{assistant_id}:{platform}:{chat_type}:{chat_id}[:thread_id][:user_id]
```

---

## 4. Request flow

1. Client → Gateway (webhook / CLI / ACP)
2. Gateway resolves `assistant_id` + `session_key`
3. `run_orchestrator_turn(session, message)`
4. Parallel routing preflight: Skill ID + sub-agent vector search
5. Fusion → orchestrator LLM decides: self-execute / dispatch / create
6. Sub-agent runs with Skill preload (≤90 iter)
7. Orchestrator merges → main session → reply to client

### 4.1 Gateway

- Asyncio loop; sync agent loop in thread pool
- `gateway/run.py` — routing, agent cache
- `gateway/session.py` — session keys, reset
- `gateway/platforms/*` — Feishu, etc.
- `gateway/assistant_registry.py` — multi-assistant bindings
- Background cron ticker (Hermes-aligned `jobs.json`)

### 4.2 Orchestrator loop

Loads compressed history + memory snapshot + routing context → LLM with orchestrator tools (`dispatch_subagent`, `create_subagent`, `plan_task`, `cronjob`, …) → tool results until final reply or budget exhausted.

### 4.3 Sub-agent loop

Load agent definition + Skill instructions → sub-agent toolset (MCP subset) → return summary (no raw tool noise in main session).

### 4.4 Triple routing

```
User message
  ├─① Skill identification → skill_candidates[]
  ├─② Vector sub-agent search → subagent_candidates[]
  ├─③ Fusion (α·vector + β·skill_overlap + γ·recency)
  └─④ Orchestrator LLM → execute / dispatch / create
```

Skill layers: L1 keyword/BM25 on metadata; L2 vector on Skill embeddings.

Fusion injected into orchestrator system prompt as a routing preflight block.

---

## 5. Memory, context, vectors

### 5.1 Memory layers

| Layer | Location | Scope |
|-------|----------|-------|
| USER.md | `memories/USER.md` | User profile |
| MEMORY.md | `memories/MEMORY.md` | Global cross-domain notes |
| Agent MEMORY | `memories/agents/<id>/` | Domain expert notes |
| SOLUTIONS.md | `memories/SOLUTIONS.md` | Reusable playbooks |
| Session DB | `state.db` + FTS5 | Searchable history |

**Frozen snapshot** at session start for prefix cache stability; mid-session writes persist but don't bust current turn prefix.

### 5.2 Sedimentation (Evolux-specific)

After turns: write global MEMORY, agent MEMORY, SOLUTIONS; optional LLM extract; expert auto-promotion on repeat tasks.

### 5.3 Vector stores

- Skill index: `vector/skills.db`
- Sub-agent index: `vector/subagents.db`
- Backends: `sqlite-vec` (default), `sqlite`, `json`

### 5.4 Context compression

Keep recent **10 turns** (configurable); summarize older messages; compression chain via `parent_session_id`.

---

## 6. Clients & multi-assistant

| Client | Status |
|--------|--------|
| CLI | ✅ |
| Feishu webhook | ✅ |
| Dashboard / SSE | ✅ |
| ACP (editors) | ✅ |
| TUI | ✅ |
| Telegram / others | Hermes adapters reusable |

**Multi-assistant:** `assistants.<id>` in config — separate sessions, routing weights, platform bindings on one gateway.

**Profiles:** `evolux -p <name>` → `~/.evolux/profiles/<name>/` (Hermes-compatible).

---

## 7. Tools, MCP, Skills

### 7.1 Tool registry

Self-registering modules in `tools/`; orchestrator vs sub-agent toolsets; `DELEGATE_BLOCKED_TOOLS` on sub-agents.

### 7.2 Toolsets

Presets: `evolux-orchestrator`, `evolux-code`, `evolux-acp`, `cronjob`, … Hermes alias `hermes-acp` supported.

### 7.3 MCP

Lazy discovery from `mcp_servers` in config; tools prefixed `mcp_{server}_{tool}`; HTTP + stdio transport; sampling support.

### 7.4 Skills

agentskills.io `SKILL.md`; progressive disclosure (`skills_list` → `skill_view`); bundled + user skills under `~/.evolux/skills/`.

---

## 8. Persistence layout

```
~/.evolux/
├── config.yaml
├── .env
├── state.db              # sessions, messages, FTS5, compression_log
├── memories/
├── agents/registry.json
├── skills/
├── cron/jobs.json
├── vector/
└── migration/hermes/     # import archives
```

---

## 9. Hermes relationship

### Reused patterns

- Tool registry, MCP bridge, Skill progressive disclosure
- Cron `jobs.json`, slash commands, ACP adapter
- Session monitor, clarify cards

### Evolux extensions

- Persistent `AgentRegistry` + sub-agent vector index
- Triple routing fusion
- Sedimentation + SOLUTIONS + expert promotion
- Multi-assistant registry
- `migrate from-hermes` import path

```
Hermes:  User → Gateway → AIAgent ──delegate──→ ephemeral worker
Evolux:  User → Gateway → Orchestrator ──dispatch──→ persistent domain expert
                              ↓
                         sedimentation → MEMORY / experts / cron
```

---

## 10. Security & observability

- Secrets in `.env` only; DM pairing patterns from Hermes where applicable
- Structured logging; dashboard SSE activity; `evolux chat --trace`
- Cron/recursion guards (`platform=cron` blocks nested `cronjob`)

---

## Appendix A: Glossary

| Term | Meaning |
|------|---------|
| Orchestrator | User-facing coordinating agent |
| Sub-agent | Domain expert executor |
| Triple routing | Skill + vector + LLM fusion |
| Sedimentation | Post-turn persistent memory writeback |
| Expert promotion | Auto-create registry entry on repeat tasks |

---

## Appendix B: References

- [Detailed design](./02-detailed-design.md)
- [Implementation plan](./03-implementation-plan.md)
- [Chinese full architecture](../../design/01-系统架构文档.md)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
