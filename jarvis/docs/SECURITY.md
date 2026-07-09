# Security

JARVIS is built for self-hosting with production-grade defaults. This document
describes the controls in place and how to harden a deployment.

## Authentication
- **Passwords**: PBKDF2-HMAC-SHA256, 390,000 iterations, 16-byte per-user salt,
  constant-time verification (`server/security.py`). Hashes are stored as
  `pbkdf2$iterations$salt$digest`.
- **Access tokens**: stateless HS256 JWTs signed with `JARVIS_SECRET_KEY`,
  implemented with the standard library (no third-party JWT dependency in the
  security-critical path). Default lifetime 60 minutes.
- **Refresh tokens**: opaque, random, **single-use and rotating**. Only a
  SHA-256 hash is stored; redemption revokes the old token and issues a new
  pair. Default lifetime 30 days.
- Set a stable `JARVIS_SECRET_KEY` in production. If unset, a strong key is
  generated and persisted to `<data>/.secret_key` (mode 0600).

## Authorization
- Role hierarchy: `viewer < member < owner`. The first registered user becomes
  `owner`; subsequent users are `member`.
- `require_role(minimum)` dependency gates privileged routes.
- **Ownership enforcement**: every user-scoped resource (conversations,
  memories, tasks, projects, workflows) checks `row.user_id == current_user.id`
  before read or mutation. There is no cross-tenant access path.

## Rate limiting
A sliding-window in-memory limiter (`RateLimiter`) caps requests per client IP
(`JARVIS_RATE_LIMIT_PER_MINUTE`, default 120), applied on the authenticated
dependency path and returning `429` when exceeded. For multi-instance
deployments, move this to a shared store (Redis) or enforce at the ingress.

## Input & output validation
- All request bodies are validated by Pydantic models (`server/schemas.py`)
  with length and range bounds; unknown fields are rejected.
- **Tool arguments** are validated against each tool's typed schema (types,
  enums, required flags, no extra params) before the handler runs.
- Workflow cron expressions are validated (5 fields) before persistence.

## Sandboxed execution
The filesystem, shell, and Python-execution tools are confined to
`JARVIS_SANDBOX_DIR`:
- Every path is resolved and checked to be inside the sandbox root; traversal
  (`../`) raises before any I/O.
- Shell/code runs have a hard timeout (`JARVIS_SHELL_TIMEOUT`) and the process
  is killed on expiry; `HOME` and cwd are set to the sandbox.
- The entire capability can be disabled with `JARVIS_ENABLE_SHELL_TOOL=false`
  for untrusted multi-tenant deployments.
- The container runs as a **non-root** user (uid 10001) with a dedicated data
  volume.

> **Note**: code execution is powerful by design. For hostile multi-tenant use,
> disable the shell tool or run the container with additional isolation
> (gVisor, a locked-down seccomp profile, no outbound network, read-only root
> filesystem except `/data`).

## Audit logging
Security-relevant events (`user.register`, `user.login`, `user.login_failed`)
are written to `audit_logs` with the client IP and structured detail. Extend
`audit(...)` to cover more actions as needed.

## Transport & CORS
- Terminate TLS at a reverse proxy (Nginx/Caddy) or the PaaS load balancer.
- Set `JARVIS_CORS_ORIGINS` to your exact frontend origin(s) in production; the
  empty default (`allow all`) is for local development only.

## Secrets handling
- Provider API keys are read from environment variables only and never logged.
- Do not commit `.env`. The `.gitignore` and `.dockerignore` exclude it.
- The model identifier and provider keys never appear in persisted artifacts.

## Threat model summary
| Threat | Mitigation |
|--------|------------|
| Credential theft | PBKDF2 with high iteration count; only hashes stored |
| Token replay after logout | Short access-token TTL; refresh rotation revokes old tokens |
| Cross-tenant data access | Ownership checks on every resource |
| Path traversal via tools | Resolved-path sandbox confinement |
| Runaway tool/LLM calls | Per-tool and per-request timeouts; step budget on agents |
| Brute-force login | Rate limiting + failed-login audit trail |
| Prompt-injected tool abuse | Tool allow-list per agent; dangerous tools flag; shell disable switch |

## Hardening checklist
1. Set `JARVIS_SECRET_KEY` explicitly and keep it out of backups.
2. Set `JARVIS_ALLOW_REGISTRATION=false` after creating the owner account.
3. Set `JARVIS_CORS_ORIGINS` to your domain.
4. Put the app behind TLS.
5. For untrusted users, set `JARVIS_ENABLE_SHELL_TOOL=false`.
6. Use Postgres and move rate limiting to the ingress for multi-instance.
7. Rotate provider keys periodically; scope them to minimum needed access.
