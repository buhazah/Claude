# Developer Guide

## Project layout

```
jarvis/
├── server/
│   ├── main.py            # FastAPI app, router wiring, SPA serving, lifespan
│   ├── config.py          # all settings, env-driven
│   ├── db.py              # async engine + ORM models + init_db
│   ├── security.py        # JWT, PBKDF2, rate limit, audit, auth deps
│   ├── schemas.py         # Pydantic request/response models
│   ├── llm/
│   │   ├── base.py        # provider interface + ModelSpec + LLMResponse
│   │   ├── providers.py   # Anthropic, OpenAI-compatible, Google
│   │   └── router.py      # model catalog + scoring + fallback
│   ├── memory/
│   │   ├── embeddings.py  # OpenAI/Voyage/local embedders
│   │   └── manager.py     # recall, ranking, decay, consolidation, reflection
│   ├── agents/
│   │   ├── definitions.py # 23 AgentDefs (declarative)
│   │   ├── runtime.py     # ReAct reason/act/observe loop
│   │   └── orchestrator.py# decompose, route, execute graph, synthesize
│   ├── tools/
│   │   ├── base.py        # Tool, ToolRegistry, @tool decorator, validation
│   │   └── core_tools.py  # web, filesystem, shell, code, documents
│   ├── automation/
│   │   └── scheduler.py   # cron parser + async workflow loop
│   ├── voice/
│   │   └── tts.py         # ElevenLabs TTS + Whisper STT
│   └── api/               # one router per domain
├── web/                   # vanilla-JS SPA (index.html, css/, js/)
├── tests/                 # pytest suite
├── docs/                  # this documentation
├── scripts/               # dev.sh, seed_examples.py
├── Dockerfile, docker-compose.yml
└── requirements*.txt
```

## Run locally

```bash
pip install -r requirements-dev.txt
./scripts/dev.sh          # auto-reload on http://localhost:8700
python -m pytest          # tests
```

## Add a new agent

Agents are pure data. Append to `AGENTS` in `server/agents/definitions.py`:

```python
_add(AgentDef(
    "negotiator", "Negotiation Agent",
    "Prepare negotiation strategy, BATNA analysis, and scripts.",
    ["Identify leverage and BATNA", "Draft concession ladders", "Write scripts"],
    BASE_TOOLS + FILE_TOOLS, complexity=7, temperature=0.5,
))
```

It's immediately routable by the orchestrator, selectable in the chat UI, and
usable as a workflow agent. No other changes needed.

## Add a new tool

Decorate an async function in `server/tools/core_tools.py` (or a new module
imported at startup):

```python
from .base import ToolParam, tool

@tool(
    "translate",
    "Translate text to a target language.",
    [ToolParam("text", "string", "Text to translate"),
     ToolParam("target", "string", "Target language, e.g. 'French'")],
    timeout=30,
)
async def translate(text: str, target: str) -> str:
    ...  # return a string
    return result
```

Then add `"translate"` to the `tools` list of any agent that should use it.
Arguments are validated against the declared params before your handler runs.

## Add a new LLM provider

1. If it's OpenAI-compatible, you're mostly done — instantiate
   `OpenAICompatibleProvider(key, base_url, name=...)` in
   `ModelRouter.__init__` and add its models to `CATALOG` in `router.py`.
2. For a native API, subclass `LLMProvider` in `providers.py` and implement
   `complete` and `stream`.
3. Add a config key in `config.py` and wire it in the router constructor.

The router will start scoring the new models automatically.

## Add an API endpoint

Create or extend a router in `server/api/`, depend on `get_current_user` for
auth, validate with a Pydantic model from `schemas.py`, and include the router
in `server/main.py`. Follow the existing per-domain pattern.

## Conventions

- **Async everywhere**: all I/O (DB, HTTP, tools) is `async`.
- **Config only via `config.py`**: never read `os.environ` elsewhere.
- **Ownership checks**: every user-scoped resource verifies `row.user_id ==
  user.id` before returning or mutating.
- **Fail soft on best-effort paths**: memory extraction and reflection never
  break the user's response.
- **Timeouts on external calls**: tools and provider calls are always bounded.

## Testing

```bash
python -m pytest                     # everything
python -m pytest tests/test_api.py   # one file
python -m pytest -k memory           # by keyword
```

Tests use a throwaway SQLite database (see `tests/conftest.py`) and never call
external LLMs — the chat test asserts graceful degradation without a key.
