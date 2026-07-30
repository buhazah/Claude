"""The routes, driven the way a founder drives them: forms and redirects."""

from __future__ import annotations

from datetime import date, timedelta

from ops import db, repo


def _add_client(client, name="Northbound", **form):
    response = client.post("/clients", data={"name": name, **form}, follow_redirects=False)
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[1])


def test_dashboard_is_honest_when_empty(client):
    body = client.get("/").text
    assert "Nothing is overdue" in body
    assert "nothing is being recorded" in body


def test_create_and_view_a_client(client):
    client_id = _add_client(
        client, industry="apparel", spend_band="£20k/mo", trigger="agency_ending"
    )
    page = client.get(f"/clients/{client_id}").text
    assert "Northbound" in page
    assert "£20k/mo" in page
    assert client.get("/clients").text.count("Northbound") >= 1


def test_client_list_filters_by_status(client):
    _add_client(client, name="Alpha", status="prospect")
    _add_client(client, name="Beta", status="active")
    assert "Alpha" in client.get("/clients?status=prospect").text
    assert "Beta" not in client.get("/clients?status=prospect").text


def test_logging_a_conversation_keeps_the_verbatim(client):
    client_id = _add_client(client)
    quote = "the platform says 4x and my bank account disagrees"
    client.post(
        f"/clients/{client_id}/interactions",
        data={"kind": "discovery_call", "summary": "first call", "verbatim": quote},
        follow_redirects=False,
    )
    page = client.get(f"/clients/{client_id}").text
    assert quote in page
    assert "first call" in page


def test_evidence_capture_records_the_qualifiers(client):
    client_id = _add_client(client)
    client.post(
        f"/clients/{client_id}/evidence",
        data={
            "kind": "objection",
            "verbatim": "you have no case studies",
            "note": "fumbled this",
            "answered_well": "no",
        },
        follow_redirects=False,
    )
    with db.session() as s:
        item = repo.evidence(s)[0]
        assert item.answered_well is False
        assert item.would_pay is None
    assert "answered badly" in client.get("/evidence").text


def test_request_without_a_pay_answer_stays_unknown(client):
    client_id = _add_client(client)
    client.post(
        f"/clients/{client_id}/evidence",
        data={"kind": "request", "verbatim": "can you do TikTok too"},
        follow_redirects=False,
    )
    with db.session() as s:
        assert repo.evidence(s)[0].would_pay is None


def test_updating_status_and_next_action(client):
    client_id = _add_client(client)
    due = (date.today() + timedelta(days=2)).isoformat()
    client.post(
        f"/clients/{client_id}",
        data={
            "status": "audit",
            "trigger": "finance_hire",
            "next_action": "deliver the audit",
            "next_action_due": due,
            "reconciliation_confidence": "0.94",
        },
        follow_redirects=False,
    )
    with db.session() as s:
        record = repo.client(s, client_id)
        assert record.status == "audit"
        assert record.next_action == "deliver the audit"
        assert record.reconciliation_confidence == 0.94


def test_blank_numeric_fields_stay_null(client):
    client_id = _add_client(client)
    client.post(
        f"/clients/{client_id}",
        data={"status": "prospect", "monthly_fee": "", "reconciliation_confidence": ""},
        follow_redirects=False,
    )
    with db.session() as s:
        record = repo.client(s, client_id)
        assert record.monthly_fee is None
        assert record.reconciliation_confidence is None


def test_completing_a_task_writes_the_effort_entry(client):
    client_id = _add_client(client)
    client.post(
        "/tasks",
        data={"title": "write the report", "client_id": str(client_id), "activity": "report_edit"},
        follow_redirects=False,
    )
    with db.session() as s:
        task_id = repo.tasks(s)[0].id
    client.post(
        f"/tasks/{task_id}/done",
        data={"minutes": "45", "category": "B"},
        follow_redirects=False,
    )
    with db.session() as s:
        task = repo.tasks(s)[0]
        assert task.is_done
        assert task.minutes == 45
        assert task.category == "B"
    assert "report_edit" in client.get("/tasks").text


