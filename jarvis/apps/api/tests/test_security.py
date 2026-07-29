"""Hardening: the vault, its leak paths, and cost governance.

The vault tests are mostly *not* about encryption. Encryption is a library
call. The tests that matter are the leak paths — the log line, the event
payload, the audit entry, the error message quoting the header it failed to
send — because that is how a secret actually escapes.

The budget tests are mostly about the check happening *before* the call. A
ceiling consulted afterwards is a report.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from jarvis.kernel import container
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.base import CompletionRequest, Message, Role
from jarvis.llm.providers.echo import EchoProvider
from jarvis.llm.router import ModelRouter
from jarvis.security.budget import (
    Budget,
    BudgetExceededError,
    CostGovernor,
    Ledger,
    Period,
    Verdict,
    period_key,
)
from jarvis.security.vault import (
    REDACTED,
    InMemorySecretStore,
    SecretNotFoundError,
    Vault,
    VaultLockedError,
    derive_key,
    hint_for,
    new_key,
)
from jarvis.tools.approvals import ApprovalBroker
from jarvis.tools.registry import Grant, Permission, ToolRegistry

KEY = new_key()
# Not shaped like a real provider key on purpose: a committed fixture that
# looks like a credential trips secret scanners, and that is a fair
# complaint rather than a false positive.
STRIPE = "NOT-A-REAL-KEY-vault-fixture-4821"


def _vault() -> Vault:
    return Vault(store=InMemorySecretStore(), key=derive_key(KEY))


# ── The store ─────────────────────────────────────────────────────────────────


async def test_a_secret_round_trips() -> None:
    vault = _vault()
    await vault.put("stripe", STRIPE)
    assert await vault.get("stripe") == STRIPE


async def test_the_stored_bytes_are_not_the_secret() -> None:
    store = InMemorySecretStore()
    vault = Vault(store=store, key=derive_key(KEY))
    await vault.put("stripe", STRIPE)

    blob = await store.get("stripe")
    assert blob is not None
    assert STRIPE.encode() not in blob


async def test_a_tampered_ciphertext_fails_loudly() -> None:
    """AEAD, not just encryption: edited bytes must not decrypt to garbage
    that something downstream then sends to Stripe."""
    store = InMemorySecretStore()
    vault = Vault(store=store, key=derive_key(KEY))
    await vault.put("stripe", STRIPE)

    blob = bytearray(await store.get("stripe") or b"")
    blob[-1] ^= 0xFF
    await store.put("stripe", bytes(blob))

    fresh = Vault(store=store, key=derive_key(KEY))
    with pytest.raises(VaultLockedError, match="could not be decrypted"):
        await fresh.get("stripe")


async def test_a_ciphertext_cannot_be_moved_to_another_name() -> None:
    """The name is authenticated, so swapping two secrets fails rather than
    silently handing the billing key to the mail client."""
    store = InMemorySecretStore()
    vault = Vault(store=store, key=derive_key(KEY))
    await vault.put("stripe", STRIPE)
    await store.put("mailgun", await store.get("stripe") or b"")

    fresh = Vault(store=store, key=derive_key(KEY))
    with pytest.raises(VaultLockedError):
        await fresh.get("mailgun")


async def test_a_different_key_cannot_read() -> None:
    store = InMemorySecretStore()
    await Vault(store=store, key=derive_key(KEY)).put("stripe", STRIPE)

    with pytest.raises(VaultLockedError):
        await Vault(store=store, key=derive_key(new_key())).get("stripe")


async def test_a_locked_vault_refuses_rather_than_storing_plaintext() -> None:
    """The wrong failure would be keeping it unencrypted "for now"."""
    vault = Vault(store=InMemorySecretStore())
    assert vault.locked
    with pytest.raises(VaultLockedError, match="no vault key"):
        await vault.put("stripe", STRIPE)


async def test_listing_secrets_never_returns_one() -> None:
    """There must be no shape of the API that hands back a plaintext."""
    vault = _vault()
    await vault.put("stripe", STRIPE)

    listed = await vault.names()
    payload = str([info.to_dict() for info in listed])
    assert STRIPE not in payload
    assert listed[0].hint == "NOT…21"
    assert listed[0].length == len(STRIPE)


def test_a_hint_is_too_short_to_use() -> None:
    assert hint_for("abc") == "•••"
    assert STRIPE not in hint_for(STRIPE)


async def test_a_deleted_secret_is_gone_from_memory_too() -> None:
    vault = _vault()
    await vault.put("stripe", STRIPE)
    assert await vault.delete("stripe") is True

    with pytest.raises(SecretNotFoundError):
        await vault.get("stripe")
    # And it stops being redacted, because it is no longer a secret.
    assert vault.redact(f"key={STRIPE}") == f"key={STRIPE}"


def test_a_passphrase_still_produces_a_usable_key() -> None:
    assert len(derive_key("correct horse battery staple")) == 32
    assert derive_key("a") != derive_key("b")


# ── Redaction: where secrets actually leak ────────────────────────────────────


async def test_redaction_scrubs_strings_dicts_and_lists() -> None:
    vault = _vault()
    await vault.put("stripe", STRIPE)

    assert vault.redact(f"Authorization: Bearer {STRIPE}") == f"Authorization: Bearer {REDACTED}"
    assert vault.redact({"headers": {"auth": STRIPE}}) == {"headers": {"auth": REDACTED}}
    assert vault.redact([STRIPE, "fine"]) == [REDACTED, "fine"]


async def test_redaction_leaves_short_secrets_alone() -> None:
    """A four-character secret would scrub half the English language."""
    vault = _vault()
    await vault.put("pin", "1234")
    assert vault.redact("the year 1234 was fine") == "the year 1234 was fine"


async def test_a_secret_never_read_is_still_redacted_after_load() -> None:
    """The most dangerous case: a secret stored last week, never fetched this
    process, appearing in a log line. Loading at boot is what covers it."""
    store = InMemorySecretStore()
    await Vault(store=store, key=derive_key(KEY)).put("stripe", STRIPE)

    fresh = Vault(store=store, key=derive_key(KEY))
    assert fresh.redact(STRIPE) == STRIPE, "not yet loaded — nothing to match against"

    assert await fresh.load() == 1
    assert fresh.redact(STRIPE) == REDACTED


# ── References: the model names a secret, never holds one ─────────────────────


async def test_a_reference_resolves_at_call_time() -> None:
    vault = _vault()
    await vault.put("stripe", STRIPE)

    resolved = await vault.resolve({"headers": {"auth": "Bearer ${vault:stripe}"}})
    assert resolved == {"headers": {"auth": f"Bearer {STRIPE}"}}


async def test_an_unknown_reference_raises_rather_than_blanking() -> None:
    """A request that silently loses its credential fails somewhere much more
    confusing than here."""
    with pytest.raises(SecretNotFoundError):
        await _vault().resolve("${vault:nope}")


async def test_the_audit_log_records_the_reference_not_the_secret(settings, clock) -> None:
    """The whole point of references: an audit trail you can keep."""
    vault = _vault()
    await vault.put("stripe", STRIPE)

    seen: list[dict] = []

    class Recorder:
        async def record(self, topic, payload, **kwargs):
            seen.append(payload)

        def entries(self, **kwargs):
            return []

    registry = ToolRegistry(
        audit=Recorder(), vault=vault, grants=[Grant("*", Permission.SENSITIVE)]
    )
    got: dict = {}

    async def charge(token: str) -> str:
        got["token"] = token
        return "ok"

    registry.register("charge", "Charge a card.", charge, permission=Permission.SENSITIVE)
    await registry.invoke("charge", {"token": "${vault:stripe}"})

    assert got["token"] == STRIPE, "the tool must receive the real value"
    assert STRIPE not in str(seen), "and the audit log must not"
    assert "${vault:stripe}" in str(seen)


async def test_a_tool_that_echoes_its_own_secret_is_redacted_on_the_bus() -> None:
    """Tools echo their requests constantly. This is the common leak."""
    bus = EventBus()
    subscription = bus.subscribe("tool.succeeded")
    vault = _vault()
    await vault.put("stripe", STRIPE)

    registry = ToolRegistry(bus=bus, vault=vault)
    registry.register("echo_it", "Echo.", lambda token: f"sent {token}")
    await registry.invoke("echo_it", {"token": "${vault:stripe}"})

    async with asyncio.timeout(2):
        event = await anext(subscription.events())
    assert STRIPE not in str(event.payload)
    assert REDACTED in event.payload["result_preview"]
    subscription.close()


async def test_an_error_quoting_the_secret_is_redacted() -> None:
    """The leak nobody writes a line of code for: an exception message."""
    bus = EventBus()
    subscription = bus.subscribe("tool.failed")
    vault = _vault()
    await vault.put("stripe", STRIPE)

    registry = ToolRegistry(bus=bus, vault=vault)

    def explode(token: str) -> str:
        raise RuntimeError(f"401 from api.stripe.com using {token}")

    registry.register("explode", "Fail.", explode)
    with pytest.raises(RuntimeError):
        await registry.invoke("explode", {"token": "${vault:stripe}"})

    async with asyncio.timeout(2):
        event = await anext(subscription.events())
    assert STRIPE not in str(event.payload)
    subscription.close()


# ── Cost governance ───────────────────────────────────────────────────────────


def test_periods_roll_on_wall_clock_boundaries() -> None:
    """ "This month" is what a person means and what an invoice says."""
    assert period_key(Period.DAY, datetime(2026, 3, 31, 23, 59, tzinfo=UTC)) == "2026-03-31"
    assert period_key(Period.MONTH, datetime(2026, 3, 31, 23, 59, tzinfo=UTC)) == "2026-03"
    assert period_key(Period.MONTH, datetime(2026, 4, 1, 0, 1, tzinfo=UTC)) == "2026-04"


def test_a_soft_ceiling_above_the_hard_one_is_rejected_at_boot() -> None:
    """Otherwise the first thing the user ever sees is a hard refusal."""
    with pytest.raises(ValueError, match="above the hard one"):
        Budget(Period.DAY, soft_usd=50.0, hard_usd=10.0)


def test_spend_rolls_over_at_the_period_boundary(clock: FrozenClock) -> None:
    ledger = Ledger(clock=clock)
    ledger.record(4.0)
    assert ledger.spent(Period.DAY) == 4.0

    clock.advance(60 * 60 * 48)
    assert ledger.spent(Period.DAY) == 0.0
    assert ledger.spent(Period.TOTAL) == 4.0


def test_an_unenforced_governor_allows_everything() -> None:
    governor = CostGovernor(budgets=(Budget(Period.DAY),))
    assert governor.enforced is False
    assert governor.assess(1_000_000.0).verdict is Verdict.ALLOW


def test_the_ceiling_is_checked_against_the_projection_not_the_spend(clock) -> None:
    """A ceiling consulted after the money is gone is a report."""
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.DAY, hard_usd=10.0),))
    governor.record(9.0)

    assert governor.assess(0.5).verdict is Verdict.ALLOW
    assert governor.assess(2.0).verdict is Verdict.REFUSE


def test_a_hard_refusal_wins_over_a_soft_one(clock) -> None:
    """Told "approve this" when the answer is "no", a user approves and is
    then confused."""
    governor = CostGovernor(
        Ledger(clock=clock),
        (Budget(Period.DAY, soft_usd=1.0, hard_usd=2.0), Budget(Period.MONTH, soft_usd=1.0)),
    )
    governor.record(1.5)

    assessment = governor.assess(1.0)
    assert assessment.verdict is Verdict.REFUSE
    assert "hard ceiling" in assessment.reason


def test_a_soft_ceiling_asks_rather_than_stopping(clock) -> None:
    governor = CostGovernor(
        Ledger(clock=clock), (Budget(Period.DAY, soft_usd=1.0, hard_usd=100.0),)
    )
    governor.record(0.9)

    assessment = governor.assess(0.5)
    assert assessment.verdict is Verdict.APPROVE
    assert "ceiling you set" in assessment.reason


# ── Governance, enforced where every call passes ──────────────────────────────


def _request() -> CompletionRequest:
    return CompletionRequest(messages=[Message(role=Role.USER, content="hello there")])


async def test_the_router_refuses_a_call_past_the_hard_ceiling(clock) -> None:
    """Enforced in the router because that is the one place agents, workflows,
    documents, voice and the arbiter all pass through."""
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, hard_usd=0.001),))
    governor.record(0.002)
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor)

    with pytest.raises(BudgetExceededError, match="hard ceiling"):
        async for _ in router.stream(_request()):
            pass


async def test_a_soft_ceiling_parks_for_a_human_and_proceeds_on_approval(clock) -> None:
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, soft_usd=0.001),))
    governor.record(0.002)
    approvals = ApprovalBroker(clock=clock)
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor, approvals=approvals)

    async def drain() -> list[str]:
        return [c.text async for c in router.stream(_request()) if c.text]

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)

    pending = [a for a in approvals.all() if a.state.value == "pending"]
    assert pending and pending[0].tool == "spend"
    await approvals.resolve(pending[0].id, approved=True)
    assert await task


async def test_a_denied_spend_stops_the_call(clock) -> None:
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, soft_usd=0.001),))
    governor.record(0.002)
    approvals = ApprovalBroker(clock=clock)
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor, approvals=approvals)

    async def drain() -> list[str]:
        return [c.text async for c in router.stream(_request())]

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    pending = [a for a in approvals.all() if a.state.value == "pending"]
    await approvals.resolve(pending[0].id, approved=False)

    with pytest.raises(BudgetExceededError, match="denied"):
        await task


async def test_a_soft_ceiling_with_no_approver_refuses(clock) -> None:
    """Spending money unasked is not the safe default."""
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, soft_usd=0.001),))
    governor.record(0.002)
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor)

    with pytest.raises(BudgetExceededError, match="no approver"):
        async for _ in router.stream(_request()):
            pass


async def test_actual_spend_is_recorded_not_the_estimate(clock) -> None:
    """The estimate is deliberately conservative; the ledger must not be."""
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, hard_usd=100.0),))
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor)

    async for _ in router.stream(_request()):
        pass

    # Echo is free, so a ledger holding the estimate would be non-zero here.
    assert governor.ledger.spent(Period.TOTAL) == 0.0
    assert governor.ledger.calls(Period.TOTAL) == 1


async def test_the_system_boots_with_governance_off_by_default(settings, clock) -> None:
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    assert system.governor.enforced is False
    assert system.vault.locked is True, "no key configured means locked, not plaintext"
