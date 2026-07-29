"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CircleDot, GitBranch, Play, ShieldQuestion, Split, Wrench } from "lucide-react";
import {
  api,
  type WorkflowDef,
  type WorkflowRunSummary,
  type WorkflowStep,
  type WorkflowTrigger,
} from "@/lib/api";
import { Chip, ErrorState, PageHeader, SectionLabel, Skeleton } from "@/components/ui";

const STEP_ICON: Record<WorkflowStep["kind"], typeof CircleDot> = {
  agent: CircleDot,
  tool: Wrench,
  approval: ShieldQuestion,
  branch: Split,
  parallel: GitBranch,
  wait: CircleDot,
  note: CircleDot,
};

const RUN_TONE: Record<WorkflowRunSummary["state"], string> = {
  succeeded: "positive",
  failed: "danger",
  cancelled: "neutral",
  running: "accent",
  pending: "neutral",
  awaiting_approval: "warning",
};

/**
 * Workflows.
 *
 * The graph is rendered as a readable sequence rather than a node canvas: at
 * this size a list you can scan beats a diagram you have to arrange, and it
 * makes the two things that matter obvious — which steps pause for a human,
 * and where a branch goes.
 */
export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowDef[] | null>(null);
  const [runs, setRuns] = useState<WorkflowRunSummary[]>([]);
  const [triggers, setTriggers] = useState<WorkflowTrigger[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.workflows(), api.workflowRuns(), api.triggers()])
      .then(([definitions, recent, configured]) => {
        if (cancelled) return;
        setWorkflows(definitions);
        setRuns(recent);
        setTriggers(configured);
        setError(false);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const run = async (workflow: WorkflowDef) => {
    setStarting(workflow.id);
    try {
      // Inputs are left empty here: a workflow that needs them says so in its
      // step prompts, and the run records which paths went unresolved.
      await api.runWorkflow(workflow.id);
      setReloadKey((key) => key + 1);
    } finally {
      setStarting(null);
    }
  };

  return (
    <div className="mx-auto max-w-[980px] px-10 py-12">
      <PageHeader
        title="Workflows"
        subtitle="Work that runs without being asked. Steps that need a decision wait for you rather than guessing."
      />

      {error ? (
        <ErrorState
          message="Could not load workflows."
          onRetry={() => setReloadKey((key) => key + 1)}
        />
      ) : workflows === null ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-[92px] w-full" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {workflows.map((workflow, index) => {
            const bound = triggers.filter((t) => t.workflow_id === workflow.id);
            const open = expanded === workflow.id;

            return (
              <motion.div
                key={workflow.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.03, 0.2) }}
                className="card p-5"
              >
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <button
                        onClick={() => setExpanded(open ? null : workflow.id)}
                        className="text-[15px] font-medium transition-colors hover:text-accent"
                      >
                        {workflow.name}
                      </button>
                      {!workflow.enabled && <Chip>disabled</Chip>}
                      {bound.map((trigger) => (
                        <Chip key={trigger.id} tone="accent">
                          {trigger.kind === "schedule"
                            ? `every ${Math.round(trigger.interval_seconds / 60)}m`
                            : trigger.topic}
                        </Chip>
                      ))}
                    </div>
                    <p className="mt-1 text-[13px] text-ink-2">{workflow.description}</p>
                  </div>

                  <button
                    onClick={() => void run(workflow)}
                    disabled={starting === workflow.id}
                    className="flex shrink-0 items-center gap-1.5 rounded-control bg-accent/15 px-3 py-1.5 text-[12.5px] text-accent transition-colors hover:bg-accent/25 disabled:opacity-40"
                  >
                    <Play size={12} />
                    {starting === workflow.id ? "Running…" : "Run"}
                  </button>
                </div>

                {open && (
                  <div className="mt-4 flex flex-col gap-1.5 border-t border-hairline pt-4">
                    {workflow.steps.map((step) => {
                      const Icon = STEP_ICON[step.kind];
                      return (
                        <div key={step.id} className="flex items-center gap-2.5 text-[12.5px]">
                          <Icon
                            size={13}
                            className="shrink-0"
                            style={{
                              color:
                                step.kind === "approval"
                                  ? "var(--color-warning)"
                                  : "var(--color-ink-3)",
                            }}
                          />
                          <span className="font-mono text-[11px] text-ink-3">{step.id}</span>
                          <span className="flex-1 truncate text-ink-2">
                            {step.label || step.agent || step.tool}
                          </span>
                          {step.kind === "branch" && (
                            <span className="font-mono text-[10.5px] text-ink-3">
                              → {step.if_true} / {step.if_false}
                            </span>
                          )}
                          {step.kind === "parallel" && (
                            <span className="font-mono text-[10.5px] text-ink-3">
                              ∥ {step.steps.join(", ")}
                            </span>
                          )}
                          <Chip tone={step.kind === "approval" ? "warning" : "neutral"}>
                            {step.kind}
                          </Chip>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}

      <section className="mt-10">
        <SectionLabel>Recent runs</SectionLabel>
        {runs.length === 0 ? (
          <div className="card px-5 py-8 text-center text-[13px] text-ink-3">
            No workflow has run yet.
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {runs.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="card flex items-center gap-3 px-4 py-3"
              >
                <Chip tone={RUN_TONE[item.state]}>{item.state.replace(/_/g, " ")}</Chip>
                <span className="flex-1 truncate text-[13.5px]">{item.workflow_name}</span>
                <Chip>{item.trigger}</Chip>
                <span className="w-20 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
                  {item.steps} steps
                </span>
                <span className="w-16 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
                  ${item.cost_usd.toFixed(4)}
                </span>
              </motion.div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
