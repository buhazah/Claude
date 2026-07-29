"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic, X } from "lucide-react";
import { openVoiceSocket, type VoiceEvent } from "@/lib/api";

/**
 * Voice mode.
 *
 * Recognition runs in the browser (`SpeechRecognition`) and the recognised text
 * goes up the socket. That keeps audio off the network in the default
 * configuration, and it is also what makes barge-in feel instant — the moment
 * the recogniser reports *any* speech, we interrupt, without waiting for a
 * server round trip to decide.
 *
 * The visual is deliberately one thing: an orb whose state you can read across
 * a room. Listening breathes, thinking pulses faster, speaking ripples.
 */

type Recognition = {
  start: () => void;
  stop: () => void;
  abort: () => void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }>;
};

const STATE_COPY: Record<string, string> = {
  idle: "Ready",
  waiting_for_wake: "Say “Jarvis”",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking — just talk to interrupt",
  ended: "Ended",
};

function recognitionCtor(): (new () => Recognition) | undefined {
  if (typeof window === "undefined") return undefined;
  const scope = window as unknown as {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
}

/**
 * Support is a fact about the browser, not React state — reading it through
 * `useSyncExternalStore` keeps the server render (assume yes) and the client
 * render honest without a setState-in-effect cascade. It never changes, so the
 * subscription is a no-op.
 */
const NEVER_CHANGES = () => () => {};

function useSpeechSupported(): boolean {
  return useSyncExternalStore(
    NEVER_CHANGES,
    () => recognitionCtor() !== undefined,
    () => true,
  );
}

export function VoiceMode({ open, onClose }: { open: boolean; onClose: () => void }) {
  return <AnimatePresence>{open && <VoiceOverlay onClose={onClose} />}</AnimatePresence>;
}

function VoiceOverlay({ onClose }: { onClose: () => void }) {
  const [state, setState] = useState("idle");
  const [heard, setHeard] = useState("");
  const [reply, setReply] = useState("");
  const [typed, setTyped] = useState("");
  const supported = useSpeechSupported();
  const socketRef = useRef<ReturnType<typeof openVoiceSocket> | null>(null);
  const speakingRef = useRef(false);

  const handle = useCallback((event: VoiceEvent) => {
    switch (event.type) {
      case "state":
        setState(event.state ?? "idle");
        speakingRef.current = event.state === "speaking" || event.state === "thinking";
        break;
      case "partial":
        setHeard(event.text ?? "");
        break;
      case "transcript":
        setHeard(event.text ?? "");
        setReply("");
        break;
      case "token":
        setReply((current) => current + (event.text ?? ""));
        break;
      case "interrupted":
        // Show what was actually heard, not what was generated.
        setReply(event.text ?? "");
        break;
    }
  }, []);

  useEffect(() => {
    const socket = openVoiceSocket(handle);
    socketRef.current = socket;

    const Ctor = recognitionCtor();
    if (!Ctor) return () => socket.close();

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0].transcript.trim();
        if (!text) continue;

        // Barge-in the instant speech is detected, without waiting for a final
        // transcript or a server decision — the delay is what makes voice
        // assistants feel like they are talking over you.
        if (!result.isFinal && speakingRef.current) socket.interrupt();
        socket.say(text, result.isFinal);
      }
    };
    // A recogniser stops on its own after a pause; restart while the overlay
    // is open so the conversation stays live.
    recognition.onend = () => {
      try {
        recognition.start();
      } catch {
        /* already started */
      }
    };
    // `no-speech` and `aborted` fire constantly and mean nothing is wrong;
    // `onend` restarts the recogniser either way, so errors are swallowed.
    recognition.onerror = () => {};

    try {
      recognition.start();
    } catch {
      /* start() throws if the mic is already live — harmless */
    }

    return () => {
      recognition.onend = null;
      recognition.abort();
      socket.close();
    };
  }, [handle]);

  const busy = state === "thinking" || state === "speaking";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[70] grid place-items-center bg-canvas/92 backdrop-blur-xl"
      role="dialog"
      aria-label="Voice mode"
    >
      <button
        onClick={onClose}
        aria-label="Close voice mode"
        className="absolute right-6 top-6 grid h-9 w-9 place-items-center rounded-full text-ink-3 transition-colors hover:text-ink"
      >
        <X size={18} />
      </button>

      <div className="flex flex-col items-center gap-8 px-8 text-center">
        <motion.div
          animate={
            busy
              ? { scale: [1, 1.12, 1], opacity: [0.85, 1, 0.85] }
              : { scale: [1, 1.04, 1], opacity: [0.6, 0.85, 0.6] }
          }
          transition={{ duration: busy ? 1.1 : 3.2, repeat: Infinity, ease: "easeInOut" }}
          className="grid h-32 w-32 place-items-center rounded-full"
          style={{
            background:
              "radial-gradient(circle at 50% 45%, color-mix(in oklab, var(--color-accent) 45%, transparent), transparent 70%)",
            boxShadow: "0 0 80px -10px color-mix(in oklab, var(--color-accent) 40%, transparent)",
          }}
        >
          <Mic size={30} className="text-accent" />
        </motion.div>

        <div className="min-h-[2rem]">
          <p className="text-[13px] uppercase tracking-[0.14em] text-ink-3">
            {STATE_COPY[state] ?? state}
          </p>
        </div>

        {!supported && (
          <p className="max-w-md text-[13.5px] text-ink-3">
            This browser has no speech recognition — type instead, or use Chrome,
            Edge or Safari.
          </p>
        )}

        {heard && (
          <p className="max-w-2xl text-[19px] leading-relaxed text-ink-2">“{heard}”</p>
        )}
        {reply && (
          <p data-testid="voice-reply" className="max-w-2xl text-[17px] leading-relaxed text-ink">
            {reply}
          </p>
        )}

        {/* Talking is not always possible. The same session takes typing, which
            is also the only way in on browsers without a recogniser. */}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const text = typed.trim();
            if (!text) return;
            socketRef.current?.say(text, true);
            setTyped("");
          }}
          className="w-full max-w-md"
        >
          <input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="or type…"
            aria-label="Say something"
            data-testid="voice-input"
            className="w-full rounded-control border border-hairline bg-surface px-3.5 py-2.5 text-center text-[14px] text-ink outline-none transition-colors placeholder:text-ink-3 focus:border-accent/50"
          />
        </form>
      </div>
    </motion.div>
  );
}
