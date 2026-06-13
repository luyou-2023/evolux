# Evolux

**Languages:** [English](README.md) · [简体中文](README.zh-CN.md)

**Self-hosted, evolving multi-agent runtime** — an orchestrator understands, coordinates, and remembers; domain expert sub-agents execute deeply. Your data stays on your machine; capabilities compound over time.

One-line install. Unified access from CLI, Feishu, and editor ACP. [Hermes Agent](https://github.com/NousResearch/hermes-agent) users can migrate memories, Skills, and cron jobs in one step.

---

## Why Evolux?

Most agents use a single brain for everything: ad-hoc delegation, no persistent experts, routing left to the model in the moment. Complex work inflates context, repeats mistakes, and burns tokens.

Evolux **separates coordination from execution** and makes both **stronger over time**:

| | Typical single agent | Evolux |
|---|---------------------|--------|
| **Structure** | One agent + ephemeral delegate | **Persistent orchestrator** + **domain expert pool** |
| **Routing** | Model decides delegation ad hoc | **Skill ID + vector retrieval + orchestrator reasoning** (triple fusion) |
| **Experts** | Start from scratch each time | Create, retrieve, **auto-promote** on repeat tasks |
| **Memory** | Session-scoped | Global MEMORY / USER + **post-turn sedimentation** + SOLUTIONS library |
| **Iteration budget** | Single limit | Orchestrator **30** turns / sub-agents **90** turns — cost-controlled |
| **Multi-assistant** | Profile isolation only | **Multiple assistants on one platform**, isolated sessions & routing |
| **Hermes users** | — | Compatible tools / MCP / Cron / ACP + `migrate from-hermes` |

```
You (Feishu / CLI / Editor)
        │
        ▼
   Gateway — multi-assistant, webhooks, dashboard
        │
        ▼
  Orchestrator — planning, memory, /goal, Session Monitor
        │
        ├── Skill identification ──┐
        ├── Vector expert search ──┼── triple routing → right sub-agent
        └── Orchestrator reasoning ┘
        │
        ▼
  Sub-agent pool — Skill preload, deep execution, MCP tools
        │
        ▼
  Sediment — MEMORY · SOLUTIONS · expert promotion · Cron reuse
```

**Built for:** developers and small teams who want agents to **collaborate like a team**, with domain division of labor and compounding experience over months.

---

## Installation

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/luyou-2023/evolux/main/scripts/install.sh | bash
```

The installer will:

- Clone into `~/.evolux/evolux` and install the CLI
- Add `~/.local/bin/evolux` to your PATH
- Run `evolux setup`, **auto-detect Hermes** (`~/.hermes`, profiles, `$HERMES_HOME`) and offer import

### Migrate from Hermes

```bash
evolux migrate detect                         # list local Hermes installs & profiles
evolux migrate from-hermes --dry-run          # preview migration
evolux migrate from-hermes --preset full      # include .env secrets
evolux setup --from-hermes                    # auto-import on first setup
```

Imports: MEMORY / USER, Skills, Cron, `config.yaml` (LLM / MCP / Gateway), session DB archive. Sub-agent registry fills via routing and expert promotion.

### Developer install

```bash
git clone https://github.com/luyou-2023/evolux.git
cd evolux
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gateway]"

evolux setup
```

### API keys

Add to `~/.evolux/.env`:

```bash
DEEPSEEK_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
```

Default model is DeepSeek; change under `llm` in `~/.evolux/config.yaml`.

### Uninstall

```bash
evolux uninstall              # interactive: code only vs full wipe
evolux uninstall --keep-data  # keep ~/.evolux
evolux uninstall --full --yes # remove everything
```

---

## Get started in 5 minutes

```bash
evolux setup
evolux chat                   # orchestrator routes to sub-agents automatically
evolux chat --trace           # show tools / sub-agents / MCP trace
evolux skills install git
evolux skills reindex
evolux cron create "every 2h" "Summarize service health" --name health
evolux cron list
```

In-session Hermes-style slash commands: `/help` `/new` `/compress` `/goal` `/cron` `/skills` …

Profiles (Hermes-compatible `-p`):

```bash
evolux -p work chat
evolux -p personal setup
```

---

## Daily commands

| Command | Description |
|---------|-------------|
| `evolux chat` | Interactive orchestrator session |
| `evolux chat --once "…"` | Single-turn reply |
| `evolux chat --trace` | Orchestration trace on stderr |
| `evolux tui` | Terminal session / assistant browser |
| `evolux dashboard start` | Web UI at `http://localhost:8787/dashboard` |
| `evolux gateway install` | Install user service (Linux systemd / macOS launchd) |
| `evolux gateway start` | Start installed background service |
| `evolux gateway run` | Foreground server (webhook + dashboard + cron) |
| `evolux gateway stop` / `restart` / `status` | Service lifecycle |
| `evolux cron list/create/tick` | Scheduled jobs |
| `evolux skills list/install/reindex` | Skill management |
| `evolux assistant list` | Multi-assistant list |
| `evolux acp start` | Editor ACP adapter (Cursor, etc.) |
| `evolux migrate detect` | Detect Hermes installs |
| `eval "$(evolux completion zsh)"` | Shell tab completion |

