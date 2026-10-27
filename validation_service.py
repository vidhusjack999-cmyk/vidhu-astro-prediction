# -*- coding: utf-8 -*-
"""
validation_service.py
Deterministic Validation & Critic Engine for Vidhu Astro Prediction (zero tokens).

Provides:
- validate_prediction_output(text, chart, fact_pack=None) -> (is_valid, issues)
- validate_detailed(text, chart, fact_pack=None) -> {'valid': bool, 'errors': [...], 'warnings': [...]}
"""
import re
from datetime import datetime, timezone, timedelta

import human_voice
import dosha_rules as dr

# Indian Standard Time (IST) offset: UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------- Multilingual Planet Aliases
ALIASES = {
    "sun": ["sun", "surya", "ravi", "சூரியன்"],
    "moon": ["moon", "chandra", "chandran", "சந்திரன்"],
    "mars": ["mars", "chevvai", "sevvai", "mangala", "kuja", "செவ்வாய்"],
    "mercury": ["mercury", "budha", "budhan", "புதன்"],
    "jupiter": ["jupiter", "guru", "குரு"],
    "venus": ["venus", "sukra", "shukra", "sukkiran", "சுக்கிரன்"],
    "saturn": ["saturn", "sani", "shani", "சனி"],
    "rahu": ["rahu", "raahu", "ragu", "raagu", "ராகு"],
    "ketu": ["ketu", "kethu", "கேது"],
}

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]

RASI_NAMES = [
    "Mesha", "Rishaba", "Mithuna", "Kataka",
    "Simha", "Kanya", "Tula", "Vrichika",
    "Dhanus", "Makara", "Kumbha", "Meena"
]

RASI_OWNERS = {
    0: "mars", 1: "venus", 2: "mercury", 3: "moon",
    4: "sun", 5: "mercury", 6: "venus", 7: "mars",
    8: "jupiter", 9: "saturn", 10: "saturn", 11: "jupiter"
}

# Standard Verdict approved phrases for Critic Pass 1
APPROVED_VERDICTS = {
    "CAREER_FIRST": ["career first", "career comes first", "career takes priority", "career takes precedence"],
    "MARRIAGE_DELAYED": ["marriage is delayed", "partnership timing is delayed", "marriage unfolds at a mature age", "marriage delayed"],
    "CONDITIONAL": ["conditional", "depends on individual circumstances", "requires situational verification", "conditional on"],
    "POSSIBLE": ["possible with specific caveats", "possible with caveats", "indicates potential", "possible"],
    "UNLIKELY": ["unlikely during the current cycle", "obstructed in this phase", "unlikely"]
}


def _has(text_lower, alias):
    if not alias:
        return False
    if alias.isascii():
        return re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text_lower) is not None
    return alias in text_lower


def _canon(word):
    w = (word or "").lower().strip()
    if not w:
        return None
    for planet, names in ALIASES.items():
        if w in names:
            return planet
    return None


def _planets_named(text_lower):
    return {p for p, names in ALIASES.items() if any(_has(text_lower, n) for n in names)}


def _sentences(text):
    if not text:
        return []
    cleaned = re.sub(r"\b(mr|mrs|dr|prof|vol|no|vs|st)\.\s*", r"\1_dot_ ", text, flags=re.IGNORECASE)
    raw_sents = [s for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if s.strip()]
    return [s.replace("_dot_", ".").strip() for s in raw_sents if s.strip()]


# ---------------------------------------------------------------- Compliance & Safety Rules
GUARANTEE_PATTERNS = [
    r"\bguarantee[sd]?\b", r"\bassured\b", r"\bwill (?:definitely|certainly|surely)\b",
    r"\bcertainly (?:will|not)\b", r"\b100\s?%", r"\bno doubt\b", r"\bunquestionabl[ey]\b",
    r"\bsuccess is (?:assured|certain)\b", r"\bzero hallucination\b",
    r"\bcompletely (?:lifted|cancelled|neutralized)\b", r"\bfully (?:cancelled|lifted)\b",
    r"\bshields (?:your|the) marriage\b", r"\bdivine protection ensures\b"
]

SENSITIVE_PATTERNS = [
    r"\bdivorce\b", r"\bsecond marriage\b", r"\bseparation\b", r"\bwidow\b", r"\blifespan\b",
    r"\byou will die\b", r"\bdeath\b", r"\bfatal\b", r"\bterminal\b",
]

