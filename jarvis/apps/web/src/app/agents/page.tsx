"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { api, type Agent } from "@/lib/api";
import { Chip, ErrorState, PageHeader, Skeleton } from "@/components/ui";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("");

  const [reloadKey, setReloadKey] = useState(0);

  // State is only ever set from the async callbacks: setting it synchronously
  // in the effect body would cascade an extra render on every mount.
  useEffect(() => {
    let cancelled = false;
    api.agents()
      .then((agents) => {
        if (cancelled) return;
        setAgents(agents);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = () => setReloadKey((key) => key + 1);

  const visible = (agents ?? []).filter((agent) =>
    `${agent.name} ${agent.tagline} ${agent.capabilities.join(" ")}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );

  return (
    <div className="mx-auto max-w-[980px] px-10 py-12">
      <PageHeader
        title="Agents"
        subtitle="Specialists Jarvis routes between. Each one carries its own remit, tools and track record."
      />

      <input
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="Filter agents…"
        className="mb-6 w-full rounded-control border border-hairline bg-surface px-3.5 py-2.5 text-[13.5px] outline-none transition-colors placeholder:text-ink-3 focus:border-accent/40"
      />

      {error ? (
        <ErrorState message="Could not load agents." onRetry={reload} />
      ) : agents === null ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-[132px] w-full" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <p className="text-[13.5px] text-ink-3">No agent matches “{filter}”.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {visible.map((agent, index) => (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.015, 0.25) }}
              className="card flex flex-col p-5"
            >
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-[15px] font-medium">{agent.name}</h2>
                <Chip>{agent.policy}</Chip>
              </div>
              <p className="mt-1 text-[13px] text-ink-2">{agent.tagline}</p>

              <ul className="mt-3 flex flex-col gap-1">
                {agent.responsibilities.slice(0, 3).map((item) => (
                  <li key={item} className="flex gap-2 text-[12.5px] text-ink-3">
                    <span className="mt-[7px] h-[3px] w-[3px] shrink-0 rounded-full bg-ink-3" />
                    {item}
                  </li>
                ))}
              </ul>

              {agent.tools.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {agent.tools.map((tool) => (
                    <Chip key={tool}>{tool}</Chip>
                  ))}
                </div>
              )}

              <div className="mt-4 flex items-center gap-4 border-t border-hairline pt-3 font-mono text-[10.5px] text-ink-3">
                <span>{agent.runs} runs</span>
                <span>{(agent.success_rate * 100).toFixed(0)}% ok</span>
                <span>{Math.round(agent.p95_latency_ms)}ms p95</span>
                <Link
                  href={`/chat?q=${encodeURIComponent(`Ask the ${agent.name.toLowerCase()} to `)}`}
                  className="ml-auto text-accent transition-opacity hover:opacity-80"
                >
                  use →
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
