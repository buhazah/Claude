# API Reference

Base URL: `http://localhost:8700`. All `/api/*` routes except health and
auth register/login/refresh require a Bearer access token:

```
Authorization: Bearer <access_token>
```

Interactive docs are available at `/docs` (Swagger) and `/redoc` when the
server is running.

## Authentication

Tokens: a short-lived **access token** (default 60 min) and a rotating
**refresh token** (default 30 days, single-use). On `401`, the client posts
the refresh token to `/api/auth/refresh` to get a new pair.

| Method | Path | Body | Notes |
|--------|------|------|-------|
| POST | `/api/auth/register` | `{email, password, name?}` | First user becomes `owner`. Returns tokens + user. |
| POST | `/api/auth/login` | `{email, password}` | Returns tokens + user. |
| POST | `/api/auth/refresh` | `{refresh_token}` | Rotates the refresh token. |
| GET | `/api/auth/me` | — | Current user. |
| PUT | `/api/auth/preferences` | `{preferences}` | Merges into stored preferences. |

**TokenOut**: `{access_token, refresh_token, token_type:"bearer", user}`.

## Chat (Server-Sent Events)

### `POST /api/chat/stream`
Body: `{message, conversation_id?, agent?}`. If `agent` is omitted or
`"orchestrator"`, the orchestrator routes automatically; otherwise the named
agent answers directly.

Returns `text/event-stream`. Event types:

| Event | Data | Meaning |
|-------|------|---------|
| `open` | `{conversation_id}` | Conversation id (new or existing). |
| `status` | `{message}` | Human-readable progress. |
| `plan` | `{mode, agent, reason, tasks}` | The orchestrator's routing decision. |
| `task_start` | `{id?, agent, instruction}` | A sub-task began. |
| `task_done` | `{id?, agent, result}` | A sub-task finished. |
| `final` | `{text, agent, cost_usd?}` | The final synthesized answer. |
| `error` | `{message}` | Recoverable error (stream continues). |
| `done` | `{agent}` | Stream complete; assistant message persisted. |

Example (JavaScript):
```js
const res = await fetch("/api/chat/stream", {
  method: "POST",
  headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
  body: JSON.stringify({ message: "Plan my week" }),
});
const reader = res.body.getReader();
// parse `event:`/`data:` blocks separated by \n\n
```

### Conversation history
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/chat/conversations` | Most recent 100. |
| GET | `/api/chat/conversations/{id}/messages` | Full transcript. |
| DELETE | `/api/chat/conversations/{id}` | Deletes conversation + messages. |

## Agents
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/agents` | All 23 agent definitions (`key, name, role, goals, tools`). |
| GET | `/api/agents/runs?limit=30` | Recent agent runs with plan, steps, tokens, cost. |

## Memory
| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/api/memory?kind=&limit=` | — | Browse, ranked by importance. |
| GET | `/api/memory/stats` | — | Counts per kind + total. |
| POST | `/api/memory` | `{content, kind?, importance?}` | Add a memory. |
| POST | `/api/memory/search` | `{query, limit?, kinds?}` | Semantic search; results include `score`. |
| DELETE | `/api/memory/{id}` | — | Delete. |
| POST | `/api/memory/maintenance` | — | Run consolidation + reflection. |

**Kinds**: `profile, preference, goal, project, relationship, fact, decision,
mistake, lesson, skill, style, business, life, conversation, reflection,
summary`.

## Projects & Tasks
| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/api/projects` | — | List. |
| POST | `/api/projects` | `{name, description?}` | Create. |
| DELETE | `/api/projects/{id}` | — | Delete + its tasks. |
| GET | `/api/tasks?project_id=&status=` | — | Filterable list, ordered by priority. |
| POST | `/api/tasks` | `{title, description?, project_id?, parent_id?, priority?, due_at?, assignee_agent?, depends_on?}` | Create. |
| PATCH | `/api/tasks/{id}` | partial `TaskUpdate` | Update; setting `status:"done"` stamps `completed_at`. |
| DELETE | `/api/tasks/{id}` | — | Delete. |

## Workflows (Automations)
| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/api/workflows` | — | List. |
| POST | `/api/workflows` | `{name, prompt, schedule?, agent?, description?, enabled?}` | `schedule` is `"manual"` or a 5-field cron. |
| PATCH | `/api/workflows/{id}` | full `WorkflowIn` | Update. |
| DELETE | `/api/workflows/{id}` | — | Delete. |
| POST | `/api/workflows/{id}/run` | — | Run now; returns output. |
| GET | `/api/workflows/{id}/runs` | — | Last 50 runs. |

## Voice
| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/api/voice/config` | — | Availability of TTS/STT. |
| POST | `/api/voice/tts` | `{text, voice_id?}` | Streams `audio/mpeg` (ElevenLabs). `503` if unconfigured. |
| POST | `/api/voice/transcribe` | multipart `file` | Whisper transcription (needs `OPENAI_API_KEY`). |

## Analytics
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/analytics/overview` | Counts, tokens, total cost. |
| GET | `/api/analytics/agent-activity` | Runs and cost per agent. |
| GET | `/api/analytics/status` | Configured providers, embedding backend, feature flags. |

## Health
`GET /api/health` → `{status:"ok", version}` (no auth).

## Errors
Standard HTTP codes with `{"detail": "<message>"}`:
`400` validation, `401` unauthenticated, `403` forbidden/role,
`404` not found, `409` conflict (duplicate email), `429` rate limited,
`503` feature unconfigured (e.g. voice without a key).
