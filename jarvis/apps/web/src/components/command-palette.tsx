"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, Loader2, Sparkles } from "lucide-react";
import { useMode } from "@/lib/mode";
import { api, type AgentMatch } from "@/lib/api";

const SUGGESTIONS = [
  "Research competitors in my market",
  "Draft replies to everything in my inbox",
  "Build a revenue forecast for next quarter",
  "Review this contract for risky clauses",
  "Find leads for my supplement brand",
];

/**
 * The primary interface.
 *
 * The defining behaviour: as you type, Jarvis previews *which agents it would
 * activate and how confident it is* before you commit. Routing is visible, not
 * a black box — you see the decision, then decide whether to run it.
 */
export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>{open && <Palette onClose={onClose} />}</AnimatePresence>
  );
}

/**
 * Mounted only while open, so every invocation starts empty without an effect
 * resetting state on the way in.
 */
function Palette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const { mode } = useMode();
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<AgentMatch[]>([]);
  const [routing, setRouting] = useState(false);

  useEffect(() => {
    // Focus after the entry animation begins, or the caret jumps.
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, []);

  // Debounced so a fast typist issues one routing preview, not fifteen.
  useEffect(() => {
    const text = query.trim();
    let cancelled = false;

    const timer = setTimeout(async () => {
      if (text.length < 3) {
        setCandidates([]);
        return;
      }
      setRouting(true);
      try {
        const { candidates } = await api.route(text, mode);
        if (!cancelled) setCandidates(candidates);
      } catch {
        if (!cancelled) setCandidates([]);
      } finally {
        if (!cancelled) setRouting(false);
      }
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // Re-previews on a mode switch, because the answer to "who would handle
    // this" is different in each one.
  }, [query, mode]);

  const execute = useCallback(() => {
    const text = query.trim();
    if (!text) return;
    onClose();
    router.push(`/chat?q=${encodeURIComponent(text)}`);
  }, [query, onClose, router]);

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]"
      />
      <motion.div
        initial={{ opacity: 0, y: -8, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.985 }}
        transition={{ type: "spring", stiffness: 320, damping: 30 }}
        role="dialog"
        aria-label="Command palette"
        className="glass fixed left-1/2 top-[16vh] z-50 w-[min(660px,92vw)] -translate-x-1/2 overflow-hidden rounded-float"
      >
        <div className="flex items-center gap-3 px-5 py-4">
          <Sparkles size={17} className="shrink-0 text-accent" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") execute();
              if (event.key === "Escape") onClose();
            }}
            placeholder="Tell Jarvis what to handle…"
            className="flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3"
          />
          {routing && <Loader2 size={15} className="animate-spin text-ink-3" />}
        </div>

        {candidates.length > 0 && (
          <div className="border-t border-white/[0.06] px-5 py-3.5">
            <div className="mb-2.5 text-[10.5px] font-medium uppercase tracking-[0.09em] text-ink-3">
              Agents Jarvis would activate
            </div>
            <div className="flex flex-col gap-1.5">
              {candidates.map((match) => (
                <div key={match.agent_id} className="flex items-center gap-3">
                  <span className="w-[132px] shrink-0 text-[13.5px]">
                    {match.agent_id.replace(/_/g, " ")}
                  </span>
                  <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/[0.07]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${match.confidence * 100}%` }}
                      transition={{
                        type: "spring",
                        stiffness: 200,
                        damping: 28,
                      }}
                      className="h-full rounded-full bg-accent"
                    />
                  </div>
                  <span className="w-9 shrink-0 text-right font-mono text-[11px] text-ink-3">
                    {match.confidence.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
            {candidates[0]?.reasons.length > 0 && (
              <div className="mt-2.5 truncate text-[11.5px] text-ink-3">
                {candidates[0].reasons.join(" · ")}
              </div>
            )}
          </div>
        )}

        {query.trim().length < 3 && (
          <div className="border-t border-white/[0.06] px-5 py-3.5">
            <div className="mb-2 text-[10.5px] font-medium uppercase tracking-[0.09em] text-ink-3">
              Try
            </div>
            <div className="flex flex-col">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  className="rounded-control px-2 py-[7px] text-left text-[13.5px] text-ink-2 transition-colors hover:bg-white/[0.05] hover:text-ink"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-2.5 text-[11px] text-ink-3">
          <span>Jarvis routes to specialists automatically</span>
          <span className="flex items-center gap-1.5">
            Execute <CornerDownLeft size={11} />
          </span>
        </div>
      </motion.div>
    </>
  );
}
