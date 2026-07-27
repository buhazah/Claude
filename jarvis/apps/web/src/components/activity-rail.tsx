"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { subscribeToEvents } from "@/lib/api";

type Entry = {
  id: string;
  topic: string;
  label: string;
  detail: string;
  tone: "neutral" | "accent" | "positive" | "danger";
  at: string;
};

const MAX_ENTRIES = 40;

/** Render one kernel event as a line a human can read at a glance. */
function describe(topic: string, payload: Record<string, unknown>): Omit<Entry, "id" | "at" | "topic"> {
  const agent = String(payload.agent ?? "");
  switch (topic) {
    case "routing.decided":
    case "routing.arbitrated":
      return { label: "routed", detail: String(payload.chosen ?? ""), tone: "neutral" };
    case "agent.started":
      return { label: agent.replace(/_/g, " "), detail: "started", tone: "accent" };
    case "agent.completed":
      return {
        label: agent.replace(/_/g, " "),
        detail: `${Math.round(Number(payload.latency_ms ?? 0))}ms · ${payload.tokens ?? 0} tok`,
        tone: "positive",
      };
    case "agent.failed":
      return { label: agent.replace(/_/g, " "), detail: "failed", tone: "danger" };
    case "llm.selected":
      return { label: "model", detail: String(payload.model ?? ""), tone: "neutral" };
    case "llm.completed":
      return {
        label: "tokens",
        detail: `${payload.output_tokens ?? 0} out · $${Number(payload.cost_usd ?? 0).toFixed(4)}`,
        tone: "neutral",
      };
    case "llm.failed":
      return { label: "model failed", detail: String(payload.provider ?? ""), tone: "danger" };
    case "memory.written":
      return { label: "remembered", detail: String(payload.kind ?? ""), tone: "positive" };
    case "memory.recalled":
      return { label: "recalled", detail: `${payload.hits ?? 0} memories`, tone: "neutral" };
    case "tool.called":
      return { label: "tool", detail: String(payload.tool ?? ""), tone: "accent" };
    case "tool.failed":
      return { label: "tool failed", detail: String(payload.tool ?? ""), tone: "danger" };
    default:
      return { label: topic, detail: "", tone: "neutral" };
  }
}

const TONE: Record<Entry["tone"], string> = {
  neutral: "var(--color-ink-3)",
  accent: "var(--color-accent)",
  positive: "var(--color-positive)",
  danger: "var(--color-danger)",
};

/**
 * Live activity.
 *
 * Nothing here is bespoke instrumentation — it is the kernel's event bus,
 * rendered. Anything the system does shows up because it was published.
 */
export function ActivityRail() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    return subscribeToEvents(
      "**",
      (event) => {
        const described = describe(event.topic, event.payload ?? {});
        setEntries((current) =>
          [
            { id: event.id, topic: event.topic, at: event.timestamp, ...described },
            ...current,
          ].slice(0, MAX_ENTRIES),
        );
      },
      setConnected,
    );
  }, []);

  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-l border-hairline px-4 py-5 xl:flex">
      <div className="mb-4 flex items-center gap-2">
        <span
          className={`h-1.5 w-1.5 rounded-full ${connected ? "live-dot" : ""}`}
          style={{ background: connected ? "var(--color-positive)" : "var(--color-ink-3)" }}
        />
        <span className="text-[10.5px] font-medium uppercase tracking-[0.09em] text-ink-3">
          Live activity
        </span>
      </div>

      {entries.length === 0 ? (
        <p className="text-[12.5px] leading-relaxed text-ink-3">
          {connected
            ? "Quiet. Everything Jarvis does will appear here as it happens."
            : "Waiting for the kernel event stream."}
        </p>
      ) : (
        <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
          <AnimatePresence initial={false}>
            {entries.map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ type: "spring", stiffness: 320, damping: 30 }}
                className="flex items-baseline gap-2 text-[12px]"
              >
                <span
                  className="mt-[5px] h-1 w-1 shrink-0 rounded-full"
                  style={{ background: TONE[entry.tone] }}
                />
                <span className="shrink-0" style={{ color: TONE[entry.tone] }}>
                  {entry.label}
                </span>
                <span className="truncate font-mono text-[11px] text-ink-3">{entry.detail}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </aside>
  );
}
