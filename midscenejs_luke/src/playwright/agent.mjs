import { loadModelConfig, parseJsonFromText, visionChat } from './model.mjs';
import { captureScreenshotBase64, executeAction, waitForNetworkIdle } from './executor.mjs';

const PLAN_SYSTEM = `You are midscenejs_luke, a vision-driven UI automation planner.
Given a screenshot and user instruction, output ONE JSON object for the next step only.
Schema:
{"action":"tap"|"input"|"scroll"|"wait"|"done"|"fail","x":number,"y":number,"text":string,"direction":"up"|"down","ms":number,"reason":string}
- Coordinates are pixel positions in the screenshot (top-left origin).
- Use "done" when the instruction is fully satisfied.
- Use "fail" when the goal is impossible on this page.
Return JSON only, no markdown.`;

const QUERY_SYSTEM = `You extract structured data from UI screenshots for automated testing.
Return JSON only matching the user request. No markdown.`;

const ASSERT_SYSTEM = `You verify UI assertions from screenshots for automated testing.
Return JSON: {"pass": boolean, "reason": string}`;

/**
 * Vision-driven Playwright agent — Midscene-inspired API surface.
 */
export class PlaywrightAgent {
  /**
   * @param {import('playwright').Page} page
   * @param {{ replanningCycleLimit?: number, waitForNetworkIdleTimeout?: number }} [opts]
   */
  constructor(page, opts = {}) {
    this.page = page;
    this.cfg = loadModelConfig();
    this.replanningCycleLimit = opts.replanningCycleLimit ?? 20;
    this.waitForNetworkIdleTimeout = opts.waitForNetworkIdleTimeout ?? 2000;
    this.reportSteps = [];
  }

  async _shot() {
    return captureScreenshotBase64(this.page);
  }

  async _plan(userPrompt, extra = '') {
    const image = await this._shot();
    const text = await visionChat(
      this.cfg,
      PLAN_SYSTEM,
      `${userPrompt}\n${extra}`.trim(),
      image,
    );
    return parseJsonFromText(text);
  }

  async _ask(system, prompt) {
    const image = await this._shot();
    const text = await visionChat(this.cfg, system, prompt, image);
    return parseJsonFromText(text);
  }

  /** Autonomous plan-and-act loop (Midscene aiAct). */
  async aiAct(instruction) {
    const steps = [];
    for (let i = 0; i < this.replanningCycleLimit; i += 1) {
      const action = await this._plan(instruction, `Step ${i + 1}/${this.replanningCycleLimit}`);
      steps.push(action);
      this.reportSteps.push({ type: 'act', instruction, action });
      if (action.action === 'done') {
        await waitForNetworkIdle(this.page, this.waitForNetworkIdleTimeout);
        return { success: true, steps };
      }
      if (action.action === 'fail') {
        return { success: false, steps, error: action.reason || 'planner failed' };
      }
      await executeAction(this.page, action);
      await waitForNetworkIdle(this.page, this.waitForNetworkIdleTimeout);
    }
    return { success: false, steps, error: 'replanning cycle limit reached' };
  }

  async aiTap(targetDescription) {
    const action = await this._plan(`Tap/click: ${targetDescription}`);
    if (action.action === 'fail') {
      throw new Error(action.reason || `cannot tap: ${targetDescription}`);
    }
    if (action.action !== 'tap' && action.action !== 'done') {
      action.action = 'tap';
    }
    if (action.action === 'tap') {
      await executeAction(this.page, action);
    }
    await waitForNetworkIdle(this.page, this.waitForNetworkIdleTimeout);
    return action;
  }

  async aiInput(value, targetDescription) {
    const action = await this._plan(`Input "${value}" into: ${targetDescription}`);
    action.action = 'input';
    action.text = String(value);
    await executeAction(this.page, action);
    await waitForNetworkIdle(this.page, this.waitForNetworkIdleTimeout);
    return action;
  }

  async aiWaitFor(condition, options = {}) {
    const timeoutMs = Number(options.timeoutMs || 15000);
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const result = await this._ask(ASSERT_SYSTEM, `Is this true on the page? ${condition}`);
      if (result?.pass) {
        return result;
      }
      await this.page.waitForTimeout(800);
    }
    throw new Error(`aiWaitFor timeout: ${condition}`);
  }

  async aiScroll(options = {}, targetDescription = '') {
    const direction = options.scrollType === 'untilTop' ? 'up' : 'down';
    await executeAction(this.page, { action: 'scroll', direction });
    if (targetDescription) {
      await this._plan(`After scroll, verify visible: ${targetDescription}`);
    }
  }

  async aiQuery(prompt) {
    return this._ask(QUERY_SYSTEM, prompt);
  }

  async aiBoolean(prompt) {
    const result = await this._ask(ASSERT_SYSTEM, prompt);
    return Boolean(result?.pass);
  }

  async aiNumber(prompt) {
    const result = await this._ask(QUERY_SYSTEM, `Return JSON {"value": number}. ${prompt}`);
    return Number(result?.value ?? result);
  }

  async aiString(prompt) {
    const result = await this._ask(QUERY_SYSTEM, `Return JSON {"value": string}. ${prompt}`);
    return String(result?.value ?? result ?? '');
  }

  async aiLocate(prompt) {
    const action = await this._plan(`Locate element center for: ${prompt}. Return tap coords or done.`);
    return {
      center: { x: action.x, y: action.y },
      reason: action.reason || '',
    };
  }

  async aiAssert(assertion) {
    const result = await this._ask(ASSERT_SYSTEM, assertion);
    if (!result?.pass) {
      throw new Error(result?.reason || `assertion failed: ${assertion}`);
    }
    return result;
  }

  async recordToReport(label = 'snapshot') {
    this.reportSteps.push({ type: 'report', label, url: this.page.url() });
  }

  async destroy() {
    /* browser lifecycle owned by caller */
  }
}

export { loadModelConfig };
