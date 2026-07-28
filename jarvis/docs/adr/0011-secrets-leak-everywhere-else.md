# ADR 0011 — Secrets leak everywhere except the store, and a budget is a control or it is a dashboard

**Status:** accepted · M10 · completes ADR 0005

## Context

**Secrets.** Encrypting secrets at rest is a library call. It is also almost
beside the point. A secret escapes through everything *except* the store: a log
line, an event payload, an audit entry, a run step, an HTTP tool echoing the
request it just made, an exception message quoting the header it failed to
send. And in this system there is a leak path no ordinary application has — a
secret handed to a model comes back in an answer, and that answer gets written
to long-term memory.

So a vault that encrypts at rest and then passes plaintext into a tool call has
protected the disk and nothing else.

**Cost.** Every LLM product reports spend. Reporting is not governing: by the
time the number is on a dashboard the money is gone, and the case where it
matters — an agent looping, a workflow firing on an event that fires
constantly — is exactly the case nobody is watching the dashboard.

## Decision

**The model names a secret; it never holds one.**

Tool arguments carry `${vault:stripe}`. The reference is resolved inside the
tool registry at call time — *after* authorisation and *after* the audit write —
so the approval prompt and the audit log both record the reference, and the
trail stays safe to keep and still worth reading. The tool receives the real
value; nothing upstream of it ever did.

**Redaction is the part that actually works, and it is deliberately dumb.**
Every known secret value is scrubbed from anything on its way to a log, an
event or the audit log, by substring replacement at the boundary. Trusting each
call site to remember is how secrets end up in logs. This requires holding
plaintexts in memory to recognise them, which is a real trade and stated as
one: redacting nothing leaks far more, far more often. Secrets are loaded
eagerly at boot for the same reason — a secret nobody has read this process
cannot be recognised, and that is precisely when it turns up in a log line.

Supporting decisions:

* **AES-256-GCM with the name as associated data.** Authenticated, so a
  tampered ciphertext fails loudly rather than decrypting to garbage something
  downstream then sends to Stripe; and a ciphertext moved to a different name
  fails rather than silently handing the billing key to the mail client.
* **No key means locked, not plaintext.** A vault that quietly stores
  unencrypted values because it was misconfigured is worse than no vault.
* **No endpoint returns a secret.** Listings carry a name, a length and a
  four-character hint. There is no shape of the API that leaks one, which is a
  property worth having rather than a rule to remember.
* **Short secrets are not redacted.** A four-character value would scrub half
  the English language out of the logs.

**A budget is checked before the call, against an estimate, or it is a report.**

Two ceilings, because one is always wrong:

* **Soft** — crosses into the same approval gate that guards a dangerous tool.
  This is the one that should fire in normal operation: it turns "you spent
  £180 this month" from something discovered later into a decision made at the
  time.
* **Hard** — refuses, with no approval path. The case a hard ceiling exists for
  is the one where the thing burning money is also generating approval requests
  faster than anyone can read them.

The estimate assumes the model emits its full output allowance. That
over-states most calls deliberately: a budget that under-estimates is a budget
that gets exceeded, and being slightly too careful with someone's money is the
better failure. The *ledger* records actual spend, never the estimate.
Enforcement lives in the model router because that is the one place agents,
workflows, documents, voice and the routing arbiter all pass through.

**Everything durable is durable.** The vault, approvals, generated documents
and agent metrics were all in-memory and flagged at every milestone. All four
now have SQL backings behind the Protocols that were written for this swap. A
restart loses whoever was parked mid-call — their connection is gone too — but
keeps the decision record, and an approval that was pending in a dead process
is expired on restore rather than left open for nobody to answer.

## Consequences

- `ApprovalBroker.create` and `.resolve` became async, because they now write
  through. Persisting on a timer instead would have kept the signatures and
  lost decisions to a crash.
- Agent metrics are written through after **each** run rather than batched:
  routing weights a spec by its track record, so losing the last N runs makes
  routing quietly worse with no sign that anything happened.
- **The router only caught `ProviderError`.** An adapter raising anything else —
  a connection reset, a JSON decode error nobody wrapped — killed the request
  with no fallback, which is exactly the failure a fallback chain exists for.
  It now catches broadly, re-raising `BudgetExceededError` (a decision, not a
  fault) and letting `CancelledError` through as a `BaseException`. Found by
  the chaos test, not by review.
- The chaos tests assert *shape*, never latency numbers: nothing deadlocks,
  nothing loses work, nothing serialises that should not. A number measured on
  CI hardware is a flake waiting to happen.
- Holding plaintexts in memory for redaction means a core dump contains
  secrets. That is the accepted cost of scrubbing them from every other path,
  and the alternative — recognising nothing — is worse in every scenario short
  of physical memory capture.
- The vault protects secrets *from the record*, not from a compromised process.
  Anything running in this process can read them, by construction, because the
  tools need them. Process isolation is a different design and not this one.