def test_task_completion_returns_where_it_came_from(client):
    client_id = _add_client(client)
    client.post(
        "/tasks", data={"title": "call them", "client_id": str(client_id)}, follow_redirects=False
    )
    with db.session() as s:
        task_id = repo.tasks(s)[0].id
    response = client.post(
        f"/tasks/{task_id}/done",
        data={"minutes": "10", "category": "A", "back": f"/clients/{client_id}"},
        follow_redirects=False,
    )
    assert response.headers["location"] == f"/clients/{client_id}"


def test_timeline_merges_everything_newest_first(client):
    client_id = _add_client(client)
    client.post(
        f"/clients/{client_id}/interactions",
        data={"kind": "note", "summary": "kickoff"},
        follow_redirects=False,
    )
    client.post(
        f"/clients/{client_id}/evidence",
        data={"kind": "pain", "verbatim": "flying blind"},
        follow_redirects=False,
    )
    with db.session() as s:
        events = repo.timeline(s, client_id)
    assert {kind for _, kind, _ in events} == {"interaction", "evidence"}
    assert events == sorted(events, key=lambda e: e[0], reverse=True)


def test_rule_of_three_surfaces_on_the_dashboard(client):
    for i in range(3):
        cid = _add_client(client, name=f"Brand {i}")
        client.post(
            f"/clients/{cid}/evidence",
            data={"kind": "pain", "verbatim": "I don't know what's working"},
            follow_redirects=False,
        )
    body = client.get("/").text
    # Jinja escapes both apostrophes, so match on the part that survives intact.
    assert "know what&#39;s working" in body
    assert "3 clients" in body


def test_two_clients_is_not_yet_a_finding(client):
    for i in range(2):
        cid = _add_client(client, name=f"Brand {i}")
        client.post(
            f"/clients/{cid}/evidence",
            data={"kind": "pain", "verbatim": "creative is stale"},
            follow_redirects=False,
        )
    assert "Nothing yet said by three different clients" in client.get("/evidence").text


def test_search_reaches_verbatim_text(client):
    client_id = _add_client(client)
    client.post(
        f"/clients/{client_id}/interactions",
        data={"kind": "discovery_call", "verbatim": "we tried to scale and CAC fell apart"},
        follow_redirects=False,
    )
    assert "CAC fell apart" in client.get("/search?q=CAC").text


def test_search_with_no_query_is_not_an_error(client):
    assert client.get("/search").status_code == 200


def test_attention_api_matches_the_page(client):
    client_id = _add_client(client, status="conversation")
    payload = client.get("/api/attention").json()
    assert payload[0]["client_id"] == client_id
    assert payload[0]["severity"] == "urgent"


def test_findings_api_names_the_clients(client):
    for i in range(3):
        cid = _add_client(client, name=f"Brand {i}")
        client.post(
            f"/clients/{cid}/evidence",
            data={"kind": "pain", "verbatim": "no idea what is working"},
            follow_redirects=False,
        )
    findings = client.get("/api/findings").json()
    assert len(findings) == 1
    assert sorted(findings[0]["clients"]) == ["Brand 0", "Brand 1", "Brand 2"]


def test_health_counts_paying_clients(client):
    _add_client(client, name="Alpha", status="active")
    _add_client(client, name="Beta", status="prospect")
    health = client.get("/api/health").json()
    assert health["paying"] == 1
    assert health["clients"] == 2


def test_missing_client_is_a_404(client):
    assert client.get("/clients/999").status_code == 404


def test_day_five_gate_is_visible_on_the_dashboard(client):
    client_id = _add_client(client)
    started = (date.today() - timedelta(days=7)).isoformat()
    client.post(
        f"/clients/{client_id}",
        data={"status": "audit", "audit_started_on": started},
        follow_redirects=False,
    )
    assert "reconciliation not recorded" in client.get("/").text
