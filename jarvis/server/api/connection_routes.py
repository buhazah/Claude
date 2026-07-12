"""Account-connection routes: OAuth authorize, callback, list, disconnect."""
from __future__ import annotations

import html

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import Connection, User, get_session
from ..integrations.oauth import (
    PROVIDERS, OAuthError, authorize_url, exchange_code, sign_state,
    store_tokens, verify_state,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _base_url(request: Request) -> str:
    if settings.public_url:
        return settings.public_url
    # Respect proxy-forwarded scheme/host (Render/Railway terminate TLS).
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}"


def _redirect_uri(request: Request, provider: str) -> str:
    return f"{_base_url(request)}/api/connections/{provider}/callback"


@router.get("")
async def list_connections(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.execute(select(Connection).where(Connection.user_id == user.id))
    ).scalars().all()
    connected = {c.provider: c for c in rows}
    out = []
    for key, p in PROVIDERS.items():
        c = connected.get(key)
        out.append({
            "provider": key,
            "name": p.name,
            "configured": p.configured,   # app credentials present (can connect)
            "connected": c is not None,
            "account": c.account_label if c else "",
        })
    return {"connections": out}


@router.get("/{provider}/authorize")
async def start_authorize(
    provider: str, request: Request, user: User = Depends(get_current_user)
):
    p = PROVIDERS.get(provider)
    if p is None:
        return {"error": "unknown provider"}
    if not p.configured:
        return {"error": f"{p.name} is not set up on this server yet. "
                         "An admin must add its client credentials — see docs/INTEGRATIONS.md."}
    state = sign_state(user.id, provider)
    url = authorize_url(provider, _redirect_uri(request, provider), state)
    return {"url": url}


async def _fetch_label(provider: str, access_token: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if provider in ("google", "gmail"):
                r = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return r.json().get("email", "") if r.status_code == 200 else ""
            if provider == "spotify":
                r = await client.get(
                    "https://api.spotify.com/v1/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if r.status_code == 200:
                    d = r.json()
                    return d.get("display_name") or d.get("id", "")
    except Exception:
        pass
    return ""


def _result_page(title: str, message: str) -> HTMLResponse:
    # title/message may contain provider- or attacker-supplied text (e.g. the
    # OAuth `error` query param), so escape before interpolating into HTML.
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{safe_title}</title>
<style>body{{font-family:system-ui,sans-serif;background:#17130d;color:#eee4d2;
display:grid;place-items:center;height:100vh;margin:0;text-align:center}}
.card{{max-width:420px;padding:40px}}h1{{color:#d6af69;font-weight:500}}
a{{color:#d6af69}}</style></head><body><div class="card">
<h1>{safe_title}</h1><p>{safe_message}</p>
<p><a href="/">Return to JARVIS →</a></p>
<script>setTimeout(function(){{try{{window.close()}}catch(e){{}}}}, 2500)</script>
</div></body></html>"""
    return HTMLResponse(page)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request,
    code: str = "", state: str = "", error: str = "",
    session: AsyncSession = Depends(get_session),
):
    if error:
        return _result_page("Connection cancelled", f"The provider returned: {error}. You can close this tab.")
    try:
        user_id, state_provider = verify_state(state)
        if state_provider != provider:
            raise OAuthError("provider mismatch")
        tokens = await exchange_code(provider, code, _redirect_uri(request, provider))
        label = await _fetch_label(provider, tokens.get("access_token", ""))
        await store_tokens(session, user_id, provider, tokens, account_label=label)
    except OAuthError as exc:
        return _result_page("Connection failed", f"{exc}. Please try again from Settings.")
    name = PROVIDERS[provider].name
    who = f" as {label}" if label else ""
    return _result_page(f"{name} connected", f"JARVIS is now linked to your {name}{who}. You can close this tab.")


@router.delete("/{provider}")
async def disconnect(
    provider: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    row = (
        await session.execute(
            select(Connection).where(Connection.user_id == user.id, Connection.provider == provider)
        )
    ).scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()
    return {"disconnected": provider}
