import { test } from './fixture.mjs';

test.beforeEach(async ({ page }) => {
  await page.goto('https://example.com');
});

test('midscenejs_luke smoke — heading visible', async ({ aiAssert, aiQuery }) => {
  await aiAssert('页面存在主标题或 heading 元素');
  const title = await aiQuery('返回 JSON {"title": string}，页面主标题文本');
  console.log('title', title);
});
