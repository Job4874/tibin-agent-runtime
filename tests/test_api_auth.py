"""API access control: mutating /api/* routes fail closed without the token."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _client():
    from app.app import app
    return app, app.test_client()


def test_mutating_api_requires_token():
    app, client = _client()
    for path in [
        "/api/tasks/run_loop",
        "/api/tasks/run_autonomous",
        "/api/daemon/start",
        "/api/daemon/stop",
        "/api/approvals/approve",
        "/api/approvals/reject",
        "/api/providers/run_next",
        "/api/providers/status",
        "/api/browser/open",
        "/api/browser/playwright",
        "/api/complexity/checkpoint",
        "/api/model_loop/generate_prompt",
    ]:
        res = client.post(path, json={})
        assert res.status_code == 401, f"{path} returned {res.status_code}, expected 401"
        assert res.get_json()["error"] == "unauthorized"


def test_wrong_token_rejected():
    app, client = _client()
    res = client.post("/api/daemon/stop", json={}, headers={"X-Tibin-Token": "wrong-token"})
    assert res.status_code == 401


def test_valid_token_accepted():
    app, client = _client()
    token = app.config["API_TOKEN"]
    res = client.post("/api/daemon/stop", json={}, headers={"X-Tibin-Token": token})
    assert res.status_code == 200

    # Bearer form also works
    res = client.post("/api/complexity/checkpoint", json={}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_get_routes_do_not_require_token():
    app, client = _client()
    for path in ["/health", "/api/status", "/api/stats", "/api/system/status", "/api/brain"]:
        res = client.get(path)
        assert res.status_code == 200, f"{path} returned {res.status_code}"


def test_unknown_host_rejected():
    app, client = _client()
    res = client.get("/health", headers={"Host": "evil.example.com"})
    assert res.status_code == 403


def test_security_headers_present():
    app, client = _client()
    res = client.get("/dashboard")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in res.headers


def test_run_loop_rejects_path_traversal():
    app, client = _client()
    token = app.config["API_TOKEN"]
    res = client.post(
        "/api/tasks/run_loop",
        json={"plan": "../../etc/passwd"},
        headers={"X-Tibin-Token": token},
    )
    assert res.status_code == 400

    res = client.post(
        "/api/tasks/run_loop",
        json={"plan": "/etc/passwd"},
        headers={"X-Tibin-Token": token},
    )
    assert res.status_code == 400


def test_providers_page_renders():
    """The committed provider config must not 500 the providers page."""
    app, client = _client()
    res = client.get("/providers")
    assert res.status_code == 200
    assert b"LLM Providers" in res.data


def test_api_token_not_logged_in_health(monkeypatch):
    app, client = _client()
    res = client.get("/health")
    assert app.config["API_TOKEN"].encode() not in res.data
