/**
 * Typed client for the Jarvis API.
 *
 * Every network call in the app goes through here, so retries, error shape and
 * base-url resolution have exactly one home.
 */

import { readSSE } from "./sse";

export const API_BASE =
  process.env.NEXT_PUBLIC_JARVIS_API ?? "http://localhost:8000";

export type Health = {
  status: string;
  environment: string;
  providers: string[];
  models: number;
  agents: number;
  tools: number;
  memories: number;
  events_published: number;
};

export type Agent = {
  id: string;
  name: string;
  tagline: string;
  responsibilities: string[];
  capabilities: string[];
  tools: string[];
  policy: string;
  runs: number;
  success_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_cost_usd: number;
};

export type AgentMatch = {
  agent_id: string;
  confidence: number;
  reasons: string[];
};

export type Model = {
  id: string;
  provider: string;
  context_window: number;
  quality: number;
  latency_score: number;
  input_cost_per_mtok: number;
  output_cost_per_mtok: number;
  privacy: string;
};

export type Run = {
  id: string;
  request: string;
  agent_id: string;
  state: "pending" | "running" | "succeeded" | "failed" | "cancelled" | "awaiting_approval";
  steps: number;
  cost_usd: number;
  tokens: number;
  duration_ms: number;
  created_at: string | null;
};

export type Memory = {
  id: string;
  content: string;
  kind: string;
  tier: string;
  scope: string;
  tags: string[];
  salience: number;
  created_at: string | null;
  access_count: number;
  score?: number;
  signals?: { lexical: number; semantic: number; recency: number };
};

export type Tool = {
  name: string;
  namespace: string;
  description: string;
  permission: "safe" | "sensitive" | "dangerous";
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new ApiError(`${path} failed`, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => get<Health>("/health"),
  agents: () => get<Agent[]>("/v1/agents"),
  models: () => get<Model[]>("/v1/models"),
  tools: () => get<Tool[]>("/v1/tools"),
  runs: (limit = 25) => get<Run[]>(`/v1/runs?limit=${limit}`),

  memories: (query = "", limit = 30) =>
    get<Memory[]>(`/v1/memory?q=${encodeURIComponent(query)}&limit=${limit}`),

  remember: (content: string) =>
    get<Memory>("/v1/memory", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content }),
    }),

  /** Preview the routing decision without executing — powers the palette. */
  route: (message: string) =>
    get<{ candidates: AgentMatch[] }>("/v1/route", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    }),
};

export type ChatEvent =
  | { type: "routing"; run_id: string; chosen: string; candidates: AgentMatch[] }
  | { type: "context"; memories: number }
  | { type: "token"; text: string }
  | { type: "tool"; name?: string }
  | { type: "done"; run_id: string; agent: string; cost_usd: number; tokens: number; latency_ms: number }
  | { type: "error"; message: string };

/** Stream a chat turn. Abort via `signal` to interrupt mid-answer. */
export async function* streamChat(
  message: string,
  options: { agentId?: string; signal?: AbortSignal } = {},
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_BASE}/v1/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, agent_id: options.agentId ?? null }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new ApiError(`chat failed (${response.status})`, response.status);
  }

  for await (const frame of readSSE(response)) {
    const payload = (frame.data ?? {}) as Record<string, unknown>;
    yield { type: frame.event, ...payload } as ChatEvent;
  }
}

export type KernelEvent = {
  topic: string;
  payload: Record<string, unknown>;
  timestamp: string;
  id: string;
};

/** Subscribe to the kernel's event firehose. Returns an unsubscribe function. */
export function subscribeToEvents(
  topics: string,
  onEvent: (event: KernelEvent) => void,
  onStatus?: (connected: boolean) => void,
): () => void {
  const source = new EventSource(
    `${API_BASE}/v1/events?topics=${encodeURIComponent(topics)}`,
  );

  // Connection state is the transport's, not "have we seen traffic" — an idle
  // system is still connected, and the indicator must say so.
  source.onopen = () => onStatus?.(true);
  source.onerror = () => onStatus?.(false);

  // The server names each frame after its topic, so there is no single event
  // name to listen for. `onmessage` never fires for named events — listen for
  // the ones we care about explicitly.
  const handler = (raw: MessageEvent) => {
    try {
      onEvent(JSON.parse(raw.data));
    } catch {
      /* a malformed frame must not tear down the feed */
    }
  };

  for (const topic of TRACKED_TOPICS) {
    source.addEventListener(topic, handler as EventListener);
  }

  return () => source.close();
}

/** Topics the activity rail renders. Named explicitly because SSE requires it. */
export const TRACKED_TOPICS = [
  "agent.started",
  "agent.completed",
  "agent.failed",
  "llm.selected",
  "llm.completed",
  "llm.failed",
  "memory.written",
  "memory.recalled",
  "tool.called",
  "tool.succeeded",
  "tool.failed",
  "routing.decided",
  "routing.arbitrated",
  "system.started",
] as const;
