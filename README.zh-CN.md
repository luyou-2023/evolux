# Evolux

**Languages:** [English](README.md) · **简体中文**

**自托管、可进化的多 Agent 协作运行时** — 主控 Agent 负责理解、协调与记忆；领域子 Agent 负责深度执行。数据在你自己的机器上，能力随使用沉淀。

一条命令安装，飞书 / CLI / 编辑器 ACP 统一接入。已用 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的用户可一键迁移记忆、Skills 与定时任务。

---

## 为什么选择 Evolux？

大多数 Agent 是「一个大脑包打天下」：临时委派、用完即丢、路由靠模型临场发挥。复杂任务容易上下文膨胀、重复踩坑、成本难控。

Evolux 把**协调**和**执行**拆开，并让它们**越用越强**：

| | 典型单 Agent | Evolux |
|---|-------------|--------|
| **结构** | 单 Agent + 临时 delegate | **持久主控** + **领域专家子 Agent 池** |
| **路由** | 模型自行决定是否委派 | **Skill 识别 + 向量检索 + 主控推理** 三重融合 |
| **专家** | 每次从零开始 | 可创建、可检索、**重复任务自动晋升**为专家 |
| **记忆** | 会话内有效 | 全局 MEMORY / USER + **回合后沉淀** + 方案库 SOLUTIONS |
| **迭代预算** | 单一上限 | 主控 **30 轮**协调 / 子 Agent **90 轮**深执行，成本可控 |
| **多助手** | Profile 隔离 | **同平台多助手**，Session / 记忆 / 路由独立 |
| **Hermes 用户** | — | 工具 / MCP / Cron / ACP **兼容**，`migrate from-hermes` 导入沉淀 |

```
你（飞书 / CLI / 编辑器）
        │
        ▼
   Gateway ── 多助手、Webhook、Dashboard
        │
        ▼
  主控 Agent ── 规划、记忆、/goal、Session Monitor
        │
        ├── Skill 识别 ──┐
        ├── 向量检索专家 ─┼── 三重路由 → 选对子 Agent
        └── 主控推理 ────┘
        │
        ▼
  子 Agent 池 ── 预加载 Skill、深执行、MCP 工具
        │
        ▼
  沉淀 ── MEMORY · SOLUTIONS · 专家晋升 · Cron 复用
```

**适合谁：** 希望 Agent「像团队一样协作」、任务有领域分工、长期使用要积累经验的开发者与小团队。

---

## 安装

### 一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/luyou-2023/evolux/main/scripts/install.sh | bash
```

安装脚本会：

- 克隆代码到 `~/.evolux/evolux` 并安装 CLI
- 写入 `~/.local/bin/evolux`，配置 PATH
- 运行 `evolux setup`，**自动检测 Hermes**（`~/.hermes` / profiles / `$HERMES_HOME`）并询问是否导入

### 从 Hermes 迁移

```bash
evolux migrate detect                         # 查看本机 Hermes 安装与 profile
evolux migrate from-hermes --dry-run          # 预览将迁移的内容
evolux migrate from-hermes --preset full      # 含 .env 密钥
evolux setup --from-hermes                      # 首次 setup 时自动导入
```

迁移内容：MEMORY / USER、Skills、Cron、`config.yaml`（LLM / MCP / Gateway）、会话库归档；子 Agent 注册表由 Evolux 路由与专家晋升逐步填充。

### 开发者安装

```bash
git clone https://github.com/luyou-2023/evolux.git
cd evolux
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gateway]"

evolux setup
```

### 配置 API Key

在 `~/.evolux/.env` 中写入（任选其一）：

```bash
DEEPSEEK_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
```

默认模型为 DeepSeek，可在 `~/.evolux/config.yaml` 的 `llm` 段修改。

### 卸载

```bash
evolux uninstall              # 交互：仅删程序 / 连同数据一起删
evolux uninstall --keep-data  # 保留 ~/.evolux
evolux uninstall --full --yes # 完全清除
```

---

## 5 分钟上手

```bash
# 1. 初始化（若尚未 setup）
evolux setup

# 2. 对话 — 交互模式，/exit 退出；session 写入 ~/.evolux/state.db（与 Hermes 飞书 session 独立）
evolux chat

# 单轮脚本（session 仍会落盘，但进程立即退出）
# evolux chat --once "你好"

# 3. 看协调过程（工具 / 子 Agent / MCP）
evolux chat --trace

# 4. 飞书机器人 — 扫码/链接一键创建并写入 config
evolux feishu setup --assistant default
# 或: evolux assistant bind feishu --wizard --id work-bot

# 5. 安装 Skill 并重建索引
evolux skills install git
evolux skills reindex

