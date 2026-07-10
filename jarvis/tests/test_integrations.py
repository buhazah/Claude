"""Tests for the integrations layer: crypto, OAuth state, connections API."""
import pytest

from server.integrations.crypto import decrypt, encrypt
from server.integrations.oauth import (
    PROVIDERS, OAuthError, authorize_url, sign_state, verify_state,
)


def test_crypto_roundtrip():
    secret = "ya29.some-access-token-value"
    assert decrypt(encrypt(secret)) == secret
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_crypto_rejects_tampering():
    blob = encrypt("token")
    # A corrupted ciphertext decrypts to empty rather than raising.
    assert decrypt(blob[:-4] + "AAAA") == ""


def test_oauth_state_roundtrip():
    state = sign_state("user-1", "spotify")
    uid, provider = verify_state(state)
    assert uid == "user-1" and provider == "spotify"


def test_oauth_state_tamper_rejected():
    state = sign_state("user-1", "spotify")
    with pytest.raises(OAuthError):
        verify_state(state[:-2] + "xx")
    with pytest.raises(OAuthError):
        verify_state("garbage")


def test_authorize_url_shape():
    p = PROVIDERS["spotify"]
    p.client_id = "test-client"  # pretend configured for URL building
    url = authorize_url("spotify", "https://app/cb", "STATE")
    assert url.startswith("https://accounts.spotify.com/authorize?")
    assert "redirect_uri=https%3A%2F%2Fapp%2Fcb" in url
    assert "state=STATE" in url
    assert "response_type=code" in url


def test_providers_present():
    assert set(PROVIDERS) == {"google", "gmail", "spotify"}


def test_connections_endpoint(auth_client):
    r = auth_client.get("/api/connections")
    assert r.status_code == 200
    conns = r.json()["connections"]
    providers = {c["provider"] for c in conns}
    assert {"google", "gmail", "spotify"} <= providers
    # Nothing connected on a fresh account.
    assert all(not c["connected"] for c in conns)


def test_authorize_unconfigured_returns_message(auth_client):
    r = auth_client.get("/api/connections/google/authorize")
    assert r.status_code == 200
    # Without server credentials it explains setup is needed rather than 500ing.
    assert "error" in r.json()


def test_live_and_connected_tools_registered():
    from server.tools import connected_tools, live_tools  # noqa: F401
    from server.tools.base import registry

    for name in ["weather", "news", "calendar_list_events", "spotify_now_playing", "gmail_draft"]:
        assert registry.get(name) is not None
