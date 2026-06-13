# Evolux Design Docs (English)

**Languages:** **English** · [简体中文](../zh-CN/README.md)

| Document | Description | Status |
|----------|-------------|--------|
| [01-architecture.md](./design/01-architecture.md) | Orchestrator, sub-agents, triple routing, gateway | **Confirmed** |
| [02-detailed-design.md](./design/02-detailed-design.md) | Module APIs, data structures, config schema | **v0.1** |
| [03-implementation-plan.md](./design/03-implementation-plan.md) | Phases, milestones, TDD rhythm | **v0.1** |

## Reading order

1. [Architecture](./design/01-architecture.md) — full system picture
2. [Detailed design](./design/02-detailed-design.md) — implementation interfaces
3. [Implementation plan](./design/03-implementation-plan.md) — delivery history & phases

## Implementation status

All core phases (1–11) plus Hermes alignment, sedimentation, cron, and install/migration are **complete**. See [03-implementation-plan.md](./design/03-implementation-plan.md) for the milestone table.

Before contributing, read:

- [§1.4 Code principles](./design/01-architecture.md#14-code-principles) (in architecture doc)
- TDD workflow: pytest green → commit → push

## Chinese documentation

Full Chinese design docs (including extended architecture sections) remain at:

- [docs/design/01-系统架构文档.md](../../design/01-系统架构文档.md)
