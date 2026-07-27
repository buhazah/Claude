"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Tool } from "@/lib/api";
import { Chip, ErrorState, PageHeader, Skeleton } from "@/components/ui";

const PERMISSION_TONE: Record<Tool["permission"], string> = {
  safe: "positive",
  sensitive: "warning",
  dangerous: "danger",
};

const PERMISSION_NOTE: Record<Tool["permission"], string> = {
  safe: "Runs freely. Read-only, reversible, no outside effects.",
  sensitive: "Runs, and is audit-logged. Touches real data or costs money.",
  dangerous: "Needs your explicit approval. Irreversible or outward-facing.",
};

export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [error, setError] = useState(false);

  const [reloadKey, setReloadKey] = useState(0);

  // State is only ever set from the async callbacks: setting it synchronously
  // in the effect body would cascade an extra render on every mount.
  useEffect(() => {
    let cancelled = false;
    api.tools()
      .then((tools) => {
        if (cancelled) return;
        setTools(tools);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = () => setReloadKey((key) => key + 1);

  const tiers: Tool["permission"][] = ["safe", "sensitive", "dangerous"];

  return (
    <div className="mx-auto max-w-[860px] px-10 py-12">
      <PageHeader
        title="Tools"
        subtitle="What Jarvis can reach, grouped by how much damage it could do."
      />

      {error ? (
        <ErrorState message="Could not load tools." onRetry={reload} />
      ) : tools === null ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-[64px] w-full" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {tiers.map((tier) => {
            const inTier = tools.filter((tool) => tool.permission === tier);
            if (inTier.length === 0) return null;
            return (
              <section key={tier}>
                <div className="mb-1 flex items-center gap-2">
                  <Chip tone={PERMISSION_TONE[tier]}>{tier}</Chip>
                  <span className="text-[12px] text-ink-3">{PERMISSION_NOTE[tier]}</span>
                </div>
                <div className="mt-3 flex flex-col gap-1.5">
                  {inTier.map((tool, index) => (
                    <motion.div
                      key={tool.name}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.02 }}
                      className="card flex items-center gap-3 px-4 py-3"
                    >
                      <span className="font-mono text-[12.5px]">{tool.name}</span>
                      <span className="flex-1 truncate text-[12.5px] text-ink-3">
                        {tool.description}
                      </span>
                      <Chip>{tool.namespace}</Chip>
                    </motion.div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
