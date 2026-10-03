"""Command-line interface.

Usage:
    python -m vibeaudit audit https://example.com
    python -m vibeaudit batch urls.csv --output results.csv
    python -m vibeaudit batch urls.csv --output results.json --format json

urls.csv format: one URL per line, optionally "app_name,url" per line.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time

from .fetcher import fetch
from .scorer import score
from .models import AuditResult


def _derive_app_name(url: str) -> str:
    from urllib.parse import urlparse

    host = urlparse(url).netloc or url
    return host.replace("www.", "")


def _audit_one(
    app_name: str,
    url: str,
    verbose: bool = True,
    hri: float | None = None,
    timeout: int = 10,
) -> AuditResult:
    if verbose:
        print(f"Fetching {url} ...", file=sys.stderr)
    fetch_result = fetch(url, timeout=timeout)
    result = score(app_name, fetch_result, hri=hri)
    if verbose:
        if not result.fetch_ok:
            print(f"  FAILED: {result.fetch_error}", file=sys.stderr)
        else:
            weight = result.utst.automated_subtotal if result.utst else 0
            blank = " [LIKELY BLANK / JS-RENDERED]" if result.likely_blank_page else ""
            tsga = result.tsga
            tsga_str = (
                f" | TSGA={tsga.tsga_base:.2f} ({tsga.band_label})" if tsga else ""
            )
            print(
                f"  OK - UTST subtotal={weight}{tsga_str}{blank}", file=sys.stderr
            )
    return result


def _print_human(result: AuditResult) -> None:
    """A readable single-audit summary for when --json is not requested."""
    print(f"\n=== {result.app_name} ===")
    print(f"URL:       {result.url}")
    if result.final_url and result.final_url != result.url:
        print(f"Final URL: {result.final_url}")
    if not result.fetch_ok:
        print(f"FETCH FAILED: {result.fetch_error}")
        return

    spc = result.spc
    print("\nSPC - Security Posture")
    print(f"  HTTPS:                 {'yes' if spc.https else 'no'}")
    print(f"  Privacy policy link:   {'yes' if spc.privacy_policy_link_found else 'no'}")
    print(
        f"  Security headers:      {len(spc.security_headers_present)}/"
        f"{len(spc.security_headers_checked)}"
        + (f" ({', '.join(spc.security_headers_present)})" if spc.security_headers_present else "")
    )

    utst = result.utst
    print(f"\nUTST - Trust Signals (weighted subtotal: {utst.automated_subtotal})")
    if not utst.hits:
        print("  (no automated trust-inflation patterns detected)")
    for hit in utst.hits:
        print(f"  +{hit.trust_weight}  {hit.pattern}")
        print(f"        \"{hit.evidence}\"")

    tsga = result.tsga
    if tsga:
        print("\nTSGA - Trust/Security Gap")
        print(f"  UTST normalized:  {tsga.utst_normalized:.2f} / 10")
        print(f"  SPC normalized:   {tsga.spc_normalized:.2f} / 10")
        print(f"  Gap:              {tsga.gap:+.2f}")
        hri_note = (
            f"{tsga.hri_normalized:.2f} (manual)"
            if tsga.hri_source == "manual"
            else "not assessed (multiplier = 1)"
        )
        print(f"  HRI:              {hri_note}")
        print(f"  TSGA_base:        {tsga.tsga_base:+.2f}  ->  {tsga.band_label}")
        print(f"                    {tsga.band_description}")

    if result.likely_blank_page:
        print("\n[!] Page looks blank / JS-rendered - see notes.")
    for note in result.notes:
        print(f"\nNote: {note}")


def _read_url_list(path: str) -> list[tuple[str, str]]:
    entries = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            row = [c.strip() for c in row if c.strip()]
            if not row:
                continue
            if len(row) == 1:
                entries.append((_derive_app_name(row[0]), row[0]))
            else:
                entries.append((row[0], row[1]))
    return entries


def _write_results_csv(results: list[AuditResult], path: str) -> None:
    fieldnames = [
        "app_name", "url", "final_url", "fetch_ok", "fetch_error", "https",
        "privacy_policy_link_found", "security_headers_present",
        "utst_automated_subtotal", "utst_patterns_hit",
        "utst_normalized", "spc_normalized", "tsga_gap", "hri", "tsga_base",
        "tsga_band", "likely_blank_page",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            t = r.tsga
            writer.writerow({
                "app_name": r.app_name,
                "url": r.url,
                "final_url": r.final_url or "",
                "fetch_ok": r.fetch_ok,
                "fetch_error": r.fetch_error or "",
                "https": r.spc.https if r.spc else "",
                "privacy_policy_link_found": r.spc.privacy_policy_link_found if r.spc else "",
                "security_headers_present": "; ".join(r.spc.security_headers_present) if r.spc else "",
                "utst_automated_subtotal": r.utst.automated_subtotal if r.utst else "",
                "utst_patterns_hit": "; ".join(h.pattern for h in r.utst.hits) if r.utst else "",
                "utst_normalized": f"{t.utst_normalized:.3f}" if t else "",
                "spc_normalized": f"{t.spc_normalized:.3f}" if t else "",
                "tsga_gap": f"{t.gap:.3f}" if t else "",
                "hri": (f"{t.hri_normalized:.2f}" if t and t.hri_normalized is not None else ""),
                "tsga_base": f"{t.tsga_base:.3f}" if t else "",
                "tsga_band": t.band_label if t else "",
                "likely_blank_page": r.likely_blank_page,
            })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vibeaudit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--hri",
            type=float,
            default=None,
            metavar="0..1",
            help="Manual Habituation Risk Index (0=none, 1=max). Omitted = not "
            "assessed; the (1 + HRI) multiplier stays at 1.",
        )
        p.add_argument(
            "--timeout", type=int, default=10, help="Per-request timeout in seconds"
        )

    audit_parser = sub.add_parser("audit", help="Audit a single URL")
    audit_parser.add_argument("url")
    audit_parser.add_argument("--name", default=None, help="App name (defaults to hostname)")
    audit_parser.add_argument("--json", action="store_true", help="Print full JSON result")
    audit_parser.add_argument(
        "--out", default=None, metavar="FILE", help="Write the JSON result to FILE"
    )
    _add_common(audit_parser)

    batch_parser = sub.add_parser("batch", help="Audit a list of URLs from a file")
    batch_parser.add_argument("input_file", help="CSV file: 'url' or 'app_name,url' per line")
    batch_parser.add_argument("--output", "-o", required=True, help="Output file path")
    batch_parser.add_argument(
        "--format", choices=["csv", "json", "md", "html"], default="csv"
    )
    batch_parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (be polite)")
    _add_common(batch_parser)

    args = parser.parse_args(argv)

    if args.hri is not None and not (0.0 <= args.hri <= 1.0):
        parser.error("--hri must be between 0 and 1")

    if args.command == "audit":
        name = args.name or _derive_app_name(args.url)
        result = _audit_one(name, args.url, hri=args.hri, timeout=args.timeout)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"Wrote {args.out}", file=sys.stderr)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            _print_human(result)
        return 0 if result.fetch_ok else 1

    if args.command == "batch":
        entries = _read_url_list(args.input_file)
        if not entries:
            print("No URLs found in input file.", file=sys.stderr)
            return 1

        results = []
        for i, (name, url) in enumerate(entries):
            results.append(_audit_one(name, url, hri=args.hri, timeout=args.timeout))
            if i < len(entries) - 1:
                time.sleep(args.delay)

        if args.format == "csv":
            _write_results_csv(results, args.output)
        elif args.format == "json":
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in results], f, indent=2)
        else:
            from .report import render_report

            text = render_report(results, fmt=args.format)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)

        failed = sum(1 for r in results if not r.fetch_ok)
        print(
            f"\nDone: {len(results)} audited, {failed} failed. "
            f"Written to {args.output}",
            file=sys.stderr,
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
