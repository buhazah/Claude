"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Run } from "@/lib/api";
import { Chip, ErrorState, PageHeader, Skeleton } from "@/components/ui";

const STATE_TONE: Record<Run["state"], string> = {
  succeeded: "positive",
  failed: "danger",
  running: "accent",
  pending: "neutral",
  cancelled: "neutral",
  awaiting_approval: "warning",
};

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState(false);

  const [reloadKey, setReloadKey] = useState(0);

  // State is only ever set from the async callbacks: setting it synchronously
  // in the effect body would cascade an extra render on every mount.
  useEffect(() => {
    let cancelled = false;
    api.runs(50)
      .then((runs) => {
        if (cancelled) return;
        setRuns(runs);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = () => setReloadKey((key) => key + 1);

  return (
    <div className="mx-auto max-w-[900px] px-10 py-12">
      <PageHeader
        title="Runs"
        subtitle="Every unit of work Jarvis has executed, with its cost and timing."
      />

      {error ? (
        <ErrorState message="Could not load runs." onRetry={reload} />
      ) : runs === null ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4].map((index) => (
            <Skeleton key={index} className="h-[56px] w-full" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="card px-5 py-10 text-center text-[13px] text-ink-3">
          No runs yet. Press ⌘K to start one.
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {runs.map((run, index) => (
            <motion.div
              key={run.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.015, 0.2) }}
              className="card flex items-center gap-3 px-4 py-3"
            >
              <Chip tone={STATE_TONE[run.state]}>{run.state}</Chip>
              <span className="flex-1 truncate text-[13.5px]">{run.request}</span>
              <Chip>{run.agent_id.replace(/_/g, " ")}</Chip>
              <span className="w-24 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
                {run.steps} steps · {run.tokens} tok
              </span>
              <span className="w-14 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
                {Math.round(run.duration_ms)}ms
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
