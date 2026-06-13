# Evolux 设计文档

**Languages:** [English](../en/README.md) · **简体中文**

| 文档 | 说明 | 状态 |
|------|------|------|
| [01-系统架构文档.md](./01-系统架构文档.md) | 整体架构、主控/子 Agent、三重路由、Gateway | **已确认** |
| [02-详细设计文档.md](./02-详细设计文档.md) | 模块接口、数据结构、配置 schema | **v0.1** |
| [03-实施计划.md](./03-实施计划.md) | Phase 拆分、里程碑、Git 提交计划 | **v0.1** |

## 阅读顺序

1. [01-系统架构文档.md](./01-系统架构文档.md) — 架构全貌
2. [02-详细设计文档.md](./02-详细设计文档.md) — 实现接口与数据模型
3. [03-实施计划.md](./03-实施计划.md) — Phase 里程碑与 TDD 提交节奏

## 实现进度

| Phase | 状态 |
|-------|------|
| Phase 1 核心运行时 | ✅ 完成 |
| Phase 2 三重路由与压缩 | ✅ 完成 |
| Phase 3 Gateway 与多助手 | ✅ 完成 |
| Phase 3.1 Webhook HTTP 服务 | ✅ 完成 |
| Phase 4 扩展与打磨 | ✅ 完成 |
| Phase 5 Skills / MCP 集成 / Cron | ✅ 完成 |
| Hermes 对齐（tools/skills/MCP/ACP） | ✅ 完成 |
| Hermes 缺口补全（MCP HTTP / ACP session / clarify） | ✅ 完成 |
| Hermes 缺口补全（MCP sampling / ACP fork-resume） | ✅ 完成 |
| CLI/zsh 集成 + 飞书结构化回复 + 协调过程可见 | ✅ 完成 |
| 子 Agent 工具 trace + 飞书 clarify 卡片 + bash 补全 | ✅ 完成 |
| 飞书 clarify 卡片按钮回调（点选自动续聊） | ✅ 完成 |
| 飞书卡片点选 UI 更新 + Dashboard card_action 活动 | ✅ 完成 |
| 默认 Session Monitor 子 Agent（协调进度推送） | ✅ 完成 |
| Session Monitor slash 命令（/help /stop /new 等） | ✅ 完成 |
| Session Monitor 扩展命令（/compress /sessions /model /tools） | ✅ 完成 |
| Session Monitor /title /skills + 飞书 /commands 卡片 | ✅ 完成 |
| /resume + Dashboard 标题 + CLI slash Tab 补全 | ✅ 完成 |
| 自主规划 + 专家/方案沉淀（orchestrator prompt、create 增强、MEMORY/SOLUTIONS） | ✅ 完成 |
| P1 FTS5 + 压缩链 + 回合后 MEMORY 沉淀 | ✅ 完成 |
| P2 /goal + plan_task + 专家自动晋升 + MCP 提案 | ✅ 完成 |
| Cron Hermes 对齐（jobs.json、cronjob 工具、/cron、gateway tick） | ✅ 完成 |
| 安装/卸载 + Hermes 用户沉淀迁移（curl install、migrate from-hermes） | ✅ 完成 |
| Gateway 服务 install/start/stop（systemd / launchd） | ✅ 完成 |
| 飞书 WebSocket 长连接（无公网，Hermes 对齐） | ✅ 完成 |
| Phase 6 Feishu 工具 / ACP 进度流 | ✅ 完成 |
| Phase 7 SQLite 向量 / LLM 流式 / CI | ✅ 完成 |
| Phase 8 LLM tools 接线 / Sub-agent MCP 子集 | ✅ 完成 |
| Phase 9 Dashboard SSE / 路由工具裁剪 | ✅ 完成 |
| Phase 10 Dashboard 实时 UI / tool_choice / 并行 tool | ✅ 完成 |
| Phase 11 sqlite-vec / 工具调用测试 / SSE 过滤 | ✅ 完成 |

**实现前必读：**

- [§1.4 代码原则](./01-系统架构文档.md#14-代码原则)
- [§1.5 开发模式](./01-系统架构文档.md#15-开发模式测试驱动--通过后提交)
