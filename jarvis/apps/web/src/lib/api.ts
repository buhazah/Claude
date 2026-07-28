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

export type Approval = {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  run_id: string | null;
  agent_id: string | null;
  state: "pending" | "approved" | "denied" | "expired";
  reason: string | null;
  requested_at: string;
  decided_at: string | null;
};

export type AuditEntry = {
  id: string;
  at: string;
  topic: string;
  run_id: string | null;
  actor: string;
  approved: boolean;
  payload: Record<string, unknown>;
  hash: string | null;
};

export type KnowledgeDoc = {
  id: string;
  title: string;
  source: string;
  kind: string;
  scope: string;
  chunk_count: number;
  bytes: number;
  created_at: string | null;
};

export type CitationHit = {
  document_id: string;
  document_title: string;
  source: string;
  locator: string;
  snippet: string;
  score: number;
  reference: string;
  signals: { lexical: number; semantic: number; recency: number };
};

export type IngestResult = {
  ingested: { id: string; title: string; kind: string; chunks: number; source: string }[];
  chunks: number;
  skipped: Record<string, string>;
  unchanged: string[];
};

export type WorkflowStep = {
  id: string;
  kind: "agent" | "tool" | "approval" | "branch" | "parallel" | "wait" | "note";
  label: string;
  agent?: string | null;
  tool?: string | null;
  if_true?: string | null;
  if_false?: string | null;
  steps: string[];
};

export type WorkflowDef = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  inputs: string[];
  steps: WorkflowStep[];
};

export type WorkflowRunSummary = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  state: "pending" | "running" | "awaiting_approval" | "succeeded" | "failed" | "cancelled";
  trigger: string;
  steps: number;
  cost_usd: number;
  created_at: string | null;
  error: string | null;
};

export type WorkflowTrigger = {
  id: string;
  workflow_id: string;
  kind: "manual" | "schedule" | "event";
  enabled: boolean;
  interval_seconds: number;
  topic: string;
  last_fired_at: string | null;
};

export type VoiceEvent = {
  type:
    | "state" | "partial" | "transcript" | "token" | "speech"
    | "interrupted" | "wake" | "done" | "error";
  text?: string;
  state?: string;
  truncated?: boolean;
};

export type ComputerStep = {
  action: { id: string; kind: string; ref: string; text: string; url: string };
  verdict: "allow" | "approve" | "refuse";
  description: string;
  reason: string;
  ok: boolean;
  detail: string;
  url: string;
  has_screenshot: boolean;
};

export type ComputerElement = {
  ref: string;
  role: string;
  name: string;
  value: string;
  enabled: boolean;
  secret: boolean;
};

export type ComputerStatus = {
  driver: string;
  available: boolean;
  policy: { allowed_hosts: string[]; blocked_hosts: string[] };
  budget: { steps: number; max_steps: number; max_seconds: number };
  page: { url: string; title: string; text: string; has_screenshot: boolean; elements: ComputerElement[] };
  steps: ComputerStep[];
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
  computer: () => get<ComputerStatus>("/v1/computer"),
  runs: (limit = 25) => get<Run[]>(`/v1/runs?limit=${limit}`),

  approvals: (pendingOnly = false) =>
    get<Approval[]>(`/v1/approvals?pending_only=${pendingOnly}`),

  /** Approve or deny a suspended tool call, releasing the waiting run. */
  decide: (id: string, approved: boolean, reason?: string) =>
    get<Approval>(`/v1/approvals/${id}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ approved, reason: reason ?? null }),
    }),

  workflows: () => get<WorkflowDef[]>("/v1/workflows"),

  workflowRuns: (limit = 25) => get<WorkflowRunSummary[]>(`/v1/workflow-runs?limit=${limit}`),

  runWorkflow: (id: string, inputs: Record<string, string> = {}) =>
    get<{ id: string; state: string }>(`/v1/workflows/${id}/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ inputs }),
    }),

  triggers: () => get<WorkflowTrigger[]>("/v1/triggers"),

  documents: (limit = 100) => get<KnowledgeDoc[]>(`/v1/knowledge?limit=${limit}`),

  searchKnowledge: (query: string, limit = 6) =>
    get<CitationHit[]>(`/v1/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  ingest: (body: { url?: string; path?: string; text?: string; title?: string }) =>
    get<IngestResult>("/v1/knowledge", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),

  forgetDocument: (id: string) =>
    fetch(`${API_BASE}/v1/knowledge/${id}`, { method: "DELETE" }).then((r) => r.ok),

  audit: (limit = 50) =>
    get<{ intact: boolean; broken_at: string | null; entries: AuditEntry[] }>(
      `/v1/audit?limit=${limit}`,
    ),

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
  | { type: "tool"; name?: string; arguments?: Record<string, unknown> }
  | { type: "tool_result"; name?: string; ok?: boolean; result?: string }
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

/**
 * Open a duplex voice session.
 *
 * A WebSocket rather than SSE, because voice is the one interaction where the
 * user talks *while* Jarvis does — barge-in needs speech going up at the same
 * moment audio comes down.
 */
export function openVoiceSocket(
  onEvent: (event: VoiceEvent) => void,
  onClose?: () => void,
): {
  say: (text: string, final?: boolean) => void;
  interrupt: () => void;
  close: () => void;
} {
  const url = API_BASE.replace(/^http/, "ws") + "/v1/voice";
  const socket = new WebSocket(url);
  const queued: string[] = [];

  const send = (payload: object) => {
    const body = JSON.stringify(payload);
    if (socket.readyState === WebSocket.OPEN) socket.send(body);
    else queued.push(body);
  };

  socket.onopen = () => {
    for (const body of queued.splice(0)) socket.send(body);
  };
  socket.onmessage = (raw) => {
    try {
      onEvent(JSON.parse(raw.data));
    } catch {
      /* a malformed frame must not tear down the session */
    }
  };
  socket.onclose = () => onClose?.();

  return {
    say: (text, final = true) => send({ type: "transcript", text, final }),
    interrupt: () => send({ type: "interrupt" }),
    close: () => {
      send({ type: "end" });
      socket.close();
    },
  };
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
  "knowledge.ingested",
  "workflow.started",
  "workflow.suspended",
  "workflow.finished",
  "knowledge.removed",
  "memory.recalled",
  "tool.called",
  "approval.requested",
  "approval.approved",
  "approval.denied",
  "approval.expired",
  "tool.succeeded",
  "tool.failed",
  "routing.decided",
  "routing.arbitrated",
  "system.started",
  "computer.started",
  "computer.acted",
  "computer.stopped",
  "voice.state",
  "voice.wake",
  "voice.interrupted",
] as const;
