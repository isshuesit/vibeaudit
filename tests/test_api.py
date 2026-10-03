"""End-to-end API tests through FastAPI's TestClient.

Network is stubbed: `fetch` is monkeypatched to return canned FetchResults
built from the local fixtures, so these exercise the real routing, scoring,
TSGA math, and leaderboard persistence without touching the internet.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api"))

import pytest
from fastapi.testclient import TestClient

from vibeaudit.fetcher import _extract_visible_text
from vibeaudit.models import FetchResult

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_fetch(filename, headers=None):
    with open(os.path.join(FIXTURES, filename), encoding="utf-8") as f:
        html = f.read()
    text = _extract_visible_text(html)

    def _fake_fetch(url, timeout=10):
        return FetchResult(
            url=url,
            ok=True,
            status_code=200,
            final_url=url,
            html=html,
            text=text,
            headers=headers or {},
        )

    return _fake_fetch


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import api.server as server

    # Test URLs are fake and won't resolve; lift the SSRF guard for them.
    monkeypatch.setenv("VIBEAUDIT_ALLOW_PRIVATE", "1")
    monkeypatch.setattr(server, "LEADERBOARD_PATH", tmp_path / "leaderboard.json")
    monkeypatch.setattr(server, "fetch", _fixture_fetch("inflated_page.html"))
    return TestClient(server.app)


def test_audit_single_returns_tsga(client):
    r = client.post("/api/audit", json={"url": "https://inflated.example"})
    assert r.status_code == 200
    body = r.json()
    assert body["fetch_ok"] is True
    assert body["tsga"]["band_label"] in {"Low", "Moderate", "High", "Severe"}
    assert body["tsga"]["hri_source"] == "not_assessed"


def test_audit_rejects_bad_scheme(client):
    r = client.post("/api/audit", json={"url": "ftp://nope"})
    assert r.status_code == 400


def test_audit_rejects_out_of_range_hri(client):
    r = client.post("/api/audit", json={"url": "https://x.example", "hri": 3})
    assert r.status_code == 400


def test_recompute_tsga_without_refetch(client):
    audit = client.post("/api/audit", json={"url": "https://inflated.example"}).json()
    t = audit["tsga"]
    r = client.post(
        "/api/tsga",
        json={"utst_raw": t["utst_raw"], "spc_raw": t["spc_raw"], "hri": 1.0},
    )
    assert r.status_code == 200
    assert r.json()["tsga_base"] > t["tsga_base"]
    assert r.json()["hri_source"] == "manual"


def test_leaderboard_dedups_by_url(client):
    for _ in range(3):
        client.post("/api/audit", json={"url": "https://dupe.example/"})
    board = client.get("/api/leaderboard").json()
    keys = [e["url"] for e in board["entries"]]
    assert keys.count("https://dupe.example/") == 1


def test_leaderboard_sort_param(client):
    client.post("/api/audit", json={"url": "https://a.example/"})
    client.post("/api/audit", json={"url": "https://b.example/"})
    asc = client.get("/api/leaderboard?sort=name&order=asc").json()["entries"]
    names = [e["app_name"] for e in asc]
    assert names == sorted(names)


def test_ssrf_guard_blocks_loopback_by_default(tmp_path, monkeypatch):
    import api.server as server

    monkeypatch.delenv("VIBEAUDIT_ALLOW_PRIVATE", raising=False)
    monkeypatch.setattr(server, "LEADERBOARD_PATH", tmp_path / "lb.json")
    c = TestClient(server.app)
    r = c.post("/api/audit", json={"url": "http://127.0.0.1:80/"})
    assert r.status_code == 400
    assert "non-public" in r.json()["detail"]


def test_batch_returns_summary(client):
    r = client.post(
        "/api/audit/batch",
        json={"entries": [{"url": "https://a.example/"}, {"url": "bad-url"}]},
    )
    assert r.status_code == 200
    summary = r.json()["summary"]
    assert summary["total"] == 2
    assert summary["failed"] == 1


def test_full_stack_against_local_http_server(tmp_path, monkeypatch):
    """No fetch stub: real fetcher -> real scorer -> real TSGA, over a
    throwaway in-process HTTP server."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    import api.server as server

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = (
                b"<html><body><h1>92% accuracy, trusted by 10,000+ users</h1>"
                b"<p>Award-winning. Limited-time offer, only 2 left.</p>"
                b"<a href='/privacy'>Privacy Policy</a></body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("VIBEAUDIT_ALLOW_PRIVATE", "1")
        monkeypatch.setattr(server, "LEADERBOARD_PATH", tmp_path / "lb.json")
        c = TestClient(server.app)
        r = c.post("/api/audit", json={"url": f"http://127.0.0.1:{srv.server_port}/"})
        assert r.status_code == 200
        body = r.json()
        assert body["fetch_ok"] is True
        assert body["spc"]["https"] is False  # served over http
        assert body["spc"]["privacy_policy_link_found"] is True
        assert body["utst"]["automated_subtotal"] > 0
        assert body["tsga"]["band_label"] in {"Low", "Moderate", "High", "Severe"}
    finally:
        srv.shutdown()
