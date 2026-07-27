"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, Square } from "lucide-react";
import { streamChat, type AgentMatch } from "@/lib/api";
import { Chip } from "@/components/ui";

type Turn = {
  id: string;
  role: "user" | "assistant";
  text: string;
  agent?: string;
  candidates?: AgentMatch[];
  memories?: number;
  stats?: { cost_usd: number; tokens: number; latency_ms: number };
  error?: string;
  streaming?: boolean;
};

function ChatView() {
  const params = useSearchParams();
  const seeded = params.get("q");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = useCallback(async (message: string) => {
    const text = message.trim();
    if (!text) return;

    const userTurn: Turn = { id: `u-${Date.now()}`, role: "user", text };
    const replyId = `a-${Date.now()}`;
    setTurns((current) => [
      ...current,
      userTurn,
      { id: replyId, role: "assistant", text: "", streaming: true },
    ]);
    setInput("");
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const patch = (update: Partial<Turn>) =>
      setTurns((current) =>
        current.map((turn) => (turn.id === replyId ? { ...turn, ...update } : turn)),
      );

    try {
      for await (const event of streamChat(text, { signal: controller.signal })) {
        switch (event.type) {
          case "routing":
            patch({ agent: event.chosen, candidates: event.candidates });
            break;
          case "context":
            patch({ memories: event.memories });
            break;
          case "token":
            setTurns((current) =>
              current.map((turn) =>
                turn.id === replyId ? { ...turn, text: turn.text + event.text } : turn,
              ),
            );
            break;
          case "done":
            patch({
              streaming: false,
              stats: {
                cost_usd: event.cost_usd,
                tokens: event.tokens,
                latency_ms: event.latency_ms,
              },
            });
            break;
          case "error":
            patch({ streaming: false, error: event.message });
            break;
        }
      }
    } catch (error) {
      // An abort is the user interrupting, not a failure.
      const aborted = error instanceof DOMException && error.name === "AbortError";
      patch({
        streaming: false,
        error: aborted ? undefined : "Could not reach the kernel. Is the API running?",
      });
    } finally {
      patch({ streaming: false });
      setBusy(false);
      abortRef.current = null;
    }
  }, []);

  // A query param from the palette starts the conversation immediately.
  const seededRef = useRef(false);
  useEffect(() => {
    if (seeded && !seededRef.current) {
      seededRef.current = true;
      void send(seeded);
    }
  }, [seeded, send]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  return (
    <div className="mx-auto flex h-full max-w-[760px] flex-col px-8">
      <div className="flex-1 overflow-y-auto py-10">
        {turns.length === 0 && (
          <div className="mt-[22vh] text-center">
            <p className="text-[19px] text-ink-2">What should I handle?</p>
            <p className="mt-2 text-[13px] text-ink-3">
              Jarvis picks the right specialist automatically.
            </p>
          </div>
        )}

        <div className="flex flex-col gap-7">
          <AnimatePresence initial={false}>
            {turns.map((turn) => (
              <motion.div
                key={turn.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
              >
                {turn.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-[16px] rounded-br-[6px] bg-surface-2 px-4 py-2.5 text-[14.5px]">
                      {turn.text}
                    </div>
                  </div>
                ) : (
                  <div>
                    {turn.agent && (
                      <div className="mb-2 flex items-center gap-2">
                        <Chip tone="accent">{turn.agent.replace(/_/g, " ")}</Chip>
                        {turn.candidates && turn.candidates.length > 0 && (
                          <span className="font-mono text-[10.5px] text-ink-3">
                            {turn.candidates[0].confidence.toFixed(2)} confidence
                          </span>
                        )}
                        {turn.memories ? (
                          <span className="text-[11px] text-ink-3">
                            recalled {turn.memories} memories
                          </span>
                        ) : null}
                      </div>
                    )}

                    {turn.error ? (
                      <p className="text-[14px] text-danger">{turn.error}</p>
                    ) : (
                      <p className="whitespace-pre-wrap text-[14.5px] leading-[1.65] text-ink">
                        {turn.text}
                        {turn.streaming && (
                          <span className="stream-caret ml-0.5 inline-block h-[15px] w-[2px] translate-y-[2px] bg-accent" />
                        )}
                      </p>
                    )}

                    {turn.stats && (
                      <div className="mt-2.5 flex gap-3 font-mono text-[10.5px] text-ink-3">
                        <span>{Math.round(turn.stats.latency_ms)}ms</span>
                        <span>{turn.stats.tokens} tokens</span>
                        <span>${turn.stats.cost_usd.toFixed(4)}</span>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="sticky bottom-0 pb-8">
        <div className="glass flex items-end gap-2 rounded-float px-3.5 py-2.5">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
            rows={1}
            placeholder="Ask Jarvis…"
            className="max-h-40 flex-1 resize-none bg-transparent py-1.5 text-[14.5px] outline-none placeholder:text-ink-3"
          />
          <button
            onClick={() => (busy ? abortRef.current?.abort() : void send(input))}
            disabled={!busy && !input.trim()}
            aria-label={busy ? "Stop" : "Send"}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-canvas transition-opacity disabled:opacity-25"
          >
            {busy ? <Square size={12} className="fill-canvas" /> : <ArrowUp size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatView />
    </Suspense>
  );
}
