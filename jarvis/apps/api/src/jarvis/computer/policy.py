"""The permission wall for computer control.

The registry's tiers (`jarvis.tools.registry`) answer "may this agent drive a
browser at all". They cannot answer the question that actually matters, because
it depends on the *target*, not the verb: typing into a search box and typing
into a card number field are the same action, and clicking a link and clicking
"Delete account" are the same action. So the wall lives here, and it grades
each action against the screen it is about to touch.

Three rules, each earning its place:

1. **Navigation off the allowlist escalates rather than blocks.** An agent
   researching the web legitimately needs to go somewhere new — but going
   somewhere new is also exactly what a prompt injection asks for. Escalating
   keeps the capability and puts a human on the edge of it.

2. **Secret fields are refused outright, never escalated.** Credentials do not
   come from a model, with or without a human clicking approve. Someone who
   approves forty prompts a day will approve the one that matters; a rule that
   cannot be clicked through is worth more than a rule that can. Filling
   credentials is a user-initiated action against a vault, not a tool call.

3. **Committing clicks escalate, named in the prompt.** "Pay", "delete",
   "confirm", "send" — the vocabulary of an action you cannot take back. The
   approval prompt quotes the element's own accessible name, so the human sees
   what the page says, not what the model claims it says.

Everything here is deny-by-default in the sense that matters: an action whose
target cannot be found in the current snapshot is refused, because acting on an
element Jarvis cannot see is acting blind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from jarvis.computer.models import Action, ActionKind, Snapshot

# Words that mark a click as committing something — money, data, or a message
# that cannot be unsent. Matched as whole words against the accessible name.
COMMITTING_WORDS = frozenset(
    {
        "buy",
        "purchase",
        "pay",
        "checkout",
        "order",
        "subscribe",
        "confirm",
        "delete",
        "remove",
        "destroy",
        "erase",
        "send",
        "submit",
        "publish",
        "post",
        "transfer",
        "withdraw",
        "cancel",
        "deactivate",
        "disable",
        "approve",
        "accept",
        "agree",
        "sign",
        "install",
        "deploy",
        "merge",
    }
)

# Field names and types that mean "this is a credential or a payment
# instrument". Sites name these inconsistently — label, `name`, `id` and
# `autocomplete` all disagree — so all four are searched.
#
# Matching is per *token*, not per substring. Substring matching looked fine
# until a real page was tried: "Keep shopping" contains "pin", so an ordinary
# link was classified as a credential field. Over-detection is not the safe
# direction it looks like — it makes Jarvis refuse ordinary work and tell the
# user a link is a password box, which teaches them to ignore the warning.
# Multi-word hints below are still matched as phrases.
SECRET_HINTS = (
    "password",
    "passwd",
    "pin",
    "otp",
    "2fa",
    "mfa",
    "one-time",
    "onetime",
    "verification code",
    "security code",
    "cvv",
    "cvc",
    "card number",
    "cardnumber",
    "credit card",
    # HTML autocomplete tokens for payment instruments. Matched as-is because
    # they are exact and unambiguous, where bare "card" catches "Cardigan".
    "cc-number",
    "cc-csc",
    "cc-exp",
    "current-password",
    "new-password",
    "iban",
    "routing",
    "account number",
    "ssn",
    "social security",
    "secret",
    "api key",
    "apikey",
    "token",
    "private key",
    "seed phrase",
    "recovery phrase",
)

_WORD = re.compile(r"[a-z]+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(text: str) -> str:
    return " ".join(part for part in _NON_ALNUM.split(text.lower()) if part)


# Split once at import: phrases are matched as substrings of the normalised
# haystack, single words only as whole tokens.
_SECRET_PHRASES = tuple(h for h in map(_normalise, SECRET_HINTS) if " " in h)
_SECRET_WORDS = frozenset(h for h in map(_normalise, SECRET_HINTS) if " " not in h)


def looks_secret(name: str, *, input_type: str = "") -> bool:
    """Whether a field is a credential or payment instrument."""
    if input_type.lower() == "password":
        return True
    haystack = _normalise(name)
    if _SECRET_WORDS & set(haystack.split()):
        return True
    return any(phrase in haystack for phrase in _SECRET_PHRASES)


class Verdict(StrEnum):
    ALLOW = "allow"
    APPROVE = "approve"
    REFUSE = "refuse"


@dataclass(slots=True)
class Ruling:
    verdict: Verdict
    description: str
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict is not Verdict.REFUSE


@dataclass(slots=True)
class ComputerPolicy:
    """Grades an action against the screen it is about to touch."""

    # Hosts Jarvis may visit without asking. Suffix-matched on label
    # boundaries, so "example.com" covers "docs.example.com" but never
    # "notexample.com". Empty means every navigation is escalated.
    allowed_hosts: tuple[str, ...] = ()
    # Hosts Jarvis may never visit, checked before the allowlist.
    blocked_hosts: tuple[str, ...] = ()
    committing_words: frozenset[str] = field(default_factory=lambda: COMMITTING_WORDS)
    # When false, even an allowlisted host's committing clicks run unattended.
    # Off by default: the whole point of the wall is that it is on.
    trust_allowlisted_clicks: bool = False

    def host_allowed(self, host: str) -> bool:
        return bool(host) and self._matches(host, self.allowed_hosts)

    def host_blocked(self, host: str) -> bool:
        return bool(host) and self._matches(host, self.blocked_hosts)

    @staticmethod
    def _matches(host: str, patterns: tuple[str, ...]) -> bool:
        host = host.lower().rstrip(".")
        for pattern in patterns:
            candidate = pattern.lower().lstrip("*.").rstrip(".")
            if host == candidate or host.endswith("." + candidate):
                return True
        return False

    @staticmethod
    def _host_of(url: str) -> str:
        return Snapshot(url=url).host

    def judge(self, action: Action, snapshot: Snapshot) -> Ruling:
        """Grade one action. This is the only place the answer is decided."""
        if action.kind is ActionKind.NAVIGATE:
            return self._judge_navigation(action)

        if action.kind in (ActionKind.SCROLL, ActionKind.WAIT, ActionKind.BACK):
            return Ruling(Verdict.ALLOW, self.describe(action, snapshot))

        element = snapshot.find(action.ref)
        if element is None:
            # Acting on something not in the current snapshot is acting blind:
            # the page has changed, or the model invented a ref.
            return Ruling(
                Verdict.REFUSE,
                self.describe(action, snapshot),
                f"no element {action.ref!r} on the current page — re-observe first",
            )
        if not element.enabled:
            return Ruling(
                Verdict.REFUSE, self.describe(action, snapshot), f"{element.describe()} is disabled"
            )

        description = self.describe(action, snapshot)

        if action.kind in (ActionKind.TYPE, ActionKind.SELECT, ActionKind.PRESS) and element.secret:
            return Ruling(
                Verdict.REFUSE,
                description,
                "credentials and payment details are never entered by an agent — "
                "fill this field yourself",
            )

        if action.kind is ActionKind.CLICK and self._is_committing(element.name):
            if self.trust_allowlisted_clicks and self.host_allowed(snapshot.host):
                return Ruling(Verdict.ALLOW, description)
            return Ruling(Verdict.APPROVE, description, "this click commits something")

        return Ruling(Verdict.ALLOW, description)

    def _judge_navigation(self, action: Action) -> Ruling:
        host = self._host_of(action.url)
        description = f"open {action.url}"
        if not host:
            return Ruling(Verdict.REFUSE, description, f"not a navigable URL: {action.url!r}")
        if self.host_blocked(host):
            return Ruling(Verdict.REFUSE, description, f"{host} is blocked")
        if self.host_allowed(host):
            return Ruling(Verdict.ALLOW, description)
        return Ruling(Verdict.APPROVE, description, f"{host} is not on the allowlist")

    def _is_committing(self, name: str) -> bool:
        return bool(self.committing_words & set(_WORD.findall(name.lower())))

    def describe(self, action: Action, snapshot: Snapshot) -> str:
        """A sentence a human can approve or refuse without seeing the page."""
        where = f" on {snapshot.host}" if snapshot.host else ""
        element = snapshot.find(action.ref)
        target = element.describe() if element else (action.ref or "the page")

        match action.kind:
            case ActionKind.NAVIGATE:
                return f"open {action.url}"
            case ActionKind.CLICK:
                return f"click {target}{where}"
            case ActionKind.TYPE:
                # Never quote the text itself: it may be long, and if the field
                # turns out to be secret the description is what gets logged.
                shown = action.text if len(action.text) <= 60 else action.text[:57] + "…"
                return f"type {shown!r} into {target}{where}"
            case ActionKind.SELECT:
                return f"select {action.text!r} in {target}{where}"
            case ActionKind.PRESS:
                return f"press {action.key} in {target}{where}"
            case ActionKind.SCROLL:
                return f"scroll {'down' if action.amount >= 0 else 'up'}{where}"
            case ActionKind.BACK:
                return f"go back{where}"
            case ActionKind.WAIT:
                return f"wait{where}"
        return f"{action.kind.value}{where}"
