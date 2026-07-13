"""Tests for the Progressive Web App plumbing (manifest, service worker, icons)."""
import json


def test_manifest_served(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert "manifest" in r.headers["content-type"]
    data = json.loads(r.content)
    assert data["name"] and data["start_url"] == "/"
    assert data["display"] == "standalone"
    # Needs the icon sizes browsers require for install + a maskable one.
    sizes = {i["sizes"] for i in data["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in data["icons"])


def test_service_worker_served_at_root_scope(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    # Must be allowed to control the whole origin.
    assert r.headers.get("service-worker-allowed") == "/"
    assert "addEventListener" in r.text


def test_icons_served(client):
    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"):
        r = client.get(f"/static/icons/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"] == "image/png"


def test_index_links_manifest(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "/manifest.webmanifest" in r.text
    assert 'name="theme-color"' in r.text
    assert "apple-touch-icon" in r.text
