# VibeAudit

VibeAudit is a research companion tool for the **Trust-Security Gap Analysis (TSGA)** framework proposed in:

> **Explaining Away Security: XAI UI Patterns, Habituation, and the Trust-Security Gap in AI-Generated Interfaces**
> Ishita Soryan, SCSET, Bennett University

The project examines the gap between trust signals presented by AI-generated ("vibe-coded") interfaces and their externally observable security posture.

VibeAudit automates the checkable portion of the framework: HTTPS, privacy-policy presence, selected security response headers, and text-based patterns associated with trust inflation. It then computes the corresponding TSGA score.

It does **not** claim to fully automate TSGA assessment. Visual professionalism, interaction patterns, feature-attribution cues, and the Habituation Risk Index (HRI) require human assessment.

---

## Research Context

The tool was developed as the implementation companion to the accompanying research paper.

The paper defines TSGA as:

```text
gap = UTST_normalized - SPC_normalized

TSGA_base = gap * (1 + HRI)
```

where:

- **UTST** = User Trust Signal Taxonomy
- **SPC** = Security Posture Checklist
- **HRI** = Habituation Risk Index

HRI is normalized to a 0–1 scale. When HRI is not assessed, the tool uses HRI = 0, so the multiplier remains 1, and reports the HRI source as not_assessed.

The paper's pilot study evaluated 25 publicly accessible AI-generated or AI-assisted interfaces. The reported pilot scores ranged from **-7.87 to 10.80**.

The paper treats the negative-gap case separately: a negative score indicates that the observable security posture exceeds the measured trust-signal subtotal rather than representing a security deficit.

---

## Current Implementation

The current repository contains an expanded implementation of the paper's framework.

### Paper Reproducibility Note

The pilot results reported in the accompanying paper were produced using the earlier implementation described in the paper's methodology. The current repository contains subsequent extensions to the automated text-pattern checks. The current `main` branch should therefore be understood as the continuing implementation of the framework, rather than as an exact snapshot of the software state used for every pilot result.

The research paper describes the automated evaluation used in its pilot as a smaller text-detectable subset of the UTST taxonomy. The repository has since been extended to include additional text-detectable patterns while retaining the paper's scoring framework.

The current implementation includes:

- HTTPS detection
- Final-URL security checking after redirects
- HTTPS-to-HTTP downgrade detection
- Privacy-policy link detection
- Selected security response-header checks
- Text-based UTST pattern detection
- TSGA score calculation
- Manual HRI input
- Optional time-projection calculation when an explicit `drift_rate` is supplied
- CLI auditing
- Batch auditing
- Web UI and API
- Offline unit and integration tests

The additional text patterns are heuristic extensions and are not presented as empirically validated additions to the original taxonomy.

---

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Web Application

```bash
uvicorn api.server:app --reload
```

Then open:

```text
http://localhost:8000
```

### Audit a Single URL

```bash
python -m vibeaudit audit https://example.com
```

### Audit with a Manually Supplied HRI

```bash
python -m vibeaudit audit https://example.com --hri 0.6 --json --out result.json
```

### Batch Audit

Input file:

```text
urls.csv
```

One URL per line, or:

```text
name,url
```

Run:

```bash
python -m vibeaudit batch urls.csv --output results.csv
```

Markdown report:

```bash
python -m vibeaudit batch urls.csv --output report.md --format md
```

HTML report:

```bash
python -m vibeaudit batch urls.csv --output report.html --format html
```

---

## Run the Tests

```bash
pytest tests/
```

The test suite uses local HTML fixtures and a throwaway in-process HTTP server. Tests do not require outbound network access.

---

## Project Structure

```text
vibeaudit/
├── api/
│   └── server.py
├── frontend/
├── tests/
├── vibeaudit/
│   ├── fetcher
│   ├── scorer
│   ├── patterns
│   ├── CLI
│   ├── reports
│   └── TSGA scoring
├── .gitignore
├── CITATION.cff
├── LICENSE
├── README.md
├── leaderboard.json
└── requirements.txt
```

The core library contains the scoring and auditing logic, while the API and CLI act as interfaces to the same pipeline.

---

## Automated Checks

The current implementation automatically evaluates:

### Security Posture

