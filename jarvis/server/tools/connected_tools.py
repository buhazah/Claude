"""Account-connected tools: Google Calendar, Spotify, Gmail.

Each reads the current user's stored OAuth token (via the execution
contextvar) and calls the provider API. If the account isn't connected the
tool returns a friendly message telling the user to connect it in Settings.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import httpx

from ..integrations.context import get_current_user_id
from ..integrations.oauth import OAuthError, get_access_token
from .base import ToolParam, tool


async def _token(provider: str) -> tuple[str | None, str]:
    """Return (access_token, error_message). One will be truthy."""
    user_id = get_current_user_id()
    if not user_id:
        return None, "No user context available."
    try:
        return await get_access_token(user_id, provider), ""
    except OAuthError as exc:
        return None, f"{exc}. Connect it under Settings → Connections."


# ------------------------------------------------------------- Google Calendar

@tool(
    "calendar_list_events",
    "List the user's upcoming Google Calendar events for the next N days.",
    [ToolParam("days", "integer", "How many days ahead to look (1-30)", required=False)],
    timeout=25,
)
async def calendar_list_events(days: int = 7) -> str:
    token, err = await _token("google")
    if err:
        return err
    days = max(1, min(int(days), 30))
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(days=days)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime", "maxResults": 20,
            },
        )
    if resp.status_code != 200:
        return f"Calendar error ({resp.status_code}): {resp.text[:200]}"
    items = resp.json().get("items", [])
    if not items:
        return f"No events in the next {days} days."
    lines = [f"Upcoming events (next {days} days):"]
    for ev in items:
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "")
        lines.append(f"  • {start} — {ev.get('summary', '(no title)')}")
    return "\n".join(lines)


@tool(
    "calendar_create_event",
    "Create a Google Calendar event. Times must be ISO 8601 "
    "(e.g. 2026-07-12T19:00:00). Includes the user's timezone automatically.",
    [
        ToolParam("title", "string", "Event title"),
        ToolParam("start", "string", "Start time, ISO 8601"),
        ToolParam("end", "string", "End time, ISO 8601"),
        ToolParam("description", "string", "Optional details", required=False),
    ],
    timeout=25,
)
async def calendar_create_event(title: str, start: str, end: str, description: str = "") -> str:
    token, err = await _token("google")
    if err:
        return err
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
    if resp.status_code not in (200, 201):
        return f"Couldn't create the event ({resp.status_code}): {resp.text[:200]}"
    link = resp.json().get("htmlLink", "")
    return f"Created '{title}' from {start} to {end}. {link}"


# --------------------------------------------------------------------- Spotify

@tool(
    "spotify_now_playing",
    "Show what the user is currently playing on Spotify.",
    [],
    timeout=20,
)
async def spotify_now_playing() -> str:
    token, err = await _token("spotify")
    if err:
        return err
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code == 204:
        return "Nothing is playing right now."
    if resp.status_code != 200:
        return f"Spotify error ({resp.status_code}): {resp.text[:200]}"
    data = resp.json()
    item = data.get("item") or {}
    name = item.get("name", "unknown")
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    state = "playing" if data.get("is_playing") else "paused"
    return f"{state.capitalize()}: “{name}” by {artists}."


@tool(
    "spotify_control",
    "Control Spotify playback: play, pause, next, or previous. Requires an "
    "active Spotify device (the app open somewhere).",
    [ToolParam("action", "string", "What to do", enum=["play", "pause", "next", "previous"])],
    timeout=20,
)
async def spotify_control(action: str) -> str:
    token, err = await _token("spotify")
    if err:
        return err
    method, path = {
        "play": ("PUT", "play"), "pause": ("PUT", "pause"),
        "next": ("POST", "next"), "previous": ("POST", "previous"),
    }[action]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(
            method, f"https://api.spotify.com/v1/me/player/{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code in (200, 202, 204):
        return f"Done — {action}."
    if resp.status_code == 404:
        return "No active Spotify device. Open Spotify on a device and try again."
    return f"Spotify error ({resp.status_code}): {resp.text[:200]}"


# ----------------------------------------------------------------------- Gmail

@tool(
    "gmail_list",
    "List the user's most recent Gmail messages (subject + sender). Optional "
    "search query (Gmail search syntax).",
    [
        ToolParam("query", "string", "Gmail search, e.g. 'is:unread'", required=False),
        ToolParam("count", "integer", "How many (1-10)", required=False),
    ],
    timeout=25,
)
async def gmail_list(query: str = "", count: int = 5) -> str:
    token, err = await _token("gmail")
    if err:
        return err
    count = max(1, min(int(count), 10))
    async with httpx.AsyncClient(timeout=20) as client:
        listing = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"maxResults": count, "q": query or ""},
        )
        if listing.status_code != 200:
            return f"Gmail error ({listing.status_code}): {listing.text[:200]}"
        ids = [m["id"] for m in listing.json().get("messages", [])]
        if not ids:
            return "No matching messages."
        lines = ["Recent messages:"]
        for mid in ids:
            msg = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": ["Subject", "From"]},
            )
            headers = {h["name"]: h["value"] for h in msg.json().get("payload", {}).get("headers", [])}
            lines.append(f"  • {headers.get('Subject', '(no subject)')} — {headers.get('From', '')}")
    return "\n".join(lines)


@tool(
    "gmail_draft",
    "Create a Gmail draft (does not send). Returns confirmation.",
    [
        ToolParam("to", "string", "Recipient email address"),
        ToolParam("subject", "string", "Email subject"),
        ToolParam("body", "string", "Email body text"),
    ],
    timeout=25,
)
async def gmail_draft(to: str, subject: str, body: str) -> str:
    token, err = await _token("gmail")
    if err:
        return err
    raw = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": {"raw": encoded}},
        )
    if resp.status_code not in (200, 201):
        return f"Couldn't create draft ({resp.status_code}): {resp.text[:200]}"
    return f"Draft to {to} saved in Gmail — subject '{subject}'. Review and send it there."


CONNECTED_TOOL_NAMES = [
    "calendar_list_events", "calendar_create_event",
    "spotify_now_playing", "spotify_control", "gmail_list", "gmail_draft",
]
