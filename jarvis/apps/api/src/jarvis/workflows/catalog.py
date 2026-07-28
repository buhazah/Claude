"""Starter workflows.

Three, chosen to exercise the shapes the engine supports rather than to be
exhaustive: a linear chain, a branch with an approval, and a fan-out. They are
seeded on first boot so the builder opens onto something real, and they are
ordinary data a user can edit or delete.
"""

from __future__ import annotations

from jarvis.workflows.models import (
    Condition,
    Operator,
    StepKind,
    Workflow,
    WorkflowStep,
)


def starter_workflows() -> list[Workflow]:
    return [
        Workflow(
            id="wfl_inbox_triage",
            name="Inbox triage",
            description=(
                "Summarise an incoming message, decide whether it needs a reply, "
                "draft one, and hold it for approval before sending."
            ),
            inputs=["body", "from"],
            steps=[
                WorkflowStep(
                    id="summarise",
                    kind=StepKind.AGENT,
                    label="Summarise the message",
                    agent="email",
                    prompt="Summarise this message in two sentences:\n\n{{ trigger.body }}",
                ),
                WorkflowStep(
                    id="classify",
                    kind=StepKind.AGENT,
                    label="Does it need a reply?",
                    agent="email",
                    prompt=(
                        "Reply with exactly one word — REPLY or IGNORE — for whether this "
                        "needs a response:\n\n{{ steps.summarise.output }}"
                    ),
                ),
                WorkflowStep(
                    id="needs_reply",
                    kind=StepKind.BRANCH,
                    label="Needs a reply?",
                    condition=Condition(
                        field="steps.classify.output", op=Operator.CONTAINS, value="reply"
                    ),
                    if_true="draft",
                    if_false="done",
                ),
                WorkflowStep(
                    id="draft",
                    kind=StepKind.AGENT,
                    label="Draft a reply",
                    agent="email",
                    prompt=(
                        "Draft a reply in the user's voice to:\n\n{{ trigger.body }}\n\n"
                        "Summary: {{ steps.summarise.output }}"
                    ),
                ),
                WorkflowStep(
                    id="approve",
                    kind=StepKind.APPROVAL,
                    label="Send this reply?",
                    question="Send this draft?\n\n{{ steps.draft.output }}",
                    if_false="done",
                ),
                WorkflowStep(
                    id="done",
                    kind=StepKind.NOTE,
                    label="Triage complete for {{ trigger.from }}",
                    terminal=True,
                ),
            ],
        ),
        Workflow(
            id="wfl_company_brief",
            name="Company brief",
            description="Research a company from several angles at once, then write it up.",
            inputs=["company"],
            steps=[
                WorkflowStep(
                    id="gather",
                    kind=StepKind.PARALLEL,
                    label="Research in parallel",
                    steps=["market", "finances"],
                ),
                WorkflowStep(
                    id="market",
                    kind=StepKind.AGENT,
                    label="Market position",
                    agent="research",
                    prompt="Research the market position of {{ trigger.company }}.",
                ),
                WorkflowStep(
                    id="finances",
                    kind=StepKind.AGENT,
                    label="Financial picture",
                    agent="financial_analyst",
                    prompt="Summarise what is known about {{ trigger.company }}'s finances.",
                ),
                WorkflowStep(
                    id="write",
                    kind=StepKind.AGENT,
                    label="Write the brief",
                    agent="research",
                    prompt=(
                        "Write a one-page brief on {{ trigger.company }} from these notes:\n\n"
                        "Market: {{ steps.market.output }}\n\nFinances: {{ steps.finances.output }}"
                    ),
                ),
            ],
        ),
        Workflow(
            id="wfl_weekly_review",
            name="Weekly review",
            description="Look back at the week's runs and goals, then plan the next one.",
            steps=[
                WorkflowStep(
                    id="review",
                    kind=StepKind.AGENT,
                    label="Review the week",
                    agent="life_coach",
                    prompt="Review my week against my stated goals and name what slipped.",
                ),
                WorkflowStep(
                    id="plan",
                    kind=StepKind.AGENT,
                    label="Plan the next one",
                    agent="planner",
                    prompt="Given this review, plan next week:\n\n{{ steps.review.output }}",
                ),
            ],
        ),
    ]
