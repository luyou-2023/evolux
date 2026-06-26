# midscenejs_luke

Luke 版视觉驱动 UI 自动化 SDK，参考 [Midscene.js](https://midscenejs.com/zh/introduction) 设计理念自研实现（非 `@midscene/web` 封装）。

## 设计

- **视觉优先**：基于 Playwright 截图 + 多模态 LLM，不依赖脆弱 DOM 选择器
- **自然语言步骤**：`aiAct` / `aiTap` / `aiQuery` / `aiAssert` 等 API
- **Playwright 集成**：`PlaywrightAgent` 绑定 `Page`；测试用 `PlaywrightAiFixture`

## 模型配置

OpenAI 兼容 Vision API（与 Evolux `llm` 配置可共用 endpoint）：

```bash
export MIDSCENE_LUKE_MODEL_BASE_URL="https://api.deepseek.com/v1"
export MIDSCENE_LUKE_MODEL_API_KEY="sk-..."
export MIDSCENE_LUKE_MODEL_NAME="deepseek-chat"
```

## 快速体验

```bash
cd midscenejs_luke
npm install
npx playwright install chromium
npm run test:smoke
```

## Evolux 集成

```bash
evolux expert install ui-automation --assistant cdp-automation
evolux midscene init
```

专家 `ui-automation-expert` 使用 toolset `evolux-ui-test` 与 skill `midscene-ui`。
