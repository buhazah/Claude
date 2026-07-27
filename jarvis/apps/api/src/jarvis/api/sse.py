"""Server-sent event framing.

Chat and the activity firehose both stream over SSE: unidirectional, survives
proxies, and reconnects on its own. The client only needs ``EventSource``.
"""

from __future__ import annotations

import json
from typing import Any

HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # stop nginx from buffering the stream
}


def frame(event: str, data: Any) -> str:
    """Encode one SSE frame. Data is always JSON so the client has one parser."""
    payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"
