"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, Circle, Cpu, Zap } from "lucide-react";
import { api, type Agent, type Health, type Run } from "@/lib/api";
import { Card, Chip, SectionLabel, Skeleton } from "@/components/ui";

function greeting(hour: number) {
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [offline, setOffline] = useState(false);
  // The clock is client-only state: rendering it on the server would produce a
  // hydration mismatch the moment the two disagree. useSyncExternalStore gives
  // the server a null snapshot and the client the real hour.
  const hour = useSyncExternalStore(
    () => () => {},
    () => new Date().getHours(),
    () => null,
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.health(), api.runs(6), api.agents()])
      .then(([health, runs, agents]) => {
        if (cancelled) return;
        setHealth(health);
        setRuns(runs);
        setAgents(agents);
      })
      .catch(() => !cancelled && setOffline(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const active = agents?.filter((agent) => agent.runs > 0) ?? [];
  const totalCost = active.reduce((sum, agent) => sum + agent.total_cost_usd, 0);

  return (
    <div className="mx-auto max-w-[980px] px-10 py-12">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 30 }}
        className="mb-10"
      >
        <h1 className="text-[30px] font-semibold">
          {hour === null ? "Hello" : greeting(hour)}.
        </h1>
        <p className="mt-1.5 text-[14px] text-ink-3">
          {offline
            ? "The kernel is not reachable. Start the API to bring Jarvis online."
            : "Press ⌘K and tell me what to handle."}
        </p>
      </motion.header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card delay={0.02}>
          <SectionLabel>System</SectionLabel>
          {health ? (
            <>
              <div className="flex items-baseline gap-2">
                <Circle
                  size={8}
                  className="fill-positive text-positive"
                  style={{ opacity: 0.9 }}
                />
                <span className="text-[15px]">Online</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {health.providers.map((provider) => (
                  <Chip key={provider} tone="accent">
                    {provider}
                  </Chip>
                ))}
              </div>
              <p className="mt-3 text-[12.5px] text-ink-3">
                {health.agents} agents · {health.models} models · {health.tools} tools
              </p>
            </>
          ) : offline ? (
            <p className="text-[13px] text-ink-3">Offline</p>
          ) : (
            <Skeleton className="h-16 w-full" />
          )}
        </Card>

        <Card delay={0.05}>
          <SectionLabel>Memory</SectionLabel>
          <div className="text-[28px] font-semibold tabular-nums">
            {health?.memories ?? (offline ? "—" : "·")}
          </div>
          <p className="mt-1 text-[12.5px] text-ink-3">
            memories stored, searchable in natural language
          </p>
          <Link
            href="/memory"
            className="mt-3 inline-flex items-center gap-1 text-[12.5px] text-accent transition-opacity hover:opacity-80"
          >
            Browse <ArrowUpRight size={12} />
          </Link>
        </Card>

        <Card delay={0.08}>
          <SectionLabel>Spend</SectionLabel>
          <div className="text-[28px] font-semibold tabular-nums">
            ${totalCost.toFixed(4)}
          </div>
          <p className="mt-1 text-[12.5px] text-ink-3">
            across {active.length} active {active.length === 1 ? "agent" : "agents"}
          </p>
        </Card>
      </div>

      <section className="mt-10">
        <div className="mb-3 flex items-baseline justify-between">
          <SectionLabel>Recent runs</SectionLabel>
          <Link href="/runs" className="text-[12px] text-ink-3 transition-colors hover:text-ink-2">
            All runs
          </Link>
        </div>

        {runs === null ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-[52px] w-full" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="card px-5 py-8 text-center text-[13px] text-ink-3">
            Nothing yet. Press ⌘K to give Jarvis its first task.
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {runs.map((run, index) => (
              <motion.div
                key={run.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.03 * index }}
                className="card flex items-center gap-3 px-4 py-3"
              >
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{
                    background:
                      run.state === "succeeded"
                        ? "var(--color-positive)"
                        : run.state === "failed"
                          ? "var(--color-danger)"
                          : "var(--color-accent)",
                  }}
                />
                <span className="flex-1 truncate text-[13.5px]">{run.request}</span>
                <Chip>{run.agent_id.replace(/_/g, " ")}</Chip>
                <span className="w-16 shrink-0 text-right font-mono text-[11px] text-ink-3">
                  {Math.round(run.duration_ms)}ms
                </span>
              </motion.div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card delay={0.02}>
          <SectionLabel>Quick actions</SectionLabel>
          <div className="flex flex-col gap-1">
            {[
              "Summarise my inbox and draft replies",
              "Research my top three competitors",
              "Plan this week around my goals",
            ].map((action) => (
              <Link
                key={action}
                href={`/chat?q=${encodeURIComponent(action)}`}
                className="flex items-center gap-2 rounded-control px-2 py-2 text-[13px] text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
              >
                <Zap size={13} className="shrink-0 text-accent" />
                {action}
              </Link>
            ))}
          </div>
        </Card>

        <Card delay={0.05}>
          <SectionLabel>Busiest agents</SectionLabel>
          {active.length === 0 ? (
            <p className="text-[13px] text-ink-3">
              No agent has run yet. Their performance appears here as they work.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {active
                .sort((a, b) => b.runs - a.runs)
                .slice(0, 4)
                .map((agent) => (
                  <div key={agent.id} className="flex items-center gap-2.5 text-[13px]">
                    <Cpu size={13} className="shrink-0 text-ink-3" />
                    <span className="flex-1 truncate">{agent.name}</span>
                    <span className="font-mono text-[11px] text-ink-3">
                      {agent.runs} · {Math.round(agent.p95_latency_ms)}ms p95
                    </span>
                  </div>
                ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
