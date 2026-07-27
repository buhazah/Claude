"use client";

import { motion } from "framer-motion";

/** Section heading. Small, quiet, never competing with content. */
export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-[10.5px] font-medium uppercase tracking-[0.09em] text-ink-3">
      {children}
    </div>
  );
}

export function Card({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 30, delay }}
      className={`card p-5 ${className}`}
    >
      {children}
    </motion.div>
  );
}

/**
 * Skeletons match the geometry of the content they replace, so nothing shifts
 * when data lands. No spinners on page surfaces.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-2 ${className}`} />;
}

export function EmptyState({ title, action }: { title: string; action?: string }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-12 text-center">
      <p className="text-[14px] text-ink-2">{title}</p>
      {action && <p className="text-[12.5px] text-ink-3">{action}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <p className="text-[14px] text-ink-2">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-control border border-hairline px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-ink-3 hover:text-ink"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function Chip({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  const colors: Record<string, string> = {
    neutral: "text-ink-3 border-hairline",
    accent: "text-accent border-accent/30 bg-accent/[0.07]",
    positive: "text-positive border-positive/30 bg-positive/[0.07]",
    warning: "text-warning border-warning/30 bg-warning/[0.07]",
    danger: "text-danger border-danger/30 bg-danger/[0.07]",
  };
  return (
    <span
      className={`rounded-md border px-1.5 py-0.5 font-mono text-[10.5px] ${colors[tone] ?? colors.neutral}`}
    >
      {children}
    </span>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-8">
      <h1 className="text-[26px] font-semibold">{title}</h1>
      {subtitle && <p className="mt-1 text-[13.5px] text-ink-3">{subtitle}</p>}
    </header>
  );
}
