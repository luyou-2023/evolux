#!/usr/bin/env node
/**
 * midscenejs_luke workflow runner for Evolux tools.
 * Usage: node runner.mjs '<json>'  OR  echo '{}' | node runner.mjs
 */

import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { PlaywrightAgent } from './src/playwright/agent.mjs';

async function readPayload() {
  const arg = process.argv[2];
  if (arg && arg !== '-') {
    return JSON.parse(arg);
  }
  return JSON.parse(readFileSync(0, 'utf-8') || '{}');
}

async function runStep(agent, page, step) {
  const type = step.type;
  switch (type) {
    case 'goto':
      await page.goto(step.url, { waitUntil: step.waitUntil || 'domcontentloaded' });
      return { ok: true, url: page.url() };
    case 'act':
      return { ok: true, ...(await agent.aiAct(step.prompt)) };
    case 'tap':
      return { ok: true, ...(await agent.aiTap(step.prompt || step.target)) };
    case 'input':
      return {
        ok: true,
        ...(await agent.aiInput(step.value ?? step.text, step.prompt || step.target)),
      };
    case 'wait':
      return { ok: true, ...(await agent.aiWaitFor(step.prompt, step.options || {})) };
    case 'query':
      return { ok: true, result: await agent.aiQuery(step.prompt) };
    case 'assert':
      await agent.aiAssert(step.prompt);
      return { ok: true, passed: true };
    case 'boolean':
      return { ok: true, result: await agent.aiBoolean(step.prompt) };
    case 'number':
      return { ok: true, result: await agent.aiNumber(step.prompt) };
    case 'string':
      return { ok: true, result: await agent.aiString(step.prompt) };
    case 'locate':
      return { ok: true, result: await agent.aiLocate(step.prompt) };
    case 'scroll':
      await agent.aiScroll(step.options || {}, step.prompt || step.target || '');
      return { ok: true };
    case 'sleep':
      await page.waitForTimeout(Number(step.ms || 1000));
      return { ok: true };
    default:
      throw new Error(`unknown step type: ${type}`);
  }
}

async function main() {
  const payload = await readPayload();
  const browser = await chromium.launch({
    headless: payload.headless !== false,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewportSize(payload.viewport || { width: 1280, height: 768 });
  if (payload.url) {
    await page.goto(payload.url, { waitUntil: 'domcontentloaded' });
  }

  const agent = new PlaywrightAgent(page, payload.agentOptions || {});
  const results = [];

  try {
    for (const [index, step] of (payload.steps || []).entries()) {
      const name = step.name || `${step.type}_${index + 1}`;
      try {
        const output = await runStep(agent, page, step);
        results.push({ name, type: step.type, ...output });
        if (output.success === false) {
          if (payload.stopOnError !== false) break;
        }
      } catch (error) {
        results.push({
          name,
          type: step.type,
          ok: false,
          error: String(error?.message || error),
        });
        if (payload.stopOnError !== false) break;
      }
    }
  } finally {
    await browser.close();
  }

  const success = results.every((item) => item.ok !== false && item.success !== false);
  process.stdout.write(
    JSON.stringify(
      {
        success,
        engine: 'midscenejs_luke',
        results,
        final_url: payload.url || '',
      },
      null,
      0,
    ),
  );
}

main().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exit(1);
});
