/** @typedef {import('playwright').Page} Page */

/**
 * @param {Page} page
 * @param {{ fullPage?: boolean }} [opts]
 */
export async function captureScreenshotBase64(page, opts = {}) {
  const buffer = await page.screenshot({
    type: 'png',
    fullPage: Boolean(opts.fullPage),
  });
  return buffer.toString('base64');
}

/**
 * @param {Page} page
 * @param {import('./model.mjs').PlannedAction} action
 */
export async function executeAction(page, action) {
  switch (action.action) {
    case 'tap':
      if (action.x == null || action.y == null) {
        throw new Error('tap requires x,y coordinates');
      }
      await page.mouse.click(action.x, action.y);
      return;
    case 'input':
      if (action.text == null) {
        throw new Error('input requires text');
      }
      if (action.x != null && action.y != null) {
        await page.mouse.click(action.x, action.y);
      }
      await page.keyboard.type(String(action.text), { delay: 20 });
      return;
    case 'scroll':
      await page.mouse.wheel(0, action.direction === 'up' ? -600 : 600);
      return;
    case 'wait':
      await page.waitForTimeout(Number(action.ms || 1000));
      return;
    case 'done':
    case 'fail':
      return;
    default:
      throw new Error(`unknown action: ${action.action}`);
  }
}

/**
 * @param {Page} page
 * @param {number} timeoutMs
 */
export async function waitForNetworkIdle(page, timeoutMs = 2000) {
  try {
    await page.waitForLoadState('networkidle', { timeout: timeoutMs });
  } catch {
    /* optional */
  }
}
