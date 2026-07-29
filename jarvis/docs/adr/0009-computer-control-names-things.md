# ADR 0009 — Computer control acts on named elements, and the wall grades the target

**Status:** accepted · M8 · extends ADR 0005

## Context

Two questions decide whether computer control is a feature or a liability.

**What is the action space?** The obvious answer is the one the demos use: give
the model a screenshot, let it emit `click(412, 388)`. It is easy to build and
it is wrong for this system, because Jarvis asks humans for permission. An
approval prompt reading "click (412, 388)" is not a decision anybody can make;
the human either rubber-stamps it or gives up on approvals. The same is true
afterwards — an audit log of coordinates records nothing about what happened.
Coordinates are also brittle: they are a claim about what has not moved since
the screenshot was taken.

**Where does the permission boundary go?** The tool registry (ADR 0005) grades
actions by verb, and for shell and filesystem that works. It cannot work here,
because for a browser the verb carries almost no information. Typing into a
search box and typing into a card number field are the same verb. Clicking a
link and clicking "Delete account" are the same verb. A tier assigned to
`browser_click` is either so loose it permits the purchase or so tight it
blocks the search.

## Decision

**Actions name elements.** Each observation enumerates interactive elements
with a per-snapshot ref, a role and an accessible name, built from the DOM
rather than from pixels. The model acts on refs. Screenshots are still
captured — as evidence for the audit trail and for the human deciding — but
they are not the action space. Every action therefore has a sentence: *click
button «Place order — £2,480» on checkout.example.com*. That sentence is what
the approval prompt shows, what the event carries, and what the UI renders.

**The wall grades the target, not the verb**, in one place
(`ComputerPolicy.judge`) called from one choke point (`ComputerSession.act`):

* **Navigation off the allowlist escalates rather than blocks.** An agent doing
  research legitimately needs somewhere new — and going somewhere new is also
  exactly what a prompt injection asks for. Escalating keeps the capability and
  puts a human on its edge. Host matching is on label boundaries, so
  `example.com` covers `docs.example.com` and never `notexample.com` or
  `example.com.evil.net`, and credentials in a URL do not make a host.

* **Credential and payment fields are refused outright, never escalated.** This
  is the one rule with no approval path, and that is the point: someone who
  approves forty prompts a day will approve the one that matters. A rule that
  cannot be clicked through is worth more than one that can. Filling
  credentials is a user-initiated action against a vault (M10), not a tool
  call. A secret field's contents are never surfaced — not to the model, not to
  the event log, not to an approval prompt.

* **Committing clicks escalate, quoting the page.** Pay, delete, confirm, send,
  transfer — the vocabulary of what cannot be taken back. The prompt quotes the
  element's own accessible name, so the human sees what the page says rather
  than what the model says the page says.

* **An action whose ref is not in the current snapshot is refused.** Acting on
  an element Jarvis cannot currently see is acting blind: either the page moved
  or the model invented the ref.

**Budgets are part of the boundary.** An agent driving a browser can burn an
afternoon and a lot of money without ever failing. A session has a step
ceiling, a wall-clock deadline, and loop detection — the same action three
times means stuck, not persistent. Scrolling and waiting are exempt, because
repeating is what they are for.

**Page text is untrusted input**, handed to the model inside an explicit
envelope saying so. That helps, but it is not the defence. The defence is that
the wall is enforced in code at the choke point, whatever the page talked the
model into asking for.

## Consequences

- Perception costs a DOM walk per observation rather than a single screenshot,
  and is capped (120 elements, 6k characters). An index of 400 divs is not
  perception; it is noise the model pays for twice.
- The driver must keep live element handles between observe and act, so a
  stale ref fails loudly rather than clicking whatever is there now.
- Sites that render controls without accessible names are perceived poorly.
  That is the right failure: an element Jarvis cannot describe is one it cannot
  ask permission for.
- **Over-detection is not the safe direction.** Secret-field matching was
  substring-based until a real page was tried, where "Keep sho*ppin*g" matched
  the `pin` hint and an ordinary link was classified as a credential field.
  Matching is now per token, with multi-word hints as phrases. A wall that
  cries wolf teaches the user to ignore it.
- Computer control is **off by default** (`enable_computer`). A browser Jarvis
  can drive is a capability to opt into, not one to discover.
- Desktop control is deliberately not built. The browser can be contained — its
  own profile, its own downloads, no filesystem outside the workspace — and a
  desktop cannot. The port is shaped so a desktop driver could sit behind it,
  but nothing about this milestone assumes one will.
