# Database Schema

Async SQLAlchemy ORM (`server/db.py`). Works on SQLite (default) and Postgres.
All ids are 32-char hex UUIDs; timestamps are UTC-naive. Tables are created on
first boot by `init_db()` — no migration tool is required for the default
setup. On SQLite, `foreign_keys` and WAL are enabled via a connect hook.

## Entity overview

```
users ─┬─< conversations ─< messages
       ├─< memories
       ├─< projects ─< tasks
       ├─< tasks (also standalone, project_id nullable)
       ├─< workflows ─< workflow_runs
       ├─< agent_runs
       └─< refresh_tokens
audit_logs (user_id nullable)
```

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| email | str unique | lowercased |
| name | str | |
| password_hash | str | PBKDF2-SHA256, per-user salt |
| role | str | `owner` \| `member` \| `viewer` |
| is_active | bool | |
| preferences | JSON | free-form user settings |
| created_at | datetime | |

### refresh_tokens
Single-use rotating tokens. `token_hash` stores SHA-256 of the raw token;
`revoked` is set on redemption. Columns: `id, user_id, token_hash, expires_at,
revoked, created_at`.

### conversations
`id, user_id, title, agent, created_at, updated_at`. Cascade-deletes messages.

### messages
`id, conversation_id, role (user|assistant|system|tool), content, agent, meta
(JSON), created_at`.

### memories
The long-term memory store.
| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| user_id | str FK | |
| kind | str | one of 16 kinds (see API.md) |
| content | str | the memory text |
| source | str | `chat` \| `manual` \| `extraction` \| `consolidation` \| `reflection` \| `seed` |
| importance | float | 0.0–1.0, drives ranking |
| embedding | bytes | float32 vector (unit-norm) |
| access_count | int | incremented on recall |
| last_accessed | datetime | drives recency decay |
| consolidated_into | str? | id of the summary memory that absorbed this one |
| meta | JSON | |
| created_at | datetime | |

Consolidated memories are excluded from recall (they live on inside a summary).

### projects
`id, user_id, name, description, status (active|paused|done|archived),
created_at`. Cascade-deletes tasks.

### tasks
| Column | Type | Notes |
|--------|------|-------|
| id | str PK | |
| user_id | str FK | |
| project_id | str? FK | nullable — tasks can be standalone |
| parent_id | str? | subtask support |
| title, description | str | |
| status | str | `todo` \| `in_progress` \| `blocked` \| `done` \| `cancelled` |
| priority | int | 1 (highest) – 5 |
| due_at | datetime? | |
| assignee_agent | str | agent key |
| depends_on | JSON | list of task ids |
| created_at, completed_at | datetime | |

### workflows
Cron-scheduled automations.
`id, user_id, name, description, schedule (cron | "manual"), prompt, agent,
enabled, last_run_at, next_run_at, created_at`. Cascade-deletes runs.

### workflow_runs
`id, workflow_id, status (running|success|failed), output, error, started_at,
finished_at`.

### agent_runs
Audit + analytics record for every agent execution.
`id, user_id, conversation_id?, agent, goal, status, plan (JSON), steps (JSON),
output, error, tokens_in, tokens_out, cost_usd, started_at, finished_at`.

### audit_logs
Security event trail. `id, user_id?, action, detail (JSON), ip, created_at`.
Actions include `user.register`, `user.login`, `user.login_failed`.

## Indexing notes
Foreign keys and hot query columns (`created_at`, `status`, `kind`, `agent`,
`token_hash`) are indexed. For Postgres at scale, add a pgvector column to
`memories` and an ANN index; the memory manager is the only code that reads the
embedding, so the change is localized.