SPOUSE_DETAIL_PATTERNS = [
    r"(?:husband|wife|spouse|partner)[^.\n]{0,60}\b(?:tall|fair|dark|handsome|slim|complexion|facial features)\b",
    r"(?:husband|wife|spouse|partner)[^.\n]{0,80}\b(?:north|south|east|west)(?:-?(?:east|west))?\b[^.\n]{0,20}\b(?:direction|region|side)\b",
    r"\bage gap\b", r"(?:husband|wife|spouse|partner)[^.\n]{0,60}\b(?:years older|years younger)\b",
]

PLACEHOLDER_PATTERNS = [r"\bNative\b[,.:]", r"\bHello Native\b", r"no dosha recorded", r"provided chart details"]

TRUNCATION_PATTERNS = [
    r"[-–—:]\s*$",
    r"\b\d+\.\s+[A-Za-z\s]+[-–—]\s*$",
    r"\b(?:and|or|but|with|that|as)\s*$"
]

CONTRADICTION_PATTERNS = [
    (r"\bjobless until 2028\b", "Contradiction: Claims native will be jobless until 2028 despite active positive sub-period/transits."),
    (r"\bno job (?:possible|available) until 2028\b", "Contradiction: Unconditionally rules out employment for multi-year Dasa duration."),
    (r"\byou may get or you may not get\b", "Ambiguity: Speeds into non-committal hedging instead of decisive analysis."),
    (r"\byou might or might not\b", "Ambiguity: Evasive prediction wording prohibited.")
]

DOSHA_KEYS = {
    "kemadruma": ["kemadruma"],
    "sarpa": ["sarpa", "rahu-ketu dosha", "naga dosha"],
    "manglik": ["manglik", "chevvai", "kuja dosha", "mangal dosha"],
    "punarphu": ["punarphu", "punarphoo"],
    "pitru": ["pitru"],
    "guru chandala": ["guru chandal"],
    "grahan": ["grahan"],
    "chandra": ["chandra dosha", "chandra dosham"],
    "shrapit": ["shrapit"],
    "kaal sarp": ["kaal sarp", "kaalsarp", "kalsarp"],
}

DENY = (
    "not present", "absent", "no ", "cancel", "neutraliz", "neutralis", "nullif",
    "free from", "does not", "not formed", "isn't", "is not"
)

RUN_WORDS = re.compile(r"\b(currently|right now|at present|presently|running|active|ongoing|now in|as of)\b")


# ---------------------------------------------------------------- Individual Verification Passes
def _dosha_key(name_lower):
    for key, tokens in DOSHA_KEYS.items():
        if any(t in name_lower for t in tokens):
            return key
    return None


def check_verdict_first(text, fact_pack):
    """Enforces that Sentence 1 must clearly state the deterministic verdict."""
    if not fact_pack or not isinstance(fact_pack, dict):
        return []

    verdict_code = fact_pack.get("verdict_code") or fact_pack.get("verdict")
    if not verdict_code:
        return []

    sents = _sentences(text)
    if not sents:
        return ["Empty output: no verdict found in sentence 1."]

    first_sent = sents[0].lower()
    approved_phrases = APPROVED_VERDICTS.get(str(verdict_code).upper(), [])
    if not approved_phrases and isinstance(verdict_code, str):
        approved_phrases = [verdict_code.lower()]

    matches = any(phrase in first_sent for phrase in approved_phrases)
    if not matches:
        return [
            f"Sentence 1 Verdict Missing: Sentence 1 must state verdict for '{verdict_code}'. "
            f"Expected one of {approved_phrases}, but got: \"{sents[0][:100]}\""
        ]
    return []


