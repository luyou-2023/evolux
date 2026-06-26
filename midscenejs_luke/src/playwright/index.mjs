export { PlaywrightAgent, loadModelConfig } from '../playwright/agent.mjs';

/**
 * Playwright test fixture — mirrors Midscene PlaywrightAiFixture pattern.
 * Usage in e2e/fixture.mjs:
 *   import { createPlaywrightAiFixture } from 'midscenejs_luke/playwright';
 *   export const test = base.extend(createPlaywrightAiFixture());
 */
export function createPlaywrightAiFixture(options = {}) {
  return {
    agentForPage: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      await use(async (p) => new PlaywrightAgent(p || page, options));
    },
    ai: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((instruction) => agent.aiAct(instruction));
    },
    aiQuery: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((prompt) => agent.aiQuery(prompt));
    },
    aiAssert: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((assertion) => agent.aiAssert(assertion));
    },
    aiTap: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((target) => agent.aiTap(target));
    },
    aiInput: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((value, target) => agent.aiInput(value, target));
    },
    aiWaitFor: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((cond, opts) => agent.aiWaitFor(cond, opts));
    },
    recordToReport: async ({ page }, use) => {
      const { PlaywrightAgent } = await import('../playwright/agent.mjs');
      const agent = new PlaywrightAgent(page, options);
      await use((label) => agent.recordToReport(label));
    },
  };
}
