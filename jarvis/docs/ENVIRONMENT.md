# Environment Variables

All configuration is read once at startup by `server/config.py`. Every value
has a safe default; the app boots with no configuration at all (reasoning
endpoints then return a "configure a provider" message).

## Core
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_HOST` | `0.0.0.0` | Bind address. |
| `JARVIS_PORT` | `8700` | Port. |
| `JARVIS_DEBUG` | `false` | Verbose logging + autoreload via `dev.sh`. |
| `JARVIS_DATA_DIR` | `./data` | Directory for the DB, sandbox, and generated secret key. |
| `JARVIS_SECRET_KEY` | *(generated)* | JWT/HMAC signing key. **Set explicitly in production.** Generated and stored in the data dir if unset. |

## Database
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_DATABASE_URL` | `sqlite+aiosqlite:///<data>/jarvis.db` | SQLAlchemy async URL. Use `postgresql+asyncpg://…` for Postgres. |

## Security
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_ACCESS_TOKEN_MINUTES` | `60` | Access-token lifetime. |
| `JARVIS_REFRESH_TOKEN_DAYS` | `30` | Refresh-token lifetime. |
| `JARVIS_ALLOW_REGISTRATION` | `true` | When `false`, only the first (owner) user can be created. |
| `JARVIS_RATE_LIMIT_PER_MINUTE` | `120` | Per-client request cap (sliding window). |
| `JARVIS_DAILY_COST_CAP_USD` | `0` (off) | Instance-wide LLM spend cap over a rolling 24h. Requests are refused with HTTP 429 once exceeded. Users may set a tighter personal cap in Settings. |
| `JARVIS_DAILY_TOKEN_CAP` | `0` (off) | Instance-wide token cap over a rolling 24h (same enforcement as the cost cap). |
| `JARVIS_CORS_ORIGINS` | *(empty = allow all)* | Comma-separated allowed origins. Set this in production. |

## Sandbox (filesystem / shell / code tools)
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_SANDBOX_DIR` | `<data>/sandbox` | Root all file/shell tools are confined to. |
| `JARVIS_SHELL_TIMEOUT` | `30` | Max seconds for a shell/code execution. |
| `JARVIS_ENABLE_SHELL_TOOL` | `true` | Set `false` to disable shell + Python execution entirely. |

## LLM providers
Set at least one to enable reasoning. A provider is active iff its key (or URL)
is present.

| Variable | Provider |
|----------|----------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) |
| `OPENAI_API_KEY` | OpenAI |
| `GOOGLE_API_KEY` | Google (Gemini) |
| `GROQ_API_KEY` | Groq |
| `OPENROUTER_API_KEY` | OpenRouter (meta-provider) |
| `DEEPSEEK_API_KEY` | DeepSeek |
| `OLLAMA_BASE_URL` | Local Ollama, e.g. `http://localhost:11434` |

## Embeddings
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_EMBEDDING_PROVIDER` | `auto` | `auto` \| `openai` \| `voyage` \| `local`. `auto` prefers OpenAI, then Voyage, else the local hash embedder. |
| `VOYAGE_API_KEY` | — | For Voyage embeddings. |

`OPENAI_API_KEY` also enables OpenAI embeddings under `auto`.

## Voice
| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | — | Enables server-side TTS. Without it the UI uses the browser's speech synthesis. |
| `ELEVENLABS_VOICE_ID` | — | Voice to speak with. |
| `ELEVENLABS_MODEL` | `eleven_turbo_v2_5` | TTS model. |

## Web search
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_SEARCH_PROVIDER` | `duckduckgo` | `duckduckgo` (no key) or `brave`. |
| `BRAVE_API_KEY` | — | Required for the Brave provider. |

## Memory tuning
| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_MEMORY_HALF_LIFE_DAYS` | `30` | Recency-decay half-life for retrieval ranking. |
| `JARVIS_MEMORY_CONSOLIDATION_THRESHOLD` | `50` | Per-kind memory count that triggers consolidation. |
| `JARVIS_MEMORY_MAX_RETRIEVAL` | `12` | Max memories injected into an agent's context. |
