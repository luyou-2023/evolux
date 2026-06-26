import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 90 * 1000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 768 },
  },
  reporter: [['list']],
});
