# VibeAudit

A tool that automates the checkable part of the **Trust-Security Gap
Analysis (TSGA)** framework: does a site use HTTPS, does it link a privacy
policy, which security response headers are set, and does its text contain
patterns associated with trust inflation (unverified performance claims,
confidence-sounding percentages, third-party launch badges, testimonial
language, manufactured urgency, guarantee and superlative-authority
phrasing)?

From those automated subtotals it computes a **TSGA gap score and band**.
The Habituation Risk Index (HRI) is never inferred — you supply it by hand,
or leave it unassessed and the score is the raw trust/security gap.

Built as the companion tool for a research paper on the trust-security gap
in AI-generated ("vibe-coded") interfaces. It does not claim to fully
automate TSGA scoring — see [Scope](#scope-what-this-tool-does-and-doesnt-do).

## Quick start

```bash
pip install -r requirements.txt

# Web UI + API
uvicorn api.server:app --reload
# then open http://localhost:8000

# CLI - single URL (human-readable summary)
python -m vibeaudit audit https://example.com

# ...with a manual Habituation Risk Index and a JSON dump to disk
python -m vibeaudit audit https://example.com --hri 0.6 --json --out result.json

# CLI - batch (urls.csv: one URL per line, or "name,url")
python -m vibeaudit batch urls.csv --output results.csv
python -m vibeaudit batch urls.csv --output report.md   --format md
python -m vibeaudit batch urls.csv --output report.html --format html
```

## Run the tests

```bash
pytest tests/
```

Tests run entirely against local HTML fixtures and a throwaway in-process
HTTP server — no outbound network access needed, so they'll pass in CI or
an offline sandbox.

## Project layout

```
vibeaudit/           Core library (fetcher, scorer, patterns, CLI, TSGA math, reports)
api/server.py        FastAPI backend - serves the API and the frontend
frontend/            Vanilla HTML/CSS/JS UI (no build step required)
tests/               Unit + integration tests, all offline
```

The core library has no dependency on the API or CLI — both are thin
wrappers around the same `fetch()` → `score()` → `tsga` pipeline, so
there's exactly one place the scoring logic lives.

## The TSGA score

Both automated subtotals are normalised to 0–10 against the maximum the
automated checks could produce (this is an **absolute** scale relative to
the pattern table, not the sample-relative normalisation in Paper 2's
pilot), then combined:

```
gap        = UTST_normalized - SPC_normalized
TSGA_base  = gap * (1 + HRI)          # HRI is 0..1, or 0 when "not assessed"
```

Bands: **Low** < 2, **Moderate** 2–5, **High** 5–8, **Severe** ≥ 8. A
negative gap (SPC keeps pace with UTST) lands in Low, not Severe.

Time projection (`TSGA_projected`) still refuses to return a number unless
you pass an explicit `drift_rate` — see the limitations below.

Endpoints: `POST /api/audit`, `POST /api/audit/batch`, `POST /api/tsga`
(recompute the figure for an already-audited page with a new HRI, no
re-fetch), `GET /api/leaderboard?sort=rank|utst|date|name`.

## Scope: what this tool does and doesn't do

**Automated (this tool):**
- HTTPS presence, scored on the final URL after redirects (an HTTPS→HTTP
  downgrade is flagged and scored as not-secure)
- Privacy policy link presence (10-language regex)
- A subset of security response headers (CSP, HSTS, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy)
- Fourteen text-pattern checks from the UTST taxonomy (see
  `vibeaudit/patterns.py`)
- The TSGA gap / band, with HRI held at 0 unless supplied

**Deliberately NOT automated — needs a human:**
- Visual professionalism, iconography, layout quality
- Feature-attribution highlights
- Habituation Risk Index (HRI) — repeated-exposure judgement a single
  static fetch cannot make; enter it manually via `--hri` or the UI slider
- The UTST patterns beyond the fourteen in `patterns.py`

A page scoring 0 on the automated checks is **not** a clean bill of health
— it means nothing in the automated subset fired. Use this tool to flag
candidates for manual review, not as a final verdict.

## Known limitations (found during testing, not swept under the rug)

- **JavaScript is not executed.** Client-side-rendered pages show up as
  near-empty. This is treated as a real, reportable signal
  (`likely_blank_page`) — the app has no non-JS fallback content — rather
  than a fetch failure, but a "blank" result needs a manual look before
  you conclude anything about the app's actual content.
- **Multilingual pattern coverage is still partial.** The privacy-link
  regex covers ten languages; a subset of the trust-signal patterns carry
  French/Spanish/German/Italian keywords. Non-Latin scripts and long-tail
  languages are not covered and will under-report. This remains the
  single most valuable thing to extend next.
- **Response bodies are capped at 3 MB** and non-HTML content types are
  fetched but not text-scored (headers/HTTPS still count). Both are noted
  in the result rather than hidden.
- **The backend refuses private/loopback/link-local targets by default**
  (SSRF guard). Set `VIBEAUDIT_ALLOW_PRIVATE=1` to audit `localhost` etc.
- **Security headers require a real HTTP fetch.** A pasted-HTML workflow
  would correctly show nothing found — it degrades safely rather than
  guessing.
- **The `drift_rate` value in `tsga.py` has no empirical basis.** Paper 2
  is explicit that this parameter needs a longitudinal user study that has
  not been run. `compute_tsga_projection` returns `None` unless you supply
  a rate — and doing so is a research claim you're making, not a fact the
  tool knows.
- **Added patterns are weighted by analogy.** The five patterns added
  beyond Paper 2's tables (urgency/scarcity, live-activity tickers,
  guarantee language, superlative authority, security-theater phrasing)
  are weighted to the closest paper category, not from the paper directly.

## License

MIT (adjust as you prefer before publishing).
