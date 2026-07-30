"""Phoenix internal operations.

Server-rendered HTML, forms, redirects. No build step, no client-side state, no
API to keep in sync with a UI. Two people use this; it needs to be instant to
change and impossible to break, and that is worth more than any amount of
front-end sophistication.

Every mutation is POST → redirect, so a refresh never re-submits.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ops import attention, db, patterns, repo
from ops.models import (
    EVIDENCE_KINDS,
    INTERACTION_KINDS,
    STATUSES,
    TRIGGERS,
    Client,
    Evidence,
    Interaction,
    Task,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _today() -> date:
    return datetime.now(UTC).date()


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def _float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _bool3(value: str | None) -> bool | None:
    """Tri-state from a select: yes / no / unknown."""
    return {"yes": True, "no": False}.get(value or "")


def create_app(url: str | None = None) -> FastAPI:
    db.configure(url)
    app = FastAPI(title="Phoenix Ops", docs_url="/api/docs")

    def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request, name, {"today": _today(), "statuses": STATUSES, **ctx}
        )

    # ---------------------------------------------------------------- dashboard

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        with db.session() as s:
            clients = list(repo.clients(s))
            interactions = list(repo.interactions(s, limit=2000))
            tasks = list(repo.tasks(s))
            today = _today()
            clusters = patterns.cluster(repo.evidence_rows(s))
            return page(
                request,
                "dashboard.html",
                attention=attention.review(clients, interactions, tasks, today),
                loose_tasks=attention.unassigned_overdue(tasks, today),
                funnel=attention.funnel(clients),
                effort=attention.effort_by_category(tasks),
                candidates=attention.automation_candidates(tasks),
                findings=patterns.findings(clusters)[:6],
                recent=repo.evidence(s, limit=8),
                names=repo.client_names(s),
                clients=clients,
            )

    # ------------------------------------------------------------------ clients

    @app.get("/clients", response_class=HTMLResponse)
    def client_list(request: Request, status: str | None = None) -> HTMLResponse:
        with db.session() as s:
            return page(
                request,
                "clients.html",
                clients=repo.clients(s, status=status),
                filter_status=status,
                triggers=TRIGGERS,
            )

    @app.post("/clients")
    def client_create(
        name: str = Form(...),
        website: str = Form(""),
        contact_name: str = Form(""),
        contact_email: str = Form(""),
        industry: str = Form(""),
        revenue_band: str = Form(""),
        spend_band: str = Form(""),
        trigger: str = Form("none"),
        source: str = Form(""),
        status: str = Form("prospect"),
    ) -> RedirectResponse:
        with db.session() as s:
            client = Client(
                name=name.strip(),
                website=website.strip(),
                contact_name=contact_name.strip(),
                contact_email=contact_email.strip(),
                industry=industry.strip(),
                revenue_band=revenue_band.strip(),
                spend_band=spend_band.strip(),
                trigger=trigger,
                source=source.strip(),
                status=status,
            )
            s.add(client)
            s.flush()
            return RedirectResponse(f"/clients/{client.id}", status_code=303)

    @app.get("/clients/{client_id}", response_class=HTMLResponse)
    def client_detail(request: Request, client_id: int) -> HTMLResponse:
        with db.session() as s:
            client = repo.client(s, client_id)
            if client is None:
                return HTMLResponse("Not found", status_code=404)
            return page(
                request,
                "client.html",
                client=client,
                timeline=repo.timeline(s, client_id),
                open_tasks=[t for t in repo.tasks(s, client_id=client_id, open_only=True)],
                kinds=INTERACTION_KINDS,
                evidence_kinds=EVIDENCE_KINDS,
                triggers=TRIGGERS,
            )

    @app.post("/clients/{client_id}")
    def client_update(
        client_id: int,
        status: str = Form(...),
        trigger: str = Form("none"),
        next_action: str = Form(""),
        next_action_due: str = Form(""),
        audit_fee: str = Form(""),
        monthly_fee: str = Form(""),
        audit_started_on: str = Form(""),
        active_since: str = Form(""),
        churned_on: str = Form(""),
        churn_reason: str = Form(""),
        reconciliation_confidence: str = Form(""),
        notes: str = Form(""),
    ) -> RedirectResponse:
        with db.session() as s:
            client = repo.client(s, client_id)
            if client is None:
                return RedirectResponse("/clients", status_code=303)
            client.status = status
            client.trigger = trigger
            client.next_action = next_action.strip()
            client.next_action_due = _date(next_action_due)
            client.audit_fee = _int(audit_fee)
            client.monthly_fee = _int(monthly_fee)
            client.audit_started_on = _date(audit_started_on)
            client.active_since = _date(active_since)
            client.churned_on = _date(churned_on)
            client.churn_reason = churn_reason.strip()
            client.reconciliation_confidence = _float(reconciliation_confidence)
            client.notes = notes
            return RedirectResponse(f"/clients/{client_id}", status_code=303)

    # ------------------------------------------------------------- interactions

    @app.post("/clients/{client_id}/interactions")
    def interaction_create(
        client_id: int,
        kind: str = Form("note"),
        occurred_on: str = Form(""),
        summary: str = Form(""),
        verbatim: str = Form(""),
    ) -> RedirectResponse:
        with db.session() as s:
            when = _date(occurred_on)
            occurred = (
                datetime.combine(when, datetime.min.time(), tzinfo=UTC)
                if when
                else datetime.now(UTC)
            )
            s.add(
                Interaction(
                    client_id=client_id,
                    kind=kind,
                    occurred_at=occurred,
                    summary=summary.strip(),
                    verbatim=verbatim,
                )
            )
            return RedirectResponse(f"/clients/{client_id}", status_code=303)

    # ----------------------------------------------------------------- evidence

    @app.post("/clients/{client_id}/evidence")
    def evidence_create(
        client_id: int,
        kind: str = Form(...),
        verbatim: str = Form(...),
        note: str = Form(""),
        would_pay: str = Form(""),
        answered_well: str = Form(""),
    ) -> RedirectResponse:
        with db.session() as s:
            s.add(
                Evidence(
                    client_id=client_id,
                    kind=kind,
                    verbatim=verbatim.strip(),
                    note=note.strip(),
                    would_pay=_bool3(would_pay),
                    answered_well=_bool3(answered_well),
                )
            )
            return RedirectResponse(f"/clients/{client_id}", status_code=303)

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence_view(request: Request, kind: str | None = None) -> HTMLResponse:
        with db.session() as s:
            clusters = patterns.cluster(repo.evidence_rows(s, kind))
            return page(
                request,
                "evidence.html",
                clusters=clusters,
                findings=patterns.findings(clusters),
                kinds=EVIDENCE_KINDS,
                filter_kind=kind,
                names=repo.client_names(s),
                items=repo.evidence(s, kind=kind),
            )

    # -------------------------------------------------------------------- tasks

    @app.get("/tasks", response_class=HTMLResponse)
    def task_list(request: Request) -> HTMLResponse:
        with db.session() as s:
            all_tasks = list(repo.tasks(s))
            return page(
                request,
                "tasks.html",
                open_tasks=[t for t in all_tasks if not t.is_done],
                done_tasks=[t for t in all_tasks if t.is_done][:40],
                effort=attention.effort_by_category(all_tasks),
                candidates=attention.automation_candidates(all_tasks, limit=10),
                clients=repo.clients(s),
                names=repo.client_names(s),
            )

    @app.post("/tasks")
    def task_create(
        title: str = Form(...),
        client_id: str = Form(""),
        detail: str = Form(""),
        activity: str = Form(""),
        due_on: str = Form(""),
    ) -> RedirectResponse:
        with db.session() as s:
            s.add(
                Task(
                    title=title.strip(),
                    client_id=_int(client_id),
                    detail=detail.strip(),
                    activity=activity.strip(),
                    due_on=_date(due_on),
                )
            )
        return RedirectResponse("/tasks", status_code=303)

    @app.post("/tasks/{task_id}/done")
    def task_done(
        task_id: int,
        minutes: str = Form(...),
        category: str = Form(...),
        activity: str = Form(""),
        back: str = Form("/tasks"),
    ) -> RedirectResponse:
        """Completing a task *is* the effort-ledger entry. One object, two jobs."""
        with db.session() as s:
            task = s.get(Task, task_id)
            if task is not None:
                task.done_at = datetime.now(UTC)
                task.minutes = _int(minutes)
                task.category = category
                if activity.strip():
                    task.activity = activity.strip()
        return RedirectResponse(back, status_code=303)

    # ------------------------------------------------------------------- search

    @app.get("/search", response_class=HTMLResponse)
    def search_view(request: Request, q: str = "") -> HTMLResponse:
        with db.session() as s:
            return page(
                request, "search.html", q=q, results=repo.search(s, q), names=repo.client_names(s)
            )

    # --------------------------------------------------------------------- json
    # A thin read-only mirror. Nothing consumes it yet; it exists so a script or
    # a future dashboard never has to scrape HTML.

    @app.get("/api/attention")
    def api_attention() -> JSONResponse:
        with db.session() as s:
            items = attention.review(
                list(repo.clients(s)),
                list(repo.interactions(s, limit=2000)),
                list(repo.tasks(s)),
                _today(),
            )
            return JSONResponse(
                [
                    {
                        "client_id": a.client_id,
                        "client": a.client_name,
                        "reason": a.reason,
                        "severity": a.label,
                        "days": a.days,
                    }
                    for a in items
                ]
            )

    @app.get("/api/findings")
    def api_findings() -> JSONResponse:
        with db.session() as s:
            names = repo.client_names(s)
            found = patterns.findings(patterns.cluster(repo.evidence_rows(s)))
            return JSONResponse(
                [
                    {
                        "kind": c.kind,
                        "label": c.label,
                        "clients": sorted(names.get(i, str(i)) for i in c.clients),
                        "statements": [t for _, _, t in c.members],
                    }
                    for c in found
                ]
            )

    @app.get("/api/health")
    def api_health() -> dict[str, Any]:
        with db.session() as s:
            clients = list(repo.clients(s))
            return {
                "status": "ok",
                "clients": len(clients),
                "paying": sum(1 for c in clients if c.status == "active"),
                "funnel": attention.funnel(clients),
            }

    return app


app = create_app()
