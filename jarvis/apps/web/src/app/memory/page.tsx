"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Memory } from "@/lib/api";
import { Chip, ErrorState, PageHeader, Skeleton } from "@/components/ui";

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(false);

  const [reloadKey, setReloadKey] = useState(0);

  // Debounced: search runs as you type without a request per keystroke.
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .memories(query)
        .then((found) => {
          if (cancelled) return;
          setMemories(found);
          setError(false);
        })
        .catch(() => !cancelled && setError(true));
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, reloadKey]);

  return (
    <div className="mx-auto max-w-[860px] px-10 py-12">
      <PageHeader
        title="Memory"
        subtitle="Everything Jarvis remembers, searchable the way you'd say it out loud."
      />

      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="What did I decide about pricing?"
        className="mb-6 w-full rounded-control border border-hairline bg-surface px-3.5 py-2.5 text-[13.5px] outline-none transition-colors placeholder:text-ink-3 focus:border-accent/40"
      />

      {error ? (
        <ErrorState message="Could not reach memory." onRetry={() => setReloadKey((key) => key + 1)} />
      ) : memories === null ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-[74px] w-full" />
          ))}
        </div>
      ) : memories.length === 0 ? (
        <div className="card px-5 py-10 text-center text-[13px] text-ink-3">
          {query
            ? `Nothing recalled for “${query}”.`
            : "No memories yet. Jarvis records what matters as you work."}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {memories.map((memory, index) => (
            <motion.div
              key={memory.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.02, 0.2) }}
              className="card px-4 py-3.5"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <Chip tone="accent">{memory.kind}</Chip>
                <Chip>{memory.scope}</Chip>
                {memory.signals && (
                  <span className="ml-auto font-mono text-[10px] text-ink-3">
                    lex {memory.signals.lexical.toFixed(2)} · sem{" "}
                    {memory.signals.semantic.toFixed(2)} · rec{" "}
                    {memory.signals.recency.toFixed(2)}
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-2">
                {memory.content}
              </p>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
