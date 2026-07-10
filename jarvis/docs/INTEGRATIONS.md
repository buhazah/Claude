# Integrations Guide

JARVIS can use external data and act on your accounts through **tools**. There
are two kinds:

## 1. Zero-setup integrations (work immediately)
No credentials, no connection — these use free public APIs:

| Tool | What it does |
|------|--------------|
| `weather` | Current conditions + 3-day forecast for any city (Open-Meteo) |
| `news` | Recent headlines, overall or by topic (Google News RSS) |

Just ask JARVIS: *"What's the weather in Dubai this weekend?"* or *"What's the
latest AI news?"*

## 2. Account integrations (one-time connection)

These act on **your** accounts and require OAuth. Two setup layers:

- **Server credentials** (admin, once): register a JARVIS "app" with the
  provider and set its client id/secret as environment variables.
- **User connection** (per user, in the UI): Settings → Connections → **Connect**,
  approve access in the popup. Tokens are stored **encrypted** (Fernet key
  derived from `JARVIS_SECRET_KEY`).

| Provider | Env vars | Tools |
|----------|----------|-------|
| Google Calendar | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `calendar_list_events`, `calendar_create_event` |
| Gmail | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (same app) | `gmail_list`, `gmail_draft` |
| Spotify | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | `spotify_now_playing`, `spotify_control` |

### The redirect URI (needed during setup)
Each provider must whitelist JARVIS's callback URL:
```
https://<your-domain>/api/connections/<provider>/callback
```
e.g. for Spotify on Render: `https://jarvis-56ml.onrender.com/api/connections/spotify/callback`.
(`<provider>` is `google`, `gmail`, or `spotify`.)

If auto-detection of your domain is ever wrong (behind an unusual proxy), set
`JARVIS_PUBLIC_URL=https://your-domain` explicitly.

---

### Google (Calendar + Gmail) setup
1. Go to <https://console.cloud.google.com/> → create/select a project.
2. **APIs & Services → Enable APIs**: enable **Google Calendar API** and
   **Gmail API**.
3. **OAuth consent screen**: choose *External*, add your email as a **Test
   user** (so it works before Google verification).
4. **Credentials → Create Credentials → OAuth client ID → Web application**.
5. Under **Authorized redirect URIs**, add both:
   - `https://<your-domain>/api/connections/google/callback`
   - `https://<your-domain>/api/connections/gmail/callback`
6. Copy the **Client ID** and **Client secret** into `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET` (on Render: the service's Environment tab), and
   redeploy.
7. In JARVIS: Settings → Connections → **Connect** next to Google Calendar
   (and Gmail).

### Spotify setup
1. Go to <https://developer.spotify.com/dashboard> → **Create app**.
2. Add redirect URI: `https://<your-domain>/api/connections/spotify/callback`.
3. Copy the **Client ID** and **Client secret** into `SPOTIFY_CLIENT_ID` /
   `SPOTIFY_CLIENT_SECRET`, and redeploy.
4. In JARVIS: Settings → Connections → **Connect** next to Spotify.
   *(Spotify playback control needs the Spotify app open on some device.)*

---

## Security notes
- Tokens are encrypted at rest; only a valid `JARVIS_SECRET_KEY` can read them.
- Access tokens auto-refresh; a user can **Disconnect** any time in Settings,
  which deletes the stored tokens.
- The OAuth `state` parameter is HMAC-signed and expires in 15 minutes, binding
  each callback to the user who started it.

## Adding more integrations
Any OAuth2 provider can be added by appending a `Provider(...)` entry in
`server/integrations/oauth.py` and writing tools that call
`get_access_token(user_id, provider)`. Non-OAuth APIs (like weather) are just
plain tools in `server/tools/live_tools.py`. See `docs/DEVELOPER.md`.
