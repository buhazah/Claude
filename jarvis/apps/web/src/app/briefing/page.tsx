"use client";

/**
 * The morning briefing.
 *
 * The whole page is built around one claim from the backend: the ranking is
 * arithmetic, and the evidence travels with it. So the interface never asks
 * the reader to trust a number — every recommendation shows what produced it,
 * inline, without a click. A score you cannot interrogate is a score you
 * either believe blindly or ignore, and both are worse than a sentence.
 *
 * Two deliberate omissions:
 *
 * **No badge counts in the nav.** A number that goes up is a number that
 * demands attention, and this page exists precisely for things that are
 * important without being urgent. Nagging them daily is how a cold project
 * gets dismissed rather than decided.
 *
 * **Nothing is hidden behind "show more".** A sweep is already capped at ten
 * server-side and says how many it held back. Adding a second layer of
 * truncation on top would mean the page and the engine disagree about what
 * "everything" is.
 */

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Check, EyeOff } from "lucide-react";
import Link from "next/link";
import { api, type Briefing, type Recommendation } from "@/lib/api";
import { Card, EmptyState, ErrorState, PageHeader, SectionLabel, Skeleton } from "@/components/ui";

/** Urgency drives the colour, because urgency is what changes by waiting. */
const URGENCY_TONE: Record<string, string> = {
  blocking: "text-danger border-danger/30 bg-danger/[0.07]",
  today: "text-warning border-warning/30 bg-warning/[0.07]",
  this_week: "text-ink-1 border-hairline bg-surface-2",
  soon: "text-ink-2 border-hairline bg-surface-2",
  whenever: "text-ink-3 border-hairline bg-transparent",
};

function ScoreBar({ score }: { score: number }) {
  // Out of 25 — impact × urgency × confidence, all capped at five.
  const share = Math.min(score / 25, 1);
  return (
    <div className="h-1 w-14 overflow-hidden rounded-full bg-surface-2" aria-hidden>
      <div className="h-full rounded-full bg-accent" style={{ width: `${share * 100}%` }} />
    </div>
  );
}

function RecommendationRow({
  recommendation,
  onDismiss,
}: {
  recommendation: Recommendation;
  onDismiss: (id: string) => void;
}) {
  const tone = URGENCY_TONE[recommendation.urgency_name] ?? URGENCY_TONE.soon;
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="group border-b border-hairline py-4 last:border-0"
    >
      <div className="flex items-start gap-3">
        <div className="flex flex-col items-center gap-1.5 pt-1">
          <ScoreBar score={recommendation.score} />
          <span className="text-[10px] tabular-nums text-ink-3">
            {recommendation.score.toFixed(1)}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13.5px] font-medium text-ink-0">{recommendation.headline}</span>
            <span
              className={`rounded-full border px-1.5 py-px text-[10px] uppercase tracking-wide ${tone}`}
            >
              {recommendation.urgency_name.replace("_", " ")}
            </span>
            {recommendation.confidence < 0.7 && (
              <span
                className="text-[10px] text-ink-3"
                title="How sure the detector is that this is real"
              >
                {Math.round(recommendation.confidence * 100)}% confident
              </span>
            )}
          </div>

          {/* The evidence, always visible. A score you cannot interrogate is
              one you either believe blindly or ignore. */}
          {/* Index keys, deliberately. These are plain strings with no
              identity, and they can legitimately repeat — two runs can record
              the same failure — which produced duplicate React keys and
              silently omitted children until the browser test caught it. */}
          <ul className="mt-1.5 space-y-0.5">
            {recommendation.evidence.map((line, index) => (
              <li key={index} className="text-[12px] leading-relaxed text-ink-2">
                · {line}
              </li>
            ))}
          </ul>

          {recommendation.action && (
            <Link
              href={`/chat?q=${encodeURIComponent(recommendation.action)}&agent=${recommendation.agent}`}
              className="mt-2 inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
            >
              Ask {recommendation.agent}
              <ArrowRight size={12} />
            </Link>
          )}
        </div>

        <button
          type="button"
          onClick={() => onDismiss(recommendation.id)}
          aria-label={`Dismiss: ${recommendation.headline}`}
          title="Not now — returns in a week"
          className="rounded-md p-1.5 text-ink-3 opacity-0 transition hover:bg-surface-2 hover:text-ink-1 focus:opacity-100 group-hover:opacity-100"
        >
          <EyeOff size={14} />
        </button>
      </div>
    </motion.li>
  );
}

