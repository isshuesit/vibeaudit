"""Human-facing batch reports (Markdown / self-contained HTML).

Shared by the CLI (`batch --format md|html`) and available to the API so
there is one place the report layout lives. Pure formatting - it takes
already-scored AuditResult objects and returns a string.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from .models import AuditResult


def _summarize(results: list[AuditResult]) -> dict:
    ok = [r for r in results if r.fetch_ok]
    bands: dict[str, int] = {}
    for r in ok:
        label = r.tsga.band_label if r.tsga else "n/a"
        bands[label] = bands.get(label, 0) + 1
    gaps = [r.tsga.gap for r in ok if r.tsga]
    return {
        "total": len(results),
        "ok": len(ok),
        "failed": len(results) - len(ok),
        "blank": sum(1 for r in ok if r.likely_blank_page),
        "bands": bands,
        "avg_gap": round(sum(gaps) / len(gaps), 2) if gaps else None,
        "max_gap": round(max(gaps), 2) if gaps else None,
    }


def _rows(results: list[AuditResult]) -> list[dict]:
    out = []
    for r in results:
        row = {
            "app_name": r.app_name,
            "url": r.final_url or r.url,
            "status": "ok" if r.fetch_ok else (r.fetch_error or "failed"),
            "https": "-",
            "privacy": "-",
            "headers": "-",
            "utst": "-",
            "gap": "-",
            "band": "-",
            "blank": "yes" if (r.fetch_ok and r.likely_blank_page) else "",
            "patterns": "",
        }
        if r.fetch_ok and r.spc and r.utst:
            row["https"] = "yes" if r.spc.https else "no"
            row["privacy"] = "yes" if r.spc.privacy_policy_link_found else "no"
            row["headers"] = (
                f"{len(r.spc.security_headers_present)}/"
                f"{len(r.spc.security_headers_checked)}"
            )
            row["utst"] = str(r.utst.automated_subtotal)
            row["patterns"] = "; ".join(h.pattern for h in r.utst.hits)
        if r.fetch_ok and r.tsga:
            row["gap"] = f"{r.tsga.gap:+.2f}"
            row["band"] = r.tsga.band_label
        out.append(row)
    return out


_COLS = [
    ("app_name", "App"),
    ("url", "URL"),
    ("https", "HTTPS"),
    ("privacy", "Privacy"),
    ("headers", "Headers"),
    ("utst", "UTST"),
    ("gap", "Gap"),
    ("band", "Band"),
    ("blank", "Blank?"),
    ("status", "Status"),
]


def _render_markdown(results: list[AuditResult]) -> str:
    s = _summarize(results)
    rows = _rows(results)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# VibeAudit batch report",
        "",
        f"_Generated {ts}_",
        "",
        "## Summary",
        "",
        f"- Targets audited: **{s['total']}** ({s['ok']} ok, {s['failed']} failed)",
        f"- Likely blank / JS-rendered: **{s['blank']}**",
        f"- Average trust/security gap: **{s['avg_gap'] if s['avg_gap'] is not None else 'n/a'}**"
        f" (max {s['max_gap'] if s['max_gap'] is not None else 'n/a'})",
    ]
    if s["bands"]:
        band_str = ", ".join(f"{k}: {v}" for k, v in sorted(s["bands"].items()))
        lines.append(f"- Bands: {band_str}")
    lines += ["", "## Results", ""]

    header = "| " + " | ".join(label for _, label in _COLS) + " |"
    sep = "| " + " | ".join("---" for _ in _COLS) + " |"
    lines += [header, sep]
    for row in rows:
        cells = [str(row[key]).replace("|", "\\|") for key, _ in _COLS]
        lines.append("| " + " | ".join(cells) + " |")

    detailed = [r for r in _rows(results) if r["patterns"]]
    if detailed:
        lines += ["", "## Patterns hit", ""]
        for row in detailed:
            lines.append(f"- **{row['app_name']}** ({row['url']}): {row['patterns']}")

    lines += [
        "",
        "---",
        "",
        "_A high UTST subtotal or gap is a prompt for manual review, not a "
        "verdict. See the tool README for the automated/manual scope split._",
        "",
    ]
    return "\n".join(lines)


def _render_html(results: list[AuditResult]) -> str:
    s = _summarize(results)
    rows = _rows(results)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def esc(v: object) -> str:
        return html.escape(str(v))

    band_str = ", ".join(f"{esc(k)}: {v}" for k, v in sorted(s["bands"].items())) or "n/a"

    head = (
        "<tr>"
        + "".join(f"<th>{esc(label)}</th>" for _, label in _COLS)
        + "</tr>"
    )
    body_rows = []
    for row in rows:
        cls = ""
        if row["status"] != "ok":
            cls = ' class="failed"'
        elif row["band"] in ("High", "Severe"):
            cls = ' class="hot"'
        cells = "".join(f"<td>{esc(row[key])}</td>" for key, _ in _COLS)
        body_rows.append(f"<tr{cls}>{cells}</tr>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VibeAudit batch report</title>
<style>
  body {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; margin: 40px;
         background: #0a0a0a; color: #ededea; }}
  h1 {{ font-size: 20px; letter-spacing: 0.04em; }}
  .meta {{ color: #8a8a8a; font-size: 13px; margin-bottom: 24px; }}
  .summary {{ border: 1px solid #2e2e2e; padding: 16px 20px; margin-bottom: 28px; }}
  .summary div {{ margin: 4px 0; font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid #1c1c1c; }}
  th {{ color: #8a8a8a; border-bottom: 1px solid #2e2e2e; }}
  tr.failed td {{ color: #8a8a8a; font-style: italic; }}
  tr.hot td {{ color: #fff; background: #1c1414; }}
  footer {{ margin-top: 28px; color: #8a8a8a; font-size: 12px; max-width: 640px; }}
</style>
</head>
<body>
<h1>VibeAudit batch report</h1>
<div class="meta">Generated {esc(ts)}</div>
<div class="summary">
  <div>Targets audited: <b>{s['total']}</b> ({s['ok']} ok, {s['failed']} failed)</div>
  <div>Likely blank / JS-rendered: <b>{s['blank']}</b></div>
  <div>Average gap: <b>{esc(s['avg_gap'] if s['avg_gap'] is not None else 'n/a')}</b>
       (max {esc(s['max_gap'] if s['max_gap'] is not None else 'n/a')})</div>
  <div>Bands: {band_str}</div>
</div>
<table>
  <thead>{head}</thead>
  <tbody>{''.join(body_rows)}</tbody>
</table>
<footer>A high UTST subtotal or gap is a prompt for manual review, not a verdict.
See the tool README for the automated/manual scope split.</footer>
</body>
</html>
"""


def render_report(results: list[AuditResult], fmt: str = "md") -> str:
    if fmt == "md":
        return _render_markdown(results)
    if fmt == "html":
        return _render_html(results)
    raise ValueError(f"unknown report format: {fmt!r}")