def check_window_matching(text, fact_pack):
    """Verifies that every date range stated in text strictly matches a window in the fact pack."""
    if not fact_pack or not isinstance(fact_pack, dict):
        return []

    favorable_windows = fact_pack.get("favorable_windows") or fact_pack.get("windows") or []
    if not favorable_windows:
        return []

    allowed_ranges = set()
    for w in favorable_windows:
        if isinstance(w, dict):
            start = w.get("start") or w.get("start_date") or ""
            end = w.get("end") or w.get("end_date") or ""
            if start and end:
                allowed_ranges.add((str(start).strip(), str(end).strip()))
            window_str = w.get("window", "")
            if window_str:
                allowed_ranges.add(window_str.strip())

    issues = []
    # Find all date-range patterns like DD-MM-YYYY to DD-MM-YYYY or YYYY-MM-DD to YYYY-MM-DD
    found_ranges = re.findall(
        r"(\d{2,4}[-/]\d{2}[-/]\d{2,4})\s+(?:to|–|-)\s+(\d{2,4}[-/]\d{2}[-/]\d{2,4})",
        text,
        re.IGNORECASE
    )

    for start_found, end_found in found_ranges:
        matched = False
        pair = (start_found.strip(), end_found.strip())
        combined = f"{start_found} to {end_found}"
        for allowed in allowed_ranges:
            if isinstance(allowed, tuple) and pair == allowed:
                matched = True
                break
            elif isinstance(allowed, str) and (combined in allowed or f"{pair[0]} to {pair[1]}" in allowed):
                matched = True
                break
        if not matched and allowed_ranges:
            issues.append(f"Unverified Window: Date range '{combined}' does not match any computed Fact Pack window.")

    return list(dict.fromkeys(issues))


def check_all_lordships(text, chart):
    """Verifies all claimed house lordships against the calculated Lagna lordship table."""
    planets = chart.get("planets") or chart.get("planetary_positions_and_dignity") or {}
    lagna_info = planets.get("Lagna", {})
    if "rasi_idx" not in lagna_info:
        return []

    lagna_idx = lagna_info["rasi_idx"]
    # Build house-to-lord map for this Lagna
    house_to_lord = {}
    for h in range(1, 13):
        sign_idx = (lagna_idx + h - 1) % 12
        house_to_lord[h] = RASI_OWNERS[sign_idx]

    issues = []
    tl = text.lower()

    # Match claims like: "Saturn ruling your professional house" or "Saturn, ruler of the 10th house"
    career_patterns = [
        r"([a-z]+)\s+ruling\s+(?:your\s+)?(?:professional|career|10th)\s+house",
        r"([a-z]+)[,\s]+(?:lord|ruler)\s+of\s+(?:the\s+)?(?:10th\s+house|career|profession)",
    ]
    for pat in career_patterns:
        for m in re.finditer(pat, tl):
            p = _canon(m.group(1))
            actual_10th = house_to_lord[10]
            if p and p != actual_10th:
                issues.append(
                    f"Wrong Lordship claim: text states '{m.group(1).capitalize()}' rules the 10th/career house. "
                    f"For {RASI_NAMES[lagna_idx]} Lagna, the 10th lord is {actual_10th.capitalize()}."
                )

    # General house lordship pattern: "[Planet] rules/is lord of [N]th house"
    general_pat = r"([a-z]+)\s+(?:rules|is\s+lord\s+of|as\s+the\s+lord\s+of)\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+house"
    for m in re.finditer(general_pat, tl):
        p = _canon(m.group(1))
        h_num = int(m.group(2))
        if p and 1 <= h_num <= 12:
            correct_lord = house_to_lord[h_num]
            if p != correct_lord:
                issues.append(
                    f"Lordship Mismatch: text claims {p.capitalize()} rules House {h_num}. "
                    f"Actual lord is {correct_lord.capitalize()}."
                )

    return list(dict.fromkeys(issues))


def check_evidence_and_balance(text, fact_pack):
    """Ensures at least 3 supporting factors and at least 1 opposing factor are cited when present."""
    if not fact_pack or not isinstance(fact_pack, dict):
        return []

    opposing = fact_pack.get("opposing_factors", [])
    supporting = fact_pack.get("supporting_factors", [])
    tl = text.lower()
    issues = []

    # If opposing factors exist, text must cite at least one opposing/delay factor
    if opposing:
        opp_found = any(any(_has(tl, word) for word in re.findall(r"\b[a-zA-Z]{4,}\b", str(item).lower())) for item in opposing)
        if not opp_found:
            issues.append("Unbalanced Advice: text omits all opposing/friction factors present in the chart fact pack.")

    # Must mention at least 3 distinct planets
    named = _planets_named(tl)
    if len(named) < 3:
        issues.append(f"Insufficient Planetary Evidence: expected at least 3 planetary citations, found {len(named)}.")

    return issues


