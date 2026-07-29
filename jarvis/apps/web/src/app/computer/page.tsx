"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Ban, Check, ShieldAlert } from "lucide-react";
import { API_BASE, api, type ComputerStatus } from "@/lib/api";
import { Card, Chip, EmptyState, ErrorState, PageHeader, SectionLabel, Skeleton } from "@/components/ui";

/**
 * What the browser is doing, and what it is allowed to do.
 *
 * The page is built around the same idea as the wall itself: an action you
 * cannot read is an action you cannot supervise. So every step is shown as the
 * sentence a human would have been asked to approve, with its verdict — not as
 * a coordinate or a selector.
 */

const VERDICT = {
  allow: { tone: "neutral", icon: Check, label: "ran" },
  approve: { tone: "warning", icon: ShieldAlert, label: "asked first" },
  refuse: { tone: "danger", icon: Ban, label: "refused" },
} as const;

export default function ComputerPage() {
  const [status, setStatus] = useState<ComputerStatus | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api
        .computer()
        .then((next) => {
          if (cancelled) return;
          setStatus(next);
          setError(false);
        })
        .catch(() => !cancelled && setError(true));

    load();
    // A browsing session moves without anyone asking it to, so this is one of
    // the few surfaces that polls rather than waiting to be reloaded.
    const timer = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [reloadKey]);

  const reload = () => setReloadKey((key) => key + 1);

  if (error) {
    return (
      <div className="mx-auto max-w-[960px] px-10 py-12">
        <ErrorState message="Could not load the browser session." onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[960px] px-10 py-12">
      <PageHeader
        title="Computer"
        subtitle="What Jarvis is looking at, everything it has done, and the wall around it."
      />

      {status === null ? (
        <Skeleton className="h-[220px] w-full" />
      ) : (
        <>
          <Card className="mb-6">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={status.available ? "positive" : "neutral"}>
                {status.available ? `driver: ${status.driver}` : "no browser configured"}
              </Chip>
              <Chip tone="neutral">
                {status.budget.steps} / {status.budget.max_steps} steps
              </Chip>
              {status.policy.allowed_hosts.length === 0 ? (
                <Chip tone="warning">every site needs approval</Chip>
              ) : (
                status.policy.allowed_hosts.map((host) => (
                  <Chip key={host} tone="positive">
                    {host}
                  </Chip>
                ))
              )}
              {status.policy.blocked_hosts.map((host) => (
                <Chip key={host} tone="danger">
                  {host} blocked
                </Chip>
              ))}
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-3">
              Jarvis never types into password or payment fields — that is a refusal, not
              an approval you can click through. Clicks that commit something, and visits
              to sites outside the list above, are put to you first.
            </p>
          </Card>

          {status.page.has_screenshot && (
            <>
              <SectionLabel>On screen</SectionLabel>
              <Card className="mb-6 overflow-hidden">
                <p className="mb-3 truncate text-[13px] text-ink-3">
                  {status.page.title || "Untitled"} — {status.page.url}
                </p>
                {/* Cache-busted by step count: the URL is stable but the image is not.
                    next/image is the wrong tool here — this is a live PNG from the
                    kernel's own origin that changes every step, so optimising and
                    caching it is exactly what must not happen. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${API_BASE}/v1/computer/screen?v=${status.budget.steps}`}
                  alt="Current browser screen"
                  className="w-full rounded-control border border-hairline"
                />
              </Card>
            </>
          )}

          {status.page.elements.length > 0 && (
            <>
              <SectionLabel>What it can act on</SectionLabel>
              <Card className="mb-6">
                <div className="flex flex-col gap-1.5">
                  {status.page.elements.slice(0, 20).map((element) => (
                    <div key={element.ref} className="flex items-center gap-2 text-[13px]">
                      <span className="font-mono text-[11px] text-ink-3">{element.ref}</span>
                      <span className="text-ink-3">{element.role}</span>
                      <span className="truncate text-ink-2">{element.name || "—"}</span>
                      {element.secret && <Chip tone="danger">never filled by Jarvis</Chip>}
                      {!element.enabled && <Chip tone="neutral">disabled</Chip>}
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          <SectionLabel>Everything it has done</SectionLabel>
          {status.steps.length === 0 ? (
            <EmptyState title="Nothing yet. Ask Jarvis to look something up." />
          ) : (
            <div className="flex flex-col gap-1.5">
              {[...status.steps].reverse().map((step) => {
                const verdict = VERDICT[step.verdict];
                const Icon = verdict.icon;
                return (
                  <motion.div
                    key={step.action.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <Card>
                      <div className="flex items-start gap-2.5">
                        <Icon size={15} className="mt-0.5 shrink-0 text-ink-3" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[13.5px] text-ink">{step.description}</p>
                          {step.reason && (
                            <p className="mt-0.5 text-[12.5px] text-ink-3">{step.reason}</p>
                          )}
                        </div>
                        <Chip tone={verdict.tone}>{verdict.label}</Chip>
                      </div>
                    </Card>
                  </motion.div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
