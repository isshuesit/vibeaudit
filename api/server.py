"""FastAPI backend for VibeAudit.

Run with:  uvicorn api.server:app --reload
Then open: http://localhost:8000
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibeaudit.fetcher import fetch
from vibeaudit.scorer import score
from vibeaudit import tsga as tsga_mod

APP_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = APP_ROOT / "frontend"
LEADERBOARD_PATH = APP_ROOT / "leaderboard.json"
LEADERBOARD_MAX = 500

app = FastAPI(title="VibeAudit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    url: str
    app_name: str | None = None
    hri: float | None = None


class BatchAuditRequest(BaseModel):
    entries: list[AuditRequest]


def _load_leaderboard() -> list[dict]:
    if not LEADERBOARD_PATH.exists():
        return []
    try:
        return json.loads(LEADERBOARD_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _entry_key(entry: dict) -> str:
    """Identity of an audited target for dedup - the final (post-redirect)
    URL when we have it, otherwise the requested one, normalised."""
    raw = (entry.get("final_url") or entry.get("url") or "").strip().lower()
    return raw.rstrip("/")


def _save_to_leaderboard(entry: dict) -> None:
    board = _load_leaderboard()
    key = _entry_key(entry)
    # Keep one row per target - the most recent audit wins.
    board = [e for e in board if _entry_key(e) != key]
    board.append(entry)
    board = board[-LEADERBOARD_MAX:]
    tmp = LEADERBOARD_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(board, indent=2))
    tmp.replace(LEADERBOARD_PATH)


def _derive_name(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).netloc or url).replace("www.", "")


def _validate_hri(hri: float | None) -> None:
    if hri is not None and not (0.0 <= hri <= 1.0):
        raise HTTPException(400, "hri must be between 0 and 1")


# SSRF guard: this backend fetches arbitrary user-supplied URLs, so by
# default it refuses targets that resolve into private, loopback, or
# link-local ranges (cloud metadata endpoints, internal admin panels...).
# Set VIBEAUDIT_ALLOW_PRIVATE=1 to lift it for local testing.
def _allow_private() -> bool:
    return os.environ.get("VIBEAUDIT_ALLOW_PRIVATE", "") not in ("", "0", "false", "False")


def _guard_target_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    if _allow_private():
        return
    host = urlparse(url).hostname
    if not host:
        raise HTTPException(400, "URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, f"Could not resolve host {host!r}")
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(
                400,
                f"Refusing to audit {host!r}: resolves to non-public address {addr}. "
                "Set VIBEAUDIT_ALLOW_PRIVATE=1 to override for local testing.",
            )


def _run_audit(url: str, app_name: str | None, hri: float | None = None) -> dict:
    name = app_name or _derive_name(url)
    fetch_result = fetch(url)
    result = score(name, fetch_result, hri=hri)
    result_dict = result.to_dict()
    if result.fetch_ok:
        _save_to_leaderboard(result_dict)
    return result_dict


@app.post("/api/audit")
def audit_single(req: AuditRequest):
    _guard_target_url(req.url)
    _validate_hri(req.hri)
    return _run_audit(req.url, req.app_name, req.hri)


@app.post("/api/audit/batch")
def audit_batch(req: BatchAuditRequest):
    results = []
    for entry in req.entries:
        try:
            _guard_target_url(entry.url)
            _validate_hri(entry.hri)
        except HTTPException as exc:
            results.append(
                {"url": entry.url, "app_name": entry.app_name, "fetch_ok": False,
                 "fetch_error": exc.detail}
            )
            continue
        results.append(_run_audit(entry.url, entry.app_name, entry.hri))
        time.sleep(0.5)  # be polite to target servers between requests
    return {"results": results, "summary": _batch_summary(results)}


def _batch_summary(results: list[dict]) -> dict:
    ok = [r for r in results if r.get("fetch_ok")]
    bands: dict[str, int] = {}
    for r in ok:
        label = ((r.get("tsga") or {}).get("band_label")) or "n/a"
        bands[label] = bands.get(label, 0) + 1
    gaps = [((r.get("tsga") or {}).get("gap") or 0.0) for r in ok]
    return {
        "total": len(results),
        "ok": len(ok),
        "failed": len(results) - len(ok),
        "blank": sum(1 for r in ok if r.get("likely_blank_page")),
        "bands": bands,
        "avg_gap": round(sum(gaps) / len(gaps), 3) if gaps else None,
        "max_gap": round(max(gaps), 3) if gaps else None,
    }


def _gap_signal(entry: dict) -> int:
    utst = (entry.get("utst") or {}).get("automated_subtotal", 0)
    spc = entry.get("spc") or {}
    spc_credit = (1 if spc.get("https") else 0) + (1 if spc.get("privacy_policy_link_found") else 0)
    return utst - spc_credit


def _rank_value(entry: dict) -> float:
    """Rank by TSGA_base when it is available (it captures the headers and
    normalisation too), falling back to the coarse gap signal for old rows
    written before TSGA existed."""
    tsga = entry.get("tsga")
    if tsga and tsga.get("tsga_base") is not None:
        return float(tsga["tsga_base"])
    return float(_gap_signal(entry))


class TsgaRecomputeRequest(BaseModel):
    utst_raw: int
    spc_raw: float
    hri: float | None = None
    projection_days: int | None = None
    drift_rate: float | None = None


@app.post("/api/tsga")
def recompute_tsga(req: TsgaRecomputeRequest):
    """Recompute the TSGA figure for an already-audited page with a new HRI
    (or a speculative projection) without re-fetching the target."""
    _validate_hri(req.hri)
    if req.utst_raw < 0 or req.spc_raw < 0:
        raise HTTPException(400, "raw subtotals must be non-negative")
    return tsga_mod.score_tsga(
        utst_raw=req.utst_raw,
        spc_raw=req.spc_raw,
        hri_normalized=req.hri,
        projection_days=req.projection_days,
        drift_rate=req.drift_rate,
    )


@app.get("/api/leaderboard")
def get_leaderboard(sort: str = "rank", order: str = "desc"):
    board = _load_leaderboard()

    keyfns = {
        "rank": _rank_value,
        "gap": _gap_signal,
        "utst": lambda e: (e.get("utst") or {}).get("automated_subtotal", 0),
        "date": lambda e: e.get("audited_at") or "",
        "name": lambda e: (e.get("app_name") or "").lower(),
    }
    keyfn = keyfns.get(sort, _rank_value)
    reverse = order != "asc"
    board_sorted = sorted(board, key=keyfn, reverse=reverse)

    for entry in board_sorted:
        entry["gap_signal"] = _gap_signal(entry)
        entry["rank_value"] = round(_rank_value(entry), 3)
    return {"entries": board_sorted, "count": len(board_sorted)}


@app.delete("/api/leaderboard")
def clear_leaderboard():
    LEADERBOARD_PATH.write_text("[]")
    return {"cleared": True}


# Serve the frontend last so /api/* routes above take precedence.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
