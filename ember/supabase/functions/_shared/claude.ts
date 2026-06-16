// Server-side Claude API helper. Never imported by client code.
// Verify current model names/pricing at https://docs.claude.com/en/api/overview
// before launch (PRD §6, OQ-08). Model is configurable via env to avoid hardcoding.
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;
export const CLAUDE_MODEL = Deno.env.get("CLAUDE_MODEL") ?? "claude-sonnet-4-6";

export async function claude(
  system: string,
  user: string,
  maxTokens = 1024,
): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: maxTokens,
      system,
      messages: [{ role: "user", content: user }],
    }),
  });
  if (!res.ok) throw new Error(`Claude API ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.content[0].text as string;
}

export function claudeJSON<T>(text: string): T {
  // Strip accidental markdown fences before parsing
  const cleaned = text.replace(/^```(?:json)?\s*|\s*```$/g, "").trim();
  return JSON.parse(cleaned) as T;
}
