"""The trading department: an SPX options AI signal bot built on the Jarvis kernel.

Nothing here is a chat agent. Market data collection, technical and options
analysis, strategy construction and risk filtering are deterministic
computation — the same input must always produce the same signal, which a
trading system cannot trade off for LLM judgement. Each stage is a plain
Python class registered as a set of Jarvis tools (``trading.tools``), wired
together by ordinary ``TOOL`` steps in a Jarvis workflow
(``trading.workflows``), and driven by the same event bus, workflow engine
and scheduler every other department uses.
"""

from __future__ import annotations
