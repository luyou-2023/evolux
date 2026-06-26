/** @typedef {{ width: number, height: number }} ViewportSize */

/**
 * @typedef {Object} ModelConfig
 * @property {string} baseUrl
 * @property {string} apiKey
 * @property {string} model
 */

/**
 * @typedef {'tap'|'input'|'scroll'|'wait'|'done'|'fail'} ActionType
 */

/**
 * @typedef {Object} PlannedAction
 * @property {ActionType} action
 * @property {number} [x]
 * @property {number} [y]
 * @property {string} [text]
 * @property {string} [reason]
 * @property {number} [ms]
 * @property {'up'|'down'} [direction]
 */

export function loadModelConfig() {
  const baseUrl = (
    process.env.MIDSCENE_LUKE_MODEL_BASE_URL ||
    process.env.OPENAI_BASE_URL ||
    'https://api.openai.com/v1'
  ).replace(/\/$/, '');
  const apiKey =
    process.env.MIDSCENE_LUKE_MODEL_API_KEY ||
    process.env.OPENAI_API_KEY ||
    process.env.DEEPSEEK_API_KEY ||
    '';
  const model =
    process.env.MIDSCENE_LUKE_MODEL_NAME ||
    process.env.OPENAI_MODEL ||
    'gpt-4o-mini';
  return { baseUrl, apiKey, model };
}

/**
 * @param {ModelConfig} cfg
 * @param {string} system
 * @param {string} userText
 * @param {string} imageBase64
 */
export async function visionChat(cfg, system, userText, imageBase64) {
  if (!cfg.apiKey) {
    throw new Error(
      'MIDSCENE_LUKE_MODEL_API_KEY (or OPENAI_API_KEY / DEEPSEEK_API_KEY) is required',
    );
  }
  const url = `${cfg.baseUrl}/chat/completions`;
  const body = {
    model: cfg.model,
    messages: [
      { role: 'system', content: system },
      {
        role: 'user',
        content: [
          { type: 'text', text: userText },
          {
            type: 'image_url',
            image_url: { url: `data:image/png;base64,${imageBase64}` },
          },
        ],
      },
    ],
    temperature: 0.2,
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${cfg.apiKey}`,
    },
    body: JSON.stringify(body),
  });
  const raw = await res.text();
  if (!res.ok) {
    throw new Error(`vision API ${res.status}: ${raw.slice(0, 500)}`);
  }
  const data = JSON.parse(raw);
  return data.choices?.[0]?.message?.content || '';
}

/** Extract first JSON object/array from LLM text. */
export function parseJsonFromText(text) {
  const trimmed = (text || '').trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    const block = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (block) {
      return JSON.parse(block[1].trim());
    }
    const start = trimmed.search(/[\[{]/);
    const end = Math.max(trimmed.lastIndexOf('}'), trimmed.lastIndexOf(']'));
    if (start >= 0 && end > start) {
      return JSON.parse(trimmed.slice(start, end + 1));
    }
    throw new Error(`cannot parse JSON from model output: ${trimmed.slice(0, 200)}`);
  }
}
