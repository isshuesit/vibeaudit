"""Fetcher hardening tests. No real network: a tiny in-process HTTP server
covers the end-to-end path, unit tests cover the helpers."""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from vibeaudit import fetcher
from vibeaudit.fetcher import _extract_visible_text, _read_capped, fetch


def test_extract_visible_text_drops_script_style_template():
    html = """
    <html><head><style>.a{color:red}</style></head>
    <body>Hello <script>doEvil()</script><template>ghost</template> world</body></html>
    """
    assert _extract_visible_text(html) == "Hello world"


class _FakeResp:
    def __init__(self, chunks, encoding="utf-8"):
        self._chunks = chunks
        self.encoding = encoding
        self.apparent_encoding = "utf-8"

    def iter_content(self, chunk_size=65536):
        yield from self._chunks


def test_read_capped_truncates():
    big = [b"x" * 100_000 for _ in range(60)]  # 6 MB
    text, truncated = _read_capped(_FakeResp(big), limit=1_000_000)
    assert truncated is True
    assert len(text) == 1_000_000


def test_read_capped_no_truncation_for_small_body():
    text, truncated = _read_capped(_FakeResp([b"hello world"]), limit=1_000_000)
    assert truncated is False
    assert text == "hello world"


# ---- in-process server for the full fetch() path ----

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path == "/html":
            body = b"<html><body><h1>Hi</h1><p>" + b"word " * 60 + b"</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Frame-Options", "DENY")
        elif self.path == "/pdf":
            body = b"%PDF-1.4 not really"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/html")
            self.end_headers()
            return
        else:
            body = b"nope"
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def base_url():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_fetch_html_ok(base_url):
    r = fetch(base_url + "/html", timeout=5)
    assert r.ok is True
    assert "word" in r.text
    assert "x-frame-options" in {k.lower() for k in r.headers}


def test_fetch_non_html_still_scores_headers_but_no_text(base_url):
    r = fetch(base_url + "/pdf", timeout=5)
    assert r.text == ""
    assert "not HTML" in (r.error or "")


def test_fetch_follows_redirect_and_records_final_url(base_url):
    r = fetch(base_url + "/redirect", timeout=5)
    assert r.final_url.endswith("/html")
    assert "Hi" in r.text


def test_fetch_bad_host_is_captured_not_raised():
    r = fetch("http://this-host-does-not-exist.invalid./", timeout=3)
    assert r.ok is False
    assert r.error
