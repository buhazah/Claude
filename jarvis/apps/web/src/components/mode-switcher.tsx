"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown } from "lucide-react";
import { useMode } from "@/lib/mode";

/**
 * Switching mode is a consequential act — it changes which agents can be
 * reached, which tools they keep, and which memory they read. So the menu
 * states what each mode actually narrows rather than only naming it.
 */
export function ModeSwitcher() {
  const { mode, setMode, modes, current } = useMode();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const away = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", away);
    return () => window.removeEventListener("mousedown", away);
  }, []);

  if (modes.length === 0) return null;

  return (
    <div ref={root} className="relative mb-3">
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="mode-switcher"
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-control px-2.5 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:bg-surface-2"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="flex-1 text-left">{current?.name ?? "Personal"}</span>
        <ChevronDown size={13} className="text-ink-3" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.14 }}
            role="listbox"
            className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-control border border-hairline bg-surface shadow-xl"
          >
            {modes.map((m) => (
              <button
                key={m.id}
                role="option"
                aria-selected={m.id === mode}
                onClick={() => {
                  setMode(m.id);
                  setOpen(false);
                }}
                className="flex w-full items-start gap-2 px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
              >
                <Check
                  size={13}
                  className={`mt-0.5 shrink-0 ${m.id === mode ? "text-accent" : "opacity-0"}`}
                />
                <span className="min-w-0">
                  <span className="block text-[12.5px] text-ink">{m.name}</span>
                  <span className="block text-[11.5px] leading-snug text-ink-3">
                    {m.id === "personal"
                      ? "Every agent, shared memory"
                      : `${m.agent_count} agents · ${m.memory_scope} memory`}
                  </span>
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