---

## Feishu integration

**Recommended (no public URL): WebSocket long connection** — Hermes-aligned default.

1. Bind assistant:

```bash
evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret> --mode websocket
```

2. In Feishu Open Platform → **Events → Long Connection (WebSocket)**, subscribe to `im.message.receive_v1`.

3. Install and start the gateway:

```bash
evolux gateway install    # systemd on Linux, launchd on macOS
evolux gateway start      # background service (includes cron ticker)
# or for local debugging:
evolux gateway run        # foreground
```

**Optional: Webhook mode** (requires a reachable HTTP endpoint):

```bash
evolux assistant bind feishu ... --mode webhook
```

Point Feishu event subscription to:

```
http://<your-host>:8787/webhook/feishu/<assistant_id>
```

Replies, coordination progress, clarify cards, and slash commands work inside Feishu.

---

## Architecture highlights

### Triple routing — don’t bet on one model guess

Every user message fuses **Skill keyword/vector ID**, **sub-agent vector retrieval**, and **orchestrator LLM reasoning**. On miss, `create_subagent` dynamically; repeat tasks **auto-promote** to persistent experts.

### Tiered iteration — deep enough, affordable

Orchestrator default **30 turns** for plan → delegate → summarize. Sub-agents default **90 turns** for focused domain work. Avoids one agent acting as both manager and worker.

### Memory & sedimentation — learns over time

- **MEMORY.md / USER.md** frozen snapshot at session start (prefix-cache friendly)
- **Post-turn sedimentation** to global and per-agent MEMORY
- **SOLUTIONS.md** for reusable playbooks
- `/goal` for cross-session objectives; FTS5 **session_search**

### Hermes-compatible upgrade path

Tool names, MCP prefix, `cronjob`, progressive Skill disclosure, ACP session persistence — aligned with Hermes. Existing Hermes sediment imports in one command.

### Self-hosted — your data, your machine

```
~/.evolux/
├── config.yaml          # model, routing, gateway, MCP
├── .env                 # API keys
├── state.db             # sessions + FTS5
├── memories/            # MEMORY · USER · SOLUTIONS
├── agents/registry.json # persistent sub-agent experts
├── skills/              # Skill definitions
├── cron/jobs.json       # scheduled jobs
└── vector/              # Skill & sub-agent indexes
```

---

## Configuration quick reference

| Key | Default | Description |
|-----|---------|-------------|
| `orchestrator.max_iterations` | 30 | Orchestrator turn limit |
| `subagent.max_iterations` | 90 | Sub-agent turn limit |
| `orchestrator.max_concurrent_subagents` | 3 | Parallel sub-agents |
| `llm.provider` / `llm.model` | deepseek / deepseek-chat | LLM |
| `gateway.port` | 8787 | Gateway & dashboard port |
| `mcp_servers` | `{}` | MCP stdio/HTTP servers |
| `sedimentation.enabled` | true | Post-turn MEMORY writeback |
| `expert_promotion.enabled` | true | Auto-create experts on repeat |
| `vector.backend` | sqlite-vec | Vector store backend |

---

## Documentation

| Document | Content |
|----------|---------|
| [Architecture](docs/en/design/01-architecture.md) | Orchestrator, sub-agents, triple routing, gateway |
| [Detailed design](docs/en/design/02-detailed-design.md) | Modules, data structures, config schema |
| [Implementation plan](docs/en/design/03-implementation-plan.md) | Phases & milestones |
| [中文文档](docs/zh-CN/README.md) | 简体中文设计文档 |
| [All languages](docs/README.md) | Documentation index |

---

## Development

```bash
pip install -e ".[dev,gateway]"
pytest -m "not live"          # unit tests (209+)
pytest -m live                # live DeepSeek tests (needs API key)
```

MIT License · Evolved from [Hermes Agent](https://github.com/NousResearch/hermes-agent), optimized for multi-agent coordination and persistent domain experts.