def check_transit_vs_natal(text):
    """Rejects using temporary Gocharam transits to explain static natal realities (e.g. siblings, parents)."""
    tl = text.lower()
    issues = []

    # Sibling natal questions must not blame Ketu/Saturn transits
    if re.search(r"\b(?:sibling|brother|sister|only child)\b", tl):
        if re.search(r"transit\s+(?:of\s+)?(?:ketu|saturn|rahu|jupiter)[^.\n]{0,80}(?:no siblings|only child|prevented siblings)", tl):
            issues.append("Natal vs Transit Violation: Cited a temporary transit as the cause of a lifelong natal sibling condition.")

    return issues


def check_stale_dates(text, today=None):
    """Detects expired 'currently transiting' or 'until [date]' statements."""
    today = today or datetime.now(IST)
    if today.tzinfo is None:
        today = today.replace(tzinfo=IST)

    tl = text.lower()
    issues = []

    # Check for Jupiter in Cancer claims past 31-10-2026
    if "jupiter" in tl and ("kataka" in tl or "cancer" in tl) and ("currently" in tl or "transiting" in tl):
        cutoff = datetime(2026, 10, 31, 23, 59, 59, tzinfo=IST)
        if today > cutoff:
            issues.append(
                f"Stale Transit Date: Jupiter left Kataka (Cancer) on 31-10-2026. "
                f"Text asserts Jupiter is currently in Cancer as of {today.strftime('%d-%m-%Y')}."
            )

    return issues


def check_repeat_tips(text):
    """Rejects repetitive generic stock remedies/tips appearing across sections."""
    issues = []
    meditation_count = len(re.findall(r"\b(?:10|15)\s*minutes?(?:\s+of)?\s+(?:morning\s+)?(?:meditation|grounding)\b", text, re.IGNORECASE))
    if meditation_count > 1:
        issues.append(f"Repetitive Stock Advice: Generic morning meditation tip repeated {meditation_count} times in the report.")
    return issues


def check_unsupported_personal_assertions(text):
    """Bans unverified biographical declarations like 'you are an only child'."""
    issues = []
    if re.search(r"\b(?:you are an only child|being an only child)\b", text, re.IGNORECASE):
        issues.append("Speculative Personal Assertion: Asserts 'you are an only child' without natal confirmation.")
    return issues


def check_doshas(text, chart):
    issues = []
    doshas = chart.get("doshas") or chart.get("dosha_status") or []
    sents = [(s, s.lower()) for s in _sentences(text)]

    for d in doshas:
        name = (d.get("name") or d.get("dosha_name") or "")
        key = _dosha_key(name.lower())
        status = (d.get("status") or "").upper()
        if not key or not status:
            continue
        tokens = DOSHA_KEYS[key]
        for raw, sl in sents:
            if not any(t in sl for t in tokens):
                continue
            denies = any(w in sl for w in DENY)
            claims_present = re.search(r"\bpresent\b|\bis formed\b|\bafflict", sl) and not denies
            if status.startswith("NOT") and claims_present:
                issues.append(
                    f"Dosha contradiction: {name} is NOT PRESENT in data, but text says present: \"{raw.strip()[:120]}\"")
                break
            if status == "PRESENT" and denies and re.search(
                    r"not present|absent|completely cancel|fully cancel|does not exist", sl):
                issues.append(
                    f"Dosha contradiction: {name} is PRESENT in data, but text denies it: \"{raw.strip()[:120]}\"")
                break
    return issues


def check_running_period(text, chart, today):
    """Catches 'currently running X dasa/bhukti' when X is a future or past period."""
    if not hasattr(human_voice, "current_period"):
        return []
    dasa, bhukti, _ = human_voice.current_period(chart, today)
    issues = []
    if not dasa:
        return issues
    markers = (
        "upcoming", "next", "following", "begin", "start", "after", "transition", "was ",
        "earlier", "previous", "past", "ended", "into", "from ", "will be", "until", "through"
    )

    def stated(sl, pattern, actual, label):
        for m in re.finditer(pattern, sl):
            prefix = sl[max(0, m.start() - 45):m.start()]
            if any(mk in prefix for mk in markers):
                continue
            p = _canon(m.group(1))
            if p and p != actual.lower():
                issues.append(
                    f"Wrong running {label}: text says {m.group(1)} {label} is running, calculation says {actual}.")

    for raw in _sentences(text):
        sl = raw.lower()
        if not RUN_WORDS.search(sl):
            continue
        stated(sl, r"([a-z\u0b80-\u0bff]+)\s+(?:maha\s?)?dasa\b", dasa, "dasa")
        if bhukti:
            stated(sl, r"([a-z\u0b80-\u0bff]+)\s+(?:bhukti|antardasa)\b", bhukti, "bhukti")
    return list(dict.fromkeys(issues))


