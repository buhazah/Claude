"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  Bot,
  Brain,
  Home,
  Library,
  MessageSquare,
  Workflow as WorkflowIcon,
  Mic,
  MonitorSmartphone,
  FileText,
  Settings,
  Sunrise,
  Search,
  Wrench,
} from "lucide-react";
import { CommandPalette } from "./command-palette";
import { ActivityRail } from "./activity-rail";
import { ApprovalGate } from "./approvals";
import { VoiceMode } from "./voice";
import { ModeSwitcher } from "./mode-switcher";

const NAV = [
  { href: "/", label: "Home", icon: Home, key: "1" },
  { href: "/briefing", label: "Briefing", icon: Sunrise, key: "2" },
  { href: "/chat", label: "Chat", icon: MessageSquare, key: "3" },
  { href: "/agents", label: "Agents", icon: Bot, key: "4" },
  { href: "/memory", label: "Memory", icon: Brain, key: "5" },
  { href: "/knowledge", label: "Knowledge", icon: Library, key: "6" },
  { href: "/workflows", label: "Workflows", icon: WorkflowIcon, key: "7" },
  { href: "/runs", label: "Runs", icon: Activity, key: "8" },
  { href: "/tools", label: "Tools", icon: Wrench, key: "9" },
  { href: "/documents", label: "Documents", icon: FileText, key: "0" },
  { href: "/computer", label: "Computer", icon: MonitorSmartphone, key: "-" },
  { href: "/settings", label: "Settings", icon: Settings, key: "," },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const chord = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();
      if (chord && key === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      // ⌘⇧V. Shift is required so a plain ⌘V still pastes.
      if (chord && event.shiftKey && key === "v") {
        event.preventDefault();
        setVoiceOpen((open) => !open);
      }
      if (key === "escape") setVoiceOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="flex w-[212px] shrink-0 flex-col border-r border-hairline px-3 py-5">
        <Link href="/" className="mb-8 flex items-center gap-2.5 px-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-[9px] bg-accent/15 text-accent">
            <span className="h-2 w-2 rounded-full bg-accent live-dot" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight">Jarvis</span>
        </Link>

        <ModeSwitcher />

        <button
          onClick={() => setPaletteOpen(true)}
          className="mb-6 flex items-center gap-2 rounded-control border border-hairline bg-surface px-2.5 py-2 text-[13px] text-ink-3 transition-colors hover:border-ink-3/40 hover:text-ink-2"
        >
          <Search size={14} />
          <span className="flex-1 text-left">Ask anything</span>
          <kbd className="font-mono text-[10px] text-ink-3">⌘K</kbd>
        </button>

        <div className="flex flex-1 flex-col gap-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className="relative flex items-center gap-2.5 rounded-control px-2.5 py-[7px] text-[13.5px] transition-colors"
                style={{ color: active ? "var(--color-ink)" : "var(--color-ink-3)" }}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-control bg-surface-2"
                    transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  />
                )}
                <Icon size={15} className="relative z-10" />
                <span className="relative z-10">{label}</span>
              </Link>
            );
          })}
        </div>

        <button
          onClick={() => setVoiceOpen(true)}
          data-testid="voice-button"
          className="flex items-center gap-2.5 rounded-control px-2.5 py-2 text-[13px] text-ink-3 transition-colors hover:text-ink-2"
        >
          <Mic size={15} />
          <span>Voice</span>
          <kbd className="ml-auto font-mono text-[10px]">⌘⇧V</kbd>
        </button>
      </nav>

      <main className="flex-1 overflow-y-auto">{children}</main>

      <ActivityRail />

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <VoiceMode open={voiceOpen} onClose={() => setVoiceOpen(false)} />
      <ApprovalGate />
    </div>
  );
}
