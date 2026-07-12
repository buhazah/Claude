"""Tests for the screen-vision endpoint and data-URL parsing."""


def test_parse_data_url():
    from server.vision.analyze import parse_data_url

    mt, data = parse_data_url("data:image/png;base64,QUJD")
    assert mt == "image/png" and data == "QUJD"
    mt, data = parse_data_url("data:image/jpeg;charset=utf-8;base64,WFla")
    assert mt == "image/jpeg" and data == "WFla"
    # Raw base64 (no data-url header) defaults to png.
    mt, data = parse_data_url("QUJD")
    assert mt == "image/png" and data == "QUJD"


def test_vision_requires_auth(client):
    r = client.post("/api/vision/analyze", json={"image": "data:image/png;base64,QUJD"})
    assert r.status_code == 401


def test_vision_rejects_missing_image(auth_client):
    r = auth_client.post("/api/vision/analyze", json={"image": "", "prompt": "hi"})
    assert r.status_code == 400


def test_vision_config_shape(auth_client):
    r = auth_client.get("/api/vision/config")
    assert r.status_code == 200
    assert "available" in r.json()
