"""The four tables the first ten clients need.

Deliberately small. Every field here exists because a specific thing in
`docs/12-FOUNDER-LED-ACQUISITION.md` has to be recorded, and nothing is here in
anticipation of a client we do not have.

The one design choice worth explaining: **a completed task is an effort-ledger
entry**. They were separate in the plan and collapsing them means the ledger
fills itself as a by-product of doing the work rather than as a second admin
job — which is the only version of a time log that survives a busy fortnight.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# Where a client is in the pipeline. Ordered as they progress.
STATUSES = (
    "prospect",  # identified, not yet spoken to
    "conversation",  # had the 30-minute call
    "audit",  # bought the £1,500 audit
    "active",  # paying monthly
    "churned",  # was paying, stopped
    "disqualified",  # we said no, or they failed a gate
    "no_trigger",  # good fit, no deadline. Log and revisit
)
LIVE_STATUSES = ("prospect", "conversation", "audit", "active")

# The seven buying triggers. A prospect with none has no deadline.
TRIGGERS = (
    "finance_hire",
    "agency_ending",
    "scaling_failed",
    "tracking_broke",
    "staff_left",
    "funding_or_pressure",
    "peak_season",
    "none",
)

INTERACTION_KINDS = (
    "outreach",
    "discovery_call",
    "audit_review",
    "weekly",
    "monthly_review",
    "exit_interview",
    "note",
)

# The discovery log, made structural. `language_*` are captured verbatim and
# become copy; the rest drive the rule of three.
EVIDENCE_KINDS = (
    "pain",
    "objection",
    "request",
    "language_problem",
    "language_value",
    "churn_reason",
    "surprise",
)

# Why a task was manual. Only B is ever sorted by hours for automation.
EFFORT_CATEGORIES = ("A", "B", "C")


class Client(Base):
    """A prospect or a client. Same table — the pipeline is a status field."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str] = mapped_column(String(300), default="")
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    contact_phone: Mapped[str] = mapped_column(String(60), default="")

    industry: Mapped[str] = mapped_column(String(120), default="")
    revenue_band: Mapped[str] = mapped_column(String(60), default="")
    spend_band: Mapped[str] = mapped_column(String(60), default="")

    status: Mapped[str] = mapped_column(String(32), default="prospect", index=True)
    trigger: Mapped[str] = mapped_column(String(40), default="none")
    source: Mapped[str] = mapped_column(String(120), default="")

    audit_fee: Mapped[int | None] = mapped_column(Integer)
    monthly_fee: Mapped[int | None] = mapped_column(Integer)

    # What happens next, and when. This drives the attention list, so it is the
    # one field that is never allowed to go stale on a live client.
    next_action: Mapped[str] = mapped_column(String(300), default="")
    next_action_due: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    audit_started_on: Mapped[date | None] = mapped_column(Date)
    active_since: Mapped[date | None] = mapped_column(Date)
    churned_on: Mapped[date | None] = mapped_column(Date)
    churn_reason: Mapped[str] = mapped_column(Text, default="")

    # Reconciliation confidence from the audit. Below 0.9 we do not proceed —
    # `11-FIRST-TEN.md §3`. Stored so the gate is visible, not remembered.
    reconciliation_confidence: Mapped[float | None] = mapped_column()

    notes: Mapped[str] = mapped_column(Text, default="")

    interactions: Mapped[list[Interaction]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="client", cascade="all, delete-orphan")

    @property
    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES


class Interaction(Base):
    """One conversation. `verbatim` is the point of this table.

    `summary` is for scanning later; `verbatim` is what they actually said, and
    it is never paraphrased at capture time — paraphrasing destroys the language
    and the language is the product.
    """

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="note", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default="")
    verbatim: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client] = relationship(back_populates="interactions")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="interaction")


class Evidence(Base):
    """Something a customer said, kept in their words.

    Captured verbatim, categorised only by `kind` — which is coarse on purpose.
    Finer grouping happens weekly, by `patterns.cluster`, over the raw text.
    """

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    interaction_id: Mapped[int | None] = mapped_column(ForeignKey("interactions.id"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")

    # Only meaningful for `request`: a feature nobody would pay for is a
    # conversation, not a requirement.
    would_pay: Mapped[bool | None] = mapped_column(Boolean)
    # Only meaningful for `objection`: the ones we answered badly are the
    # useful ones, so they have to be recordable as such.
    answered_well: Mapped[bool | None] = mapped_column(Boolean)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client] = relationship(back_populates="evidence")
    interaction: Mapped[Interaction | None] = relationship(back_populates="evidence")


class Task(Base):
    """Work to do, and — once done — the effort-ledger entry for having done it.

    `minutes` and `category` are set on completion. That is the whole trick:
    the ledger cannot drift from reality because it is the same object.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    activity: Mapped[str] = mapped_column(String(60), default="")
    due_on: Mapped[date | None] = mapped_column(Date, index=True)

    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    minutes: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(1))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client | None] = relationship(back_populates="tasks")

    @property
    def is_done(self) -> bool:
        return self.done_at is not None
