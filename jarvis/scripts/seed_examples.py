"""Seed a demo user with example memories, a project with tasks, and sample
automations so a fresh install has something to explore.

Usage:  python scripts/seed_examples.py
Creates (or reuses) demo@jarvis.local / demopassword123
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.automation.scheduler import next_run_after  # noqa: E402
from server.db import (  # noqa: E402
    Project, TaskItem, User, Workflow, SessionLocal, init_db, utcnow,
)
from server.memory.manager import memory_manager  # noqa: E402
from server.security import hash_password  # noqa: E402
from sqlalchemy import select  # noqa: E402

DEMO_EMAIL = "demo@jarvis.local"
DEMO_PASSWORD = "demopassword123"

EXAMPLE_MEMORIES = [
    ("profile", "My name is Tony and I'm a solo founder building AI products.", 0.95),
    ("business", "I run an e-commerce brand called Ember on Shopify selling home goods.", 0.85),
    ("goal", "Reach $50k MRR within 12 months across my product portfolio.", 0.9),
    ("preference", "I prefer concise, direct answers with concrete next steps.", 0.8),
    ("preference", "I write in a warm but no-nonsense tone; avoid corporate jargon.", 0.75),
    ("relationship", "My co-founder is Maya, who leads design and brand.", 0.7),
    ("decision", "Decided to focus on the AI OS product over the mobile app for Q3.", 0.7),
    ("lesson", "Launching without a waitlist last time hurt momentum — always build anticipation first.", 0.7),
    ("skill", "Strong at product and marketing; weaker at backend infrastructure.", 0.6),
    ("style", "Emails should open with the ask, then context — never bury the lede.", 0.65),
]

EXAMPLE_TASKS = [
    ("Draft the JARVIS landing page copy", "marketing", 1, "in_progress"),
    ("Set up the waitlist and referral flow", "automation", 2, "todo"),
    ("Write launch announcement thread", "social", 2, "todo"),
    ("Model 12-month revenue projection", "finance", 3, "todo"),
    ("Competitive research on AI assistants", "research", 3, "done"),
]

EXAMPLE_WORKFLOWS = [
    ("Morning briefing", "Summarize my open tasks, flag anything due today, and propose my top 3 priorities.",
     "0 8 * * *", "assistant"),
    ("Weekly business review", "Review progress toward $50k MRR goal and suggest three growth experiments for next week.",
     "0 17 * * 5", "ceo"),
    ("Competitor watch", "Search for news about AI personal assistant products launched this week and summarize what's notable.",
     "0 9 * * 1", "research"),
]


async def main():
    await init_db()
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=DEMO_EMAIL, name="Tony (Demo)",
                password_hash=hash_password(DEMO_PASSWORD), role="owner",
                preferences={"display_name": "Tony"},
            )
            session.add(user)
            await session.commit()
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Reusing demo user: {DEMO_EMAIL}")

        for kind, content, importance in EXAMPLE_MEMORIES:
            await memory_manager.remember(
                session, user.id, content, kind=kind, source="seed", importance=importance
            )
        print(f"Seeded {len(EXAMPLE_MEMORIES)} memories")

        project = Project(user_id=user.id, name="JARVIS Launch", description="Bring the AI OS to market.")
        session.add(project)
        await session.commit()
        for title, agent, prio, status in EXAMPLE_TASKS:
            session.add(TaskItem(
                user_id=user.id, project_id=project.id, title=title,
                assignee_agent=agent, priority=prio, status=status,
                completed_at=utcnow() if status == "done" else None,
            ))
        await session.commit()
        print(f"Seeded project 'JARVIS Launch' with {len(EXAMPLE_TASKS)} tasks")

        for name, prompt, schedule, agent in EXAMPLE_WORKFLOWS:
            session.add(Workflow(
                user_id=user.id, name=name, prompt=prompt, schedule=schedule,
                agent=agent, next_run_at=next_run_after(schedule, utcnow()),
            ))
        await session.commit()
        print(f"Seeded {len(EXAMPLE_WORKFLOWS)} automations")
        print("\nDone. Log in with the demo credentials to explore.")


if __name__ == "__main__":
    asyncio.run(main())