def check_combustion(text, chart):
    """Attributes 'combust' claims to the nearest planet named immediately before it."""
    planets = chart.get("planets") or chart.get("planetary_positions_and_dignity") or {}
    if "Sun" not in planets:
        return []

    actual = {p.lower() for p, data in planets.items() if isinstance(data, dict) and data.get("is_combust")}
    if not actual and hasattr(dr, "combust_planets"):
        actual = {p.lower() for p in dr.combust_planets(planets)}

    issues = []
    for raw in _sentences(text):
        sl = raw.lower()
        for m in re.finditer(r"combust|\basta\b", sl):
            prefix = sl[max(0, m.start() - 12):m.start()]
            if "not " in prefix or "un" in prefix[-3:]:
                continue
            window = sl[max(0, m.start() - 40):m.start()]
            hits = [(window.rfind(n), p) for p, names in ALIASES.items() for n in names if n in window]
            if not hits:
                continue
            p = max(hits)[1]
            if p in ("moon", "mars", "mercury", "jupiter", "venus", "saturn") and p not in actual:
                issues.append(
                    f"Combustion claim: text says {p.capitalize()} is combust, but it is outside the combustion limit.")
    return list(dict.fromkeys(issues))


def check_moolatrikona_claims(text, chart):
    """Verifies that Moolatrikona claims in generated text match verified degree zones."""
    issues = []
    planets = chart.get("planets") or chart.get("planetary_positions_and_dignity") or {}
    for raw in _sentences(text):
        sl = raw.lower()
        if "moolatrikona" in sl or "moola trikona" in sl or "மூலத்திரிகோணம்" in sl:
            named = _planets_named(sl)
            for p in named:
                p_cap = p.capitalize()
                p_info = planets.get(p_cap, {})
                dignity = p_info.get("dignity", "")
                if "Moolatrikona" not in dignity:
                    issues.append(f"Invalid Moolatrikona claim: text states {p_cap} is in Moolatrikona, but its actual state is {dignity}.")
    return issues


def check_contradictions(text):
    issues = []
    for pat, desc in CONTRADICTION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            issues.append(desc)
    return issues


def check_anchors(text, min_planets=2):
    tl = text.lower()
    named = _planets_named(tl)
    house = re.search(
        r"\b\d{1,2}(?:st|nd|rd|th)\s+house\b|\bhouse\s+\d{1,2}\b|\b(?:mesha|rishaba|mithuna|kataka|simha|kanya|tula|vrichika|dhanus|makara|kumbha|meena)\b",
        tl
    )
    if len(named) < min_planets or not house:
        return [
            f"Too generic: name at least {min_planets} planets and one house or sign from chart (found {len(named)} planets)."]
    return []


def check_truncation_and_structure(text):
    issues = []
    stripped = text.strip()

    for pat in TRUNCATION_PATTERNS:
        if re.search(pat, stripped, re.MULTILINE):
            issues.append("Truncation error: output ends abruptly mid-sentence or on a dangling dash/conjunction.")
            break

    count_match = re.search(r"here are the (\d+) most important insights", stripped, re.IGNORECASE)
    if count_match:
        expected = int(count_match.group(1))
        found_points = len(re.findall(r"(?:^|\n|\<p\>)\s*(?:\<strong\>)?\d+\.", stripped))
        if found_points < expected:
            issues.append(f"Incomplete list: text promised {expected} insights, but only generated {found_points}.")

    return issues