export default function BriefingPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [failed, setFailed] = useState(false);
  // A counter rather than a callback: the React compiler forbids a synchronous
  // setState in an effect body, so retrying has to be a dependency change
  // rather than a function the button calls directly.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .briefing()
      .then((next) => !cancelled && setBriefing(next))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setFailed(false);
    setAttempt((n) => n + 1);
  }, []);

  const dismiss = useCallback((id: string) => {
    // Optimistic: the server holds the dismissal for a week, and a failed
    // request means it comes back on the next load rather than being lost.
    setBriefing((current) =>
      current
        ? { ...current, recommendations: current.recommendations.filter((r) => r.id !== id) }
        : current,
    );
    void api.dismiss(id);
  }, []);

  if (failed) {
    return (
      <div className="mx-auto max-w-[820px] px-10 py-12">
        <ErrorState message="The briefing could not be assembled." onRetry={retry} />
      </div>
    );
  }

  if (!briefing) {
    return (
      <div className="mx-auto max-w-[820px] space-y-4 px-10 py-12">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-44 w-full" />
      </div>
    );
  }

  const day = new Date(`${briefing.day}T00:00:00`);
  const unavailable = Object.entries(briefing.unavailable);

  return (
    <div className="mx-auto max-w-[820px] px-10 py-12">
      <PageHeader
        title={day.toLocaleDateString(undefined, {
          weekday: "long",
          day: "numeric",
          month: "long",
        })}
        subtitle={
          briefing.generated_by === "model"
            ? "Written from what Jarvis found"
            : "Assembled from what Jarvis found"
        }
      />

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="mb-8 text-[15px] leading-relaxed text-ink-0"
      >
        {briefing.opener}
      </motion.p>

      {briefing.quiet && <EmptyState title="Nothing needs you this morning." />}

      {briefing.recommendations.length > 0 && (
        <Card className="mb-6">
          <SectionLabel>Ranked by impact × urgency × confidence</SectionLabel>
          <ul>
            {briefing.recommendations.map((recommendation) => (
              <RecommendationRow
                key={recommendation.id}
                recommendation={recommendation}
                onDismiss={dismiss}
              />
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {briefing.sections
          .filter((section) => section.title !== "Today")
          .map((section, index) => (
            <Card key={section.title} delay={index * 0.03}>
              <SectionLabel>{section.title}</SectionLabel>
              <ul className="space-y-1.5">
                {section.lines.map((line, lineIndex) => (
                  <li key={lineIndex} className="text-[12.5px] leading-relaxed text-ink-1">
                    {line.replace(/\*\*/g, "").replace(/`/g, "")}
                  </li>
                ))}
              </ul>
              {section.note && <p className="mt-3 text-[11px] text-ink-3">{section.note}</p>}
            </Card>
          ))}
      </div>

      {/* Named, not omitted. A missing calendar section reads as "nothing on
          today" rather than "Jarvis cannot see your calendar". */}
      {unavailable.length > 0 && (
        <div className="mt-8 flex items-start gap-2 border-t border-hairline pt-4 text-[11.5px] text-ink-3">
          <AlertTriangle size={13} className="mt-px shrink-0" />
          <p>
            Not covered:{" "}
            {unavailable.map(([name, why], index) => (
              <span key={name}>
                {index > 0 && "; "}
                <span className="text-ink-2">{name}</span> — {why}
              </span>
            ))}
            .
          </p>
        </div>
      )}

      {briefing.recommendations.length > 0 && (
        <p className="mt-4 flex items-center gap-1.5 text-[11.5px] text-ink-3">
          <Check size={12} />
          Ranking is arithmetic, not a model&apos;s opinion — every line shows what produced it.
        </p>
      )}
    </div>
  );
}
