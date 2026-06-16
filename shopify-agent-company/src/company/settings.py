"""Load environment and per-store config. Nothing here is store-specific —
the store lives entirely in the YAML config file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_MODEL = os.getenv("COMPANY_MODEL", "claude-sonnet-4-6")


@dataclass
class StoreConfig:
    """Parsed contents of config/store.yaml for one store."""

    raw: dict[str, Any]

    @property
    def store(self) -> dict[str, Any]:
        return self.raw.get("store", {})

    @property
    def enabled_agents(self) -> list[str]:
        return [name for name, on in self.raw.get("agents", {}).items() if on]

    def autonomy(self, agent: str) -> str:
        """Per-agent autonomy: 'advise' | 'approve' | 'auto'.

        - advise/approve: read-only; the agent proposes, a human executes.
        - auto: the agent may use its mutation tools without asking.
        Defaults to 'approve' (safe) when unspecified.
        """
        levels = self.raw.get("autonomy", {})
        return levels.get(agent, levels.get("default", "approve"))

    @property
    def schedule(self) -> list[dict[str, Any]]:
        """Recurring autopilot tasks: [{name, every_minutes, task}]."""
        return self.raw.get("schedule", [])

    # --- rendered text blocks injected into prompts ---

    def profile_block(self) -> str:
        s = self.store
        return (
            f"Name: {s.get('name', '?')}\n"
            f"Domain: {s.get('domain', '?')}\n"
            f"Niche: {s.get('niche', '?')}\n"
            f"Currency: {s.get('currency', 'USD')}\n"
            f"Target market: {s.get('target_market', '?')}"
        )

    def rules_block(self) -> str:
        return "\n".join(f"- {r}" for r in self.raw.get("rules", []))

    def brand_voice_block(self) -> str:
        return yaml.safe_dump(self.raw.get("brand_voice", {}), sort_keys=False).strip()

    def economics_block(self) -> str:
        return yaml.safe_dump(self.raw.get("economics", {}), sort_keys=False).strip()


def load_store_config(path: str | None = None) -> StoreConfig:
    cfg_path = Path(path or os.getenv("STORE_CONFIG", ROOT / "config" / "store.yaml"))
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Store config not found at {cfg_path}. "
            "Copy config/store.example.yaml to config/store.yaml and edit it."
        )
    with open(cfg_path) as f:
        return StoreConfig(raw=yaml.safe_load(f) or {})


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()
