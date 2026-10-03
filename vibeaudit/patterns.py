"""UTST pattern definitions.

Trust weights (1-3) follow Paper 2's UTST tables (Section 3.1) where the
pattern maps to one; the additional text-detectable patterns added since
(urgency/scarcity cues, live-activity tickers, guarantee language,
superlative authority claims, security-theater phrasing) are weighted by
analogy to the closest paper category and are flagged as such in review
notes. Only patterns realistically detectable from page text/HTML without a
human looking at the visual design are included here.

Multilingual coverage is intentionally documented rather than hidden. The
privacy-link regex covers English, French, Spanish, Portuguese, Dutch,
Turkish, German, Italian, Polish, and the Scandinavian languages. A handful
of the trust-signal patterns (testimonials, guarantees, superlatives,
urgency) carry French / Spanish / German / Italian keywords too. This is
still NOT exhaustive - non-Latin scripts and most long-tail languages are
not covered, and extending them remains the highest-value contribution.

Fourteen patterns are defined here. Patterns that need a human eye
(minimalist layout, professional iconography, feature-attribution
highlights) are deliberately left out - see the README for the full
manual/automated split.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextPattern:
    name: str
    category: str
    trust_weight: int
    regex: str


TEXT_PATTERNS: list[TextPattern] = [
    TextPattern(
        name="Confidence score displays",
        category="Explanation & Transparency",
        trust_weight=3,
        regex=r"\b\d{1,3}(\.\d+)?\s?%\s?(accuracy|confidence|success|win rate|match)",
    ),
    TextPattern(
        name="Process transparency labels",
        category="Explanation & Transparency",
        trust_weight=2,
        regex=r"\b(AI[- ]generated|AI[- ]powered|powered by (machine learning|AI)|built with (AI|Lovable|v0|Bolt))\b",
    ),
    TextPattern(
        name="Uncertainty acknowledgment",
        category="Explanation & Transparency",
        trust_weight=1,
        regex=r"\b(may vary|estimated|approximately|could vary|not guaranteed|for informational purposes)\b",
    ),
    TextPattern(
        name="Security badge imagery (text form)",
        category="Security Indicator",
        trust_weight=3,
        regex=(
            r"\b(SOC ?2|ISO ?27001|ISO ?9001|GDPR[- ]compliant|bank[- ]level encryption|"
            r"HIPAA[- ]compliant|PCI[- ]DSS|CCPA[- ]compliant|FedRAMP|FERPA[- ]compliant|"
            r"Cyber Essentials|Datenschutz[- ]konform)\b"
        ),
    ),
    TextPattern(
        name="Security theater phrasing",
        category="Security Indicator",
        trust_weight=2,
        regex=(
            r"\b(military[- ]grade encryption|256[- ]bit (SSL|encryption)|SSL[- ]secured|"
            r"secure checkout|100% secure|bank[- ]grade security|"
            r"your (data|information|privacy) is (100% )?(safe|secure|protected)|"
            r"unhackable|completely secure|totally secure)\b"
        ),
    ),
    TextPattern(
        name="User review or rating displays",
        category="Social Proof & Authority",
        trust_weight=2,
        regex=(
            r"(\u2605{2,}|\btestimonial(s)?\b|\bt[ée]moignages?\b|"
            r"\btestimonianze?\b|\bRezensionen?\b|\bBewertungen\b|"
            r"\btrusted by [\d,]+|\bjoin(ed by)? [\d,]+\+? (happy )?(users|customers)|"
            r"\b[\d,]+\+? (users|customers|downloads|reviews|ratings|"
            r"clientes|utilisateurs|utenti|Nutzer|Kunden|u[zż]ytkownik[oó]w))"
        ),
    ),
    TextPattern(
        name="Third-party launch/recognition badges",
        category="Social Proof & Authority",
        trust_weight=1,
        regex=r"\b(Featured on|Product Hunt|#1 Product of the Day|Top \d+ (Daily|Weekly)|SaasHunt|Startup Fame|PeerPush|KittyLaunch|LaunchBuff)\b",
    ),
    TextPattern(
        name="Unverified numerical performance claims",
        category="Social Proof & Authority",
        trust_weight=3,
        regex=(
            r"\b\d{1,3}(\.\d+)?%\s?(win rate|accuracy|success rate|faster|savings)|"
            r"\bsave(d)?\s?\$[\d,]+|\b\d{1,3}[x\u00d7]\s?(faster|more|better|quicker)"
        ),
    ),
    TextPattern(
        name="Guarantee / risk-reversal language",
        category="Social Proof & Authority",
        trust_weight=2,
        regex=(
            r"\b(money[- ]back guarantee|100% (guarantee|guaranteed)|risk[- ]free|"
            r"satisfaction guaranteed|guaranteed results|"
            r"garantie? de remboursement|garant[i\u00ed]a de devoluci[o\u00f3]n|"
            r"Geld[- ]zur[u\u00fc]ck[- ]Garantie|soddisfatti o rimborsati)\b"
        ),
    ),
    TextPattern(
        name="Manufactured urgency / scarcity",
        category="Urgency & Scarcity Cues",
        trust_weight=2,
        regex=(
            r"\b(limited[- ]time offer|only \d+ (left|remaining|spots?|seats?)|"
            r"offer ends (soon|today|tonight|in \d+)|act now|hurry[,!]? |"
            r"\d+ spots? (left|remaining)|sale ends in \d+|"
            r"oferta por tiempo limitado|offre [\u00e0a] dur[\u00e9e]e limit[\u00e9e]e)\b"
        ),
    ),
    TextPattern(
        name="Live-activity social proof ticker",
        category="Social Proof & Authority",
        trust_weight=2,
        regex=(
            r"\b(\d+ (people|users|visitors|others) (are )?(viewing|online now|looking|"
            r"watching this)|just (purchased|signed up|bought|joined|subscribed)|"
            r"\d+ (sold|bought|claimed) (today|in the last|this week)|"
            r"someone (in|from) .{2,20} just (bought|purchased|signed up))\b"
        ),
    ),
    TextPattern(
        name="Press / media endorsement (text form)",
        category="Social Proof & Authority",
        trust_weight=1,
        regex=(
            r"\b(as (seen|featured) (in|on)|featured in the press|in the media|"
            r"press coverage)\b|"
            r"\b(TechCrunch|Forbes|Wired|Mashable|Business Insider|The Verge|"
            r"Entrepreneur Magazine|Fast Company)\b"
        ),
    ),
    TextPattern(
        name="Superlative authority claims",
        category="Social Proof & Authority",
        trust_weight=2,
        regex=(
            r"\b(award[- ]winning|industry[- ]leading|best[- ]in[- ]class|world[- ]class|"
            r"#1 (rated|ranked|choice)|market[- ]leading|the leading (platform|provider|"
            r"solution|tool)|trusted (industry )?standard|"
            r"l[i\u00ed]der del mercado|leader del mercato|Marktf[u\u00fc]hrer)\b"
        ),
    ),
    TextPattern(
        name="Vague AI capability claims",
        category="Explanation & Transparency",
        trust_weight=2,
        regex=(
            r"\b((state[- ]of[- ]the[- ]art|cutting[- ]edge|next[- ]gen(eration)?|"
            r"revolutionary|groundbreaking|most advanced) (AI|machine learning|"
            r"algorithms?|models?|neural network)|powered by GPT[- ]?\d?|"
            r"smartest AI|world'?s most advanced AI)\b"
        ),
    ),
]

PRIVACY_LINK_REGEX = (
    r"privacy policy|privacy-policy|/privacy\b|\bprivacy\b|"
    r"confidentialit[ée]|politique de confidentialit[ée]|"
    r"pol[ií]tica de privacidad|pol[ií]tica de privacidade|privacidade|"
    r"privacybeleid|gizlilik|"
    r"datenschutz(erkl[aä]rung|richtlinie)?|"  # German
    r"informativa sulla privacy|privacy e cookie|"  # Italian
    r"polityka prywatno[sś]ci|"  # Polish
    r"personvern|integritetspolicy|tietosuoja"  # Norwegian / Swedish / Finnish
)

# Security headers worth checking when fetch was done with a library that
# exposes response headers (the CLI/fetcher does; a browser-pasted-HTML
# workflow would not).
SECURITY_HEADERS_TO_CHECK = [
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
]

BLANK_PAGE_TEXT_LENGTH_THRESHOLD = 200