def check_patterns(text):
    issues = []
    groups = [
        (GUARANTEE_PATTERNS, "Guarantee language"),
        (SENSITIVE_PATTERNS, "Sensitive topic the prompt forbids"),
        (SPOUSE_DETAIL_PATTERNS, "Unsupported spouse detail (looks, direction or age)"),
        (PLACEHOLDER_PATTERNS, "Placeholder or missing-data text"),
    ]
    for patterns, label in groups:
        for pat in patterns:
            m = re.search(pat, text, re.I if label != "Placeholder or missing-data text" else 0)
            if m:
                issues.append(f"{label}: \"{m.group(0)[:80]}\"")
                break
    return issues


def month_year_warnings(text, chart, today):
    known = set()
    for d in chart.get("dasa_bhukti") or []:
        for x in [d.get("start_date"), d.get("end_date")] + [v for a in d.get("antardasas", []) or [] for v in
                                                             (a.get("start_date"), a.get("end_date"))]:
            dt = None
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(str(x), fmt)
                    break
                except ValueError:
                    pass
            if dt:
                known.add((dt.month, dt.year))
    known.add((today.month, today.year))
    out = []
    for raw in _sentences(text):
        sl = raw.lower()
        if not re.search(r"bhukti|dasa|antardasa", sl):
            continue
        for mname, yr in re.findall(rf"\b({'|'.join(MONTHS)})\s+(20\d\d)\b", sl):
            if (MONTHS.index(mname) + 1, int(yr)) not in known:
                out.append(f"{mname.capitalize()} {yr} is mentioned with a dasa/bhukti but is not a period boundary.")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- Primary Entry Points
def validate_detailed(generated_text, chart, today=None, kind="report", fact_pack=None):
    """
    Evaluates generated text against both ground-truth chart calculations and the Fact Pack.
    Returns: {'valid': bool, 'errors': [...], 'warnings': [...]}
    """
    today = today or datetime.now(IST)
    if not generated_text or not isinstance(generated_text, str):
        return {"valid": False, "errors": ["Output error: generated text is empty or invalid."], "warnings": []}

    chart = chart or {}
    fact_pack = fact_pack or chart.get("fact_pack")
    errors, warnings = [], []

    usable = human_voice.chart_is_usable(chart) if hasattr(human_voice, "chart_is_usable") else bool(chart)
    if not usable:
        warnings.append("Chart data missing or incomplete: data-based checks were skipped.")
    else:
        timeline = chart.get("dasa_bhukti") or []
        dob = (chart.get("_meta") or {}).get("dob") or chart.get("dob")

        if hasattr(human_voice, "allowed_dates") and hasattr(human_voice, "find_bad_dates"):
            allowed = human_voice.allowed_dates(timeline, dob=dob, today=today)
            bad = human_voice.find_bad_dates(generated_text, allowed)
            if bad:
                errors.append(f"Date hallucination: dates not in timeline: {bad}")

        errors += check_running_period(generated_text, chart, today)
        errors += check_all_lordships(generated_text, chart)
        errors += check_doshas(generated_text, chart)
        errors += check_combustion(generated_text, chart)
        errors += check_moolatrikona_claims(generated_text, chart)

        if hasattr(human_voice, "current_period"):
            dasa, bhukti, _ = human_voice.current_period(chart, today)
            tl = generated_text.lower()
            if kind == "report" and dasa and not any(_has(tl, n) for n in ALIASES.get(dasa.lower(), [dasa.lower()])):
                errors.append(f"The running {dasa} dasa is never mentioned.")

        warnings += month_year_warnings(generated_text, chart, today)

    # Substantive Fact Pack & Critic Checks
    if fact_pack:
        errors += check_verdict_first(generated_text, fact_pack)
        errors += check_window_matching(generated_text, fact_pack)
        errors += check_evidence_and_balance(generated_text, fact_pack)

    errors += check_transit_vs_natal(generated_text)
    errors += check_stale_dates(generated_text, today)
    errors += check_repeat_tips(generated_text)
    errors += check_unsupported_personal_assertions(generated_text)
    errors += check_contradictions(generated_text)
    errors += check_truncation_and_structure(generated_text)
    errors += check_patterns(generated_text)
    errors += check_anchors(generated_text, min_planets=2 if kind == "report" else 1)

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def validate_prediction_output(generated_text: str, ground_truth_chart: dict, today=None, kind="report", fact_pack=None):
    """Drop-in interface returning (is_valid, hard_errors)."""
    r = validate_detailed(generated_text, ground_truth_chart, today=today, kind=kind, fact_pack=fact_pack)
    return r["valid"], r["errors"]