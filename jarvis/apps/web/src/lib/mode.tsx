"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, type ModeInfo } from "./api";

/**
 * The current mode, shared across every surface.
 *
 * The list comes from the kernel rather than being hardcoded here, because the
 * kernel is what actually enforces the narrowing. A client that invented its
 * own mode list could show a constraint nobody holds.
 */

type ModeState = {
  mode: string;
  setMode: (id: string) => void;
  modes: ModeInfo[];
  current: ModeInfo | null;
};

const ModeContext = createContext<ModeState>({
  mode: "personal",
  setMode: () => {},
  modes: [],
  current: null,
});

const STORAGE_KEY = "jarvis.mode";

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState("personal");
  const [modes, setModes] = useState<ModeInfo[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .modes()
      .then(({ modes: loaded, default: fallback }) => {
        if (cancelled) return;
        setModes(loaded);
        // Restored only after the list arrives, so a stored id the kernel no
        // longer knows about cannot wedge every request at 404.
        const stored = window.localStorage.getItem(STORAGE_KEY);
        setModeState(loaded.some((m) => m.id === stored) ? stored! : fallback);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setMode = useCallback((id: string) => {
    setModeState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const value = useMemo(
    () => ({ mode, setMode, modes, current: modes.find((m) => m.id === mode) ?? null }),
    [mode, setMode, modes],
  );

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode(): ModeState {
  return useContext(ModeContext);
}
