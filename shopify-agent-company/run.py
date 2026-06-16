#!/usr/bin/env python3
"""CLI entry point for the Shopify Agent Company.

Usage:
    python run.py "Audit conversion and give me the top 3 fixes"
    python run.py                # interactive: type tasks, Ctrl-C to quit
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from company.master import run_task          # noqa: E402
from company.settings import load_store_config  # noqa: E402


def main() -> None:
    cfg = load_store_config()
    name = cfg.store.get("name", "store")
    agents = ", ".join(cfg.enabled_agents) or "(none enabled)"
    print(f"🏢 Agent Company online for: {name}")
    print(f"   Active agents: {agents}\n")

    if len(sys.argv) > 1:
        asyncio.run(run_task(cfg, " ".join(sys.argv[1:])))
        return

    print("Interactive mode — type a task, Ctrl-C to quit.\n")
    try:
        while True:
            task = input("you> ").strip()
            if task:
                asyncio.run(run_task(cfg, task))
                print()
    except (KeyboardInterrupt, EOFError):
        print("\n👋 shutting down.")


if __name__ == "__main__":
    main()