# 6. 定时任务（Hermes 兼容）
evolux cron create "every 2h" "检查服务健康并摘要" --name health
evolux cron list
```

会话内可用 Hermes 风格 slash 命令：`/help` `/new` `/compress` `/goal` `/cron` `/skills` 等。

多 Profile（与 Hermes `-p` 一致）：

```bash
evolux -p work chat
evolux -p personal setup
```

---

## 日常使用

| 命令 | 说明 |
|------|------|
| `evolux chat` | 交互式主控会话 |
| `evolux chat --once "…"` | 单轮问答 |
| `evolux chat --trace` | 显示编排 trace |
| `evolux tui` | 终端会话 / 助手浏览 |
| `evolux dashboard start` | Web 面板 `http://localhost:8787/dashboard` |
| `evolux gateway install` | 安装用户级后台服务（Linux systemd / macOS launchd） |
| `evolux gateway start` | 启动已安装的后台服务 |
| `evolux gateway run` | 前台运行（Webhook + Dashboard + Cron） |
| `evolux gateway stop` / `restart` / `status` | 服务生命周期管理 |
| `evolux cron list/create/tick` | 定时任务管理 |
| `evolux skills list/install/reindex` | Skill 管理 |
| `evolux assistant list` | 多助手列表 |
| `evolux acp start` | 编辑器 ACP 适配（Cursor 等） |
| `evolux migrate detect` | 检测 Hermes 安装 |
| `eval "$(evolux completion zsh)"` | Shell 补全 |

---

## 飞书接入

**推荐（无需公网）：WebSocket 长连接** — 与 Hermes 默认方式一致。

1. 绑定助手：

```bash
evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret> --mode websocket
```

2. 在飞书开放平台 → **事件订阅 → 长连接（WebSocket）**，订阅 `im.message.receive_v1`。

3. 安装并启动 Gateway：

```bash
evolux gateway install    # systemd (Linux) / launchd (macOS)
evolux gateway start      # 启动后台服务（含 cron ticker）
# 或开发调试：
evolux gateway run        # 前台运行
```

**可选：Webhook 模式**（需要可达的 HTTP 地址）：

```bash
evolux assistant bind feishu ... --mode webhook
```

将事件订阅指向：

```
http://<你的主机>:8787/webhook/feishu/<assistant_id>
```

主控回复会自动回传飞书；协调进度、clarify 卡片、slash 命令在飞书内可用。

---

## 架构亮点（深入）

### 三重路由，不赌模型一次猜对

每一轮用户消息经过三条信号融合：**Skill 关键词/向量识别**、**子 Agent 向量检索**、**主控 LLM 推理**。未命中时动态 `create_subagent`，重复任务可 **自动晋升** 为持久专家。

### 分层迭代，省钱又够深

主控默认 **30 轮** — 足够规划、委派、汇总；子 Agent 默认 **90 轮** — 专注单一领域深挖。避免「一个 Agent 又当经理又当工人」导致的 token 浪费。

### 记忆与沉淀，越用越懂你

- 启动时注入 **MEMORY.md / USER.md** 冻结快照（利于 prefix cache）
- 回合结束后 **自动沉淀** 到全局 MEMORY 与 Agent 级 MEMORY
- 成功方案写入 **SOLUTIONS.md**，同类任务下次直接复用
- `/goal` 跨会话目标；FTS5 **session_search** 检索历史

### Hermes 生态兼容，平滑升级

工具名、MCP 前缀、`cronjob`、Skills 渐进式披露、ACP 会话持久化 — 与 Hermes 对齐。已有 Hermes 沉淀无需从零开始。

### 自托管、数据归你

```
~/.evolux/
├── config.yaml          # 模型、路由、Gateway、MCP
├── .env                 # API 密钥
├── state.db             # 会话 + FTS5
├── memories/            # MEMORY · USER · SOLUTIONS
├── agents/registry.json # 持久子 Agent 专家
├── skills/              # Skill 定义
├── cron/jobs.json       # 定时任务
└── vector/              # Skill / 子 Agent 向量索引
```

---

## 配置速查

`~/.evolux/config.yaml` 常用项：

| 配置 | 默认 | 说明 |
|------|------|------|
| `orchestrator.max_iterations` | 30 | 主控迭代上限 |
| `subagent.max_iterations` | 90 | 子 Agent 迭代上限 |
| `orchestrator.max_concurrent_subagents` | 3 | 并行子 Agent 数 |
| `llm.provider` / `llm.model` | deepseek / deepseek-chat | 模型 |
| `gateway.port` | 8787 | Gateway / Dashboard 端口 |
| `mcp_servers` | `{}` | MCP stdio/HTTP 服务 |
| `sedimentation.enabled` | true | 回合后 MEMORY 沉淀 |
| `expert_promotion.enabled` | true | 重复任务自动建专家 |
| `vector.backend` | sqlite-vec | 向量后端 |

---

## 文档

| 文档 | 内容 |
|------|------|
| [系统架构](docs/design/01-系统架构文档.md) | 主控/子 Agent、三重路由、Gateway、记忆模型 |
| [详细设计](docs/design/02-详细设计文档.md) | 模块接口、数据结构、配置 schema |
| [实施计划](docs/design/03-实施计划.md) | Phase 里程碑与实现进度 |
| [English docs](docs/en/README.md) | English documentation |

---

## 开发

```bash
pip install -e ".[dev,gateway]"
pytest -m "not live"          # 单元测试（209+）
pytest -m live                # 需 DEEPSEEK_API_KEY 的 live 测试
```

MIT License · 基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 架构演进，针对多 Agent 协调与持久专家优化。
