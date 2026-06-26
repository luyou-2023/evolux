import { test as base } from '@playwright/test';
import { createPlaywrightAiFixture } from '../../src/playwright/index.mjs';

export const test = base.extend(createPlaywrightAiFixture({
  replanningCycleLimit: 30,
  waitForNetworkIdleTimeout: 2000,
}));

export { expect } from '@playwright/test';