- HTTPS presence
- Final URL after redirects
- HTTPS-to-HTTP downgrade
- Privacy-policy link presence
- Content-Security-Policy
- Strict-Transport-Security
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy

### Trust-Signal Text Patterns

The current implementation contains fourteen text-detectable patterns covering areas such as:

- Confidence and numerical performance claims
- AI capability claims
- Process-transparency labels
- Security claims and security-theater phrasing
- Testimonials and user ratings
- Third-party recognition and launch badges
- Guarantee or risk-reversal language
- Manufactured urgency and scarcity
- Live-activity social-proof signals
- Press and media endorsement
- Superlative authority claims
- Uncertainty acknowledgments

These patterns operate on text/HTML that can be inspected without a human evaluating the visual design.

---

## What Remains Manual

VibeAudit deliberately does not attempt to infer every component of TSGA automatically.

The following require human assessment:

- Visual professionalism
- Layout quality
- Professional iconography
- Feature-attribution highlights
- Interaction confidence patterns
- Habituation Risk Index (HRI)
- Trust signals that cannot be reliably detected from page text or HTML
- UTST dimensions outside the automated implementation

A page receiving a low automated score is **not** a clean bill of health.

The tool is intended to identify candidates for further assessment, not to replace a security audit or human evaluation.

---

## TSGA Scoring

The automated subtotals are normalized to a 0–10 scale relative to the maximum available points for the current automated checks.

The base score is:

```text
TSGA_base = (UTST_normalized - SPC_normalized) * (1 + HRI_normalized)
```

where `HRI_normalized` ranges from 0 to 1.

If HRI is not assessed, the multiplier defaults to 1.

The current implementation classifies scores as:

Score	Band
< 2	Low
2.0–<5.0	Moderate
5.0–<8.0	High
≥ 8.0	Severe


Negative scores are treated as part of the lowest reporting band by the implementation. In the research paper, negative gaps are discussed separately because they represent cases where the observable security posture exceeds the measured trust-signal subtotal.

---

## Time Projection

The framework also defines a projected score:

```text
TSGA_projected(t) = TSGA_base + (HRI_normalized * drift_rate * t)
```

The `drift_rate` parameter does not currently have an empirically validated value.

For that reason, VibeAudit does not silently invent a drift rate. A projection is only produced when an explicit `drift_rate` is supplied.

A longitudinal user study is required to empirically estimate this parameter.

---

## Limitations

Several limitations are important when interpreting results:

- JavaScript is not executed during the basic fetch workflow. Client-side-rendered pages may therefore appear nearly empty.
- Multilingual pattern coverage is partial.
- Privacy-policy detection currently covers multiple languages, but this is not exhaustive.
- Trust-signal text detection covers only a subset of languages and may under-report non-Latin scripts and long-tail languages.
- Response bodies are capped at 3 MB.
- Non-HTML content is not text-scored, although HTTPS and response-header checks still apply.
- Private, loopback, and link-local targets are blocked by default by the SSRF guard.
- Security headers require a real HTTP fetch.
- Visual trust signals cannot reliably be evaluated from raw HTML alone.
- Additional text patterns in the current implementation are heuristic extensions and are not independently validated.
- The UTST weights are theory-informed rather than empirically calibrated.
- The HRI has not been empirically calibrated against repeated user exposure.
- The `drift_rate` parameter requires longitudinal validation.
- The pilot study described in the accompanying paper is limited in sample size and does not establish external validity.

---

## Research Paper

**Explaining Away Security: XAI UI Patterns, Habituation, and the Trust-Security Gap in AI-Generated Interfaces**

**Author:** Ishita Soryan
**Institution:** SCSET, Bennett University

The paper describes the theoretical framework, pilot study, scoring methodology, limitations, and future validation work associated with VibeAudit.

An arXiv link and publication DOI will be added here once available.

---

## Citation

If you use VibeAudit or the TSGA framework in academic work, please cite the accompanying research paper.

```text
Soryan, I. "Explaining Away Security: XAI UI Patterns, Habituation, and the Trust-Security Gap in AI-Generated Interfaces."
```

A formal citation identifier will be added after publication or arXiv submission.

---

## License

This project is released under the MIT License. See [LICENSE](LICENSE).