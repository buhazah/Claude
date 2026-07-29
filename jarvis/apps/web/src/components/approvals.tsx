"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ShieldAlert, X } from "lucide-react";
import { api, subscribeToEvents, type Approval } from "@/lib/api";

/**
 * The approval gate, surfaced globally.
 *
 * A suspended run is blocking on a person, so this cannot live on a page the
 * person might not be looking at. It floats above everything, arrives via the
 * kernel's own event stream (not polling), and states the exact call being
 * authorised — approving "run_command" means nothing; approving
 * `rm -rf build/` means something.
 */
export function ApprovalGate() {
  const [pending, setPending] = useState<Approval[]>([]);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // Two effects, deliberately. The subscription is set up once; refetching is
  // keyed off a counter it bumps. Combining them would either re-subscribe on
  // every event or set state synchronously in an effect body.
  useEffect(
    () =>
      // Approvals ride the same firehose as everything else, so the banner
      // appears the instant a run parks rather than a poll interval later.
      subscribeToEvents("approval.**", () => setTick((current) => current + 1)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .approvals(true)
      .then((approvals) => !cancelled && setPending(approvals))
      .catch(() => {
        /* the gate is additive; a fetch failure must not break the page */
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const decide = useCallback(
    async (approval: Approval, approved: boolean) => {
      setDeciding(approval.id);
      try {
        await api.decide(approval.id, approved);
        setPending((current) => current.filter((a) => a.id !== approval.id));
      } finally {
        setDeciding(null);
      }
    },
    [],
  );

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[60] flex flex-col items-center gap-2">
      <AnimatePresence initial={false}>
        {pending.map((approval) => (
          <motion.div
            key={approval.id}
            initial={{ opacity: 0, y: -16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className="glass pointer-events-auto w-[min(620px,92vw)] rounded-float px-5 py-4"
            role="alertdialog"
            aria-label={`Approve ${approval.tool}`}
          >
            <div className="flex items-start gap-3">
              <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warning" />

              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-[14px] font-medium">Approval needed</span>
                  <span className="font-mono text-[11px] text-ink-3">{approval.tool}</span>
                  {approval.agent_id && (
                    <span className="text-[11.5px] text-ink-3">
                      · {approval.agent_id.replace(/_/g, " ")}
                    </span>
                  )}
                </div>

                {/* The exact call, not just its name. */}
                <pre className="mt-2 max-h-32 overflow-auto rounded-control bg-black/30 px-3 py-2 font-mono text-[11.5px] leading-relaxed text-ink-2">
                  {JSON.stringify(approval.arguments, null, 2)}
                </pre>
              </div>

              <div className="flex shrink-0 gap-1.5">
                <button
                  onClick={() => void decide(approval, false)}
                  disabled={deciding === approval.id}
                  aria-label="Deny"
                  className="grid h-8 w-8 place-items-center rounded-control border border-hairline text-ink-3 transition-colors hover:border-danger/50 hover:text-danger disabled:opacity-40"
                >
                  <X size={14} />
                </button>
                <button
                  onClick={() => void decide(approval, true)}
                  disabled={deciding === approval.id}
                  aria-label="Approve"
                  className="grid h-8 w-8 place-items-center rounded-control bg-positive/15 text-positive transition-colors hover:bg-positive/25 disabled:opacity-40"
                >
                  <Check size={14} />
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
