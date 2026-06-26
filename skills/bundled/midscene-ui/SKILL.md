---
name: midscene-ui
description: "UI automation with midscenejs_luke (vision + Playwright): aiAct, aiQuery, aiAssert."
version: 1.0.0
author: Evolux
platforms: [linux, macos, windows]
metadata:
  evolux:
    tags: [UI, Playwright, Testing, Vision]
---

# midscene-ui — midscenejs_luke 视觉 UI 自动化

使用 **midscenejs_luke**（Luke 自研，Midscene 设计理念）+ Playwright 做 UI 测试，不依赖 DOM 选择器。

## 何时使用

- Web UI 自动化 / E2E 测试
- 自然语言描述步骤：`点击登录`、`断言列表有数据`
- Canvas、无 aria 元素、频繁改版的页面

## 前置

```bash
cd midscenejs_luke && npm install && npx playwright install chromium
export MIDSCENE_LUKE_MODEL_BASE_URL=https://api.deepseek.com/v1
export MIDSCENE_LUKE_MODEL_API_KEY=...
export MIDSCENE_LUKE_MODEL_NAME=deepseek-chat
```

## Evolux 工具

| 工具 | 用途 |
|------|------|
| `midscene_luke_run` | 单会话多步 workflow |
| `midscene_luke_init_project` | 初始化 ~/.evolux/ui-tests |
| `midscene_luke_run_playwright_test` | 跑 Playwright spec |
| `midscene_luke_status` | 检查引擎 |

## Workflow 示例（midscene_luke_run）

```json
{
  "url": "https://example.com",
  "steps": [
    {"type": "assert", "prompt": "页面有主标题"},
    {"type": "act", "prompt": "点击 More information 链接"},
    {"type": "query", "prompt": "返回 JSON {heading: string}", "name": "heading"}
  ]
}
```

## Playwright 测试集成

```javascript
import { test } from './fixture.mjs';

test('login flow', async ({ aiAct, aiAssert, aiQuery }) => {
  await aiAct('在用户名框输入 demo，密码框输入 secret，点击登录');
  await aiAssert('进入首页且显示欢迎语');
  const user = await aiQuery('JSON {name: string} 当前用户名');
});
```

## API 对照（midscenejs_luke ≈ Midscene）

| Midscene | midscenejs_luke |
|----------|-----------------|
| aiAct | aiAct |
| aiQuery | aiQuery |
| aiAssert | aiAssert |
| aiTap | aiTap |
| aiInput | aiInput |
| aiWaitFor | aiWaitFor |
| aiBoolean / aiNumber / aiString | 同名 |
| PlaywrightAgent | PlaywrightAgent |
| PlaywrightAiFixture | createPlaywrightAiFixture |

参考：https://midscenejs.com/zh/introduction

## 专家职责

- 用 `midscene_luke_run` 或 Playwright spec 执行测试
- 摘要须含：步骤、断言结果、失败截图/错误
- 勿用裸 terminal 绕过 midscenejs_luke 做 UI 点击
