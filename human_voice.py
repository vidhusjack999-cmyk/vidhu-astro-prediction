# -*- coding: utf-8 -*-
"""
human_voice.py - Humanoid Voice & Persona Guardrails for Vidhu Astro Prediction.

DUAL-STAGE PIPELINE SCOPE:
1. PROMPT STAGE: Injects `style_block()` guidelines into system instructions to shape tone,
   prohibit placeholder terms like "Native", and enforce South Indian astrological style rules.
2. POST-PROCESSING STAGE: Runs `tidy()` to strip leftover AI menu footers, disclaimers,
   and markdown dividers prior to report rendering while strictly preserving exact report headers.
"""

import re
from datetime import datetime, date

STYLE_RULES_EN = """
[VOICE - Write like a warm, experienced South Indian astrologer talking directly to one person]
- Speak to the person as "you". Use plain, natural, flowing sentences and vary sentence length.
- Open with the main theme in 1 or 2 clear sentences, followed by astrological reasoning.
- Pick the 3 most important insights for this specific topic. Do NOT list every planet placement or yoga.
- Explain technical terms (dasa, bhukti, dosha) simply the first time they appear.
- Be specific: give relevant time windows (month and year) and 1 practical action step.
- Never repeat raw chart details, birth facts, or long planetary lists that the user already sees.
- Sound confident where the chart is clear, and honest where planetary influences are mixed.
- Avoid AI buzzwords: profound, robust, tapestry, testament, delve, navigate, journey, harmonious, unwavering.
- ABSOLUTE WORD BAN: NEVER use the word "Native", "Hello Native", or "Dear Native" anywhere in the document.
- No ALL CAPS headings, no ASCII borders (====, ----), and no bracketed timelines like "[1985-1989] Moon Dasa".
- Short paragraphs (2 to 4 sentences). Use bolding sparingly for key terms or date windows.
- Length: 250-400 words for topic readings, 80-150 words for chat answers.
"""

STYLE_RULES_TA = """
[VOICE - தமிழ் ஜோதிடர் நடை]
- வாடிக்கையாளரிடம் நேரடியாக உரையாடும் வகையில் இயல்பான, தெளிவான தமிழில் எழுதவும்.
- முதல் 1-2 வரிகளிலேயே முதன்மை பலனைத் தெளிவாகக் கூறி, பின்னர் அதற்கான ஜோதிட காரணங்களை விளக்கவும்.
- கேட்கப்பட்ட தலைப்பிற்கு மிகவும் முக்கியமான 3 கருத்துக்களை மட்டும் கூறவும்.
- தசா, புக்தி, தோஷங்களை எளிய முறையில் விளக்கவும்.
- அட்டவணைகள், ASCII கோடுகள் (====, ----), மற்றும் "அடுத்த கட்டமாக என்ன பார்க்க விரும்புகிறீர்கள்?" போன்ற AI கேள்விகளை தவிர்க்கவும்.
- "Native" என்ற சொல்லை முற்றிலுமாக தவிர்க்கவும்.
"""

SENSITIVE_RULES = """
[CARE & ETHICS RULES]
- Never predict divorce, separation, second marriage, death, lifespan, severe accidents, or critical illness.
- For relationship concerns, focus on communication, patience, and constructive guidance. Never call a marriage doomed.
- For health queries, offer general wellness and lifestyle guidance only. Never offer medical diagnoses.
- Do not state a dosha is present or cancelled unless explicitly stated in the calculated chart data.
- Every date mentioned MUST come directly from the calculated Dasa timeline. If a date is missing, do not guess.
"""

TOPIC_FOCUS = {
    "work": "10th house and lord, 6th house, current dasa-bhukti, Saturn and Sun.",
    "career": "10th house and lord, 6th house, current dasa-bhukti, Saturn and Sun.",
    "marriage": "7th house and lord, Venus, Jupiter, Mars dosham status, current dasa-bhukti.",
    "matching": "7th house and lord, Venus, Jupiter, Mars dosham status, current dasa-bhukti.",
    "health": "Lagna and lord, 6th and 8th houses, Moon, current dasa-bhukti. General lifestyle advice only.",
    "finance": "2nd and 11th houses and lords, Jupiter, current dasa-bhukti.",
    "education": "4th, 5th and 9th houses, Mercury, Jupiter, current dasa-bhukti.",
    "dasa": "Current and next two dasa-bhukti periods and what each favours.",
    "dosha": "Only the doshas marked PRESENT in the chart payload, with cancellations explained simply.",
}


def style_block(
        topic: str = "",
        language: str = "English",
        greet: bool = False,
        first_name: str = ""
) -> str:
    """
    PROMPT STAGE: Generates combined style, care, and focus instructions based on topic and language.
    `greet=True` adds a personalized initial greeting instruction.
    """
    focus = TOPIC_FOCUS.get((topic or "").lower().strip(), "")
    focus_line = f"\n[FOCUS FOR THIS TOPIC]: {focus}\n" if focus else ""

    base_style = STYLE_RULES_TA if str(language).lower() == "tamil" else STYLE_RULES_EN

    greet_line = ""
    if greet:
        who = f" by first name ({first_name})" if first_name else ""
        greet_line = (
            f"\n[GREETING]: Greet the person once{who}, then go straight to the chart. "
            "Make the first sentence about their chart, not a general compliment.\n"
        )

    return base_style + SENSITIVE_RULES + greet_line + focus_line


_DATE_PATTERNS = [
    re.compile(r"\b(\d{2}-\d{2}-\d{4})\b"),  # DD-MM-YYYY
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")  # YYYY-MM-DD
]


def allowed_dates(dasa_timeline, dob=None, today=None):
    """
    Collects every valid date string present in the calculated Dasa timeline (Maha & Antardasa),
    plus birth date and today's date.
    """
    ok_dates = set()

    def _add_date(d_val):
        if not d_val:
            return
        if isinstance(d_val, (datetime, date)):
            ok_dates.add(d_val.strftime("%d-%m-%Y"))
            ok_dates.add(d_val.strftime("%Y-%m-%d"))
        elif isinstance(d_val, str):
            s = d_val.strip()
            if s:
                ok_dates.add(s)

    for d in dasa_timeline or []:
        if isinstance(d, dict):
            _add_date(d.get("start_date"))
            _add_date(d.get("end_date"))
            for a in d.get("antardasas", []) or []:
                if isinstance(a, dict):
                    _add_date(a.get("start_date"))
                    _add_date(a.get("end_date"))

    _add_date(dob)
    _add_date(today or date.today())
    return {x for x in ok_dates if x}


def find_bad_dates(text: str, allowed: set) -> list:
    """
    Identifies date strings in LLM output that do not exist in the allowed timeline set,
    or zero-length date ranges like '12-05-2025 to 12-05-2025'.
    """
    found_dates = []
    for pat in _DATE_PATTERNS:
        found_dates.extend(pat.findall(text))

    bad = [d for d in found_dates if d not in allowed]

    # Catch zero-length date ranges
    zero_range_pattern = r"(\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2})\s*(?:to|-|–)\s*\1"
    bad += [m.group(0) for m in re.finditer(zero_range_pattern, text)]

    return sorted(set(bad))


# Regex patterns to strip unwanted AI boilerplate, footers, and menu questions
_BOILER_PATTERNS = [
    r"(?im)^\s*note:\s*generated using.*$",
    r"(?im)^\s*(?:\d+\.\s*)?next steps(?:\s*&\s*discussion)?.*$",
    r"(?im)^\s*please indicate which.*$",
    r"(?im)^\s*would you like to (?:explore|delve|dive|examine|examine further).*$",
    r"(?im)^\s*as an ai astrologer.*$",
    r"(?im)^\s*in summary,.*$"
]


def tidy(text: str) -> str:
    """
    POST-PROCESSING STAGE: Cleans raw LLM output by removing AI menu footers,
    ASCII line breaks, and excessive blank lines while preserving exact report section headers.
    """
    if not text:
        return ""

    for pat in _BOILER_PATTERNS:
        text = re.sub(pat, "", text)

    # Remove ASCII dividers (e.g., ====, ----, ****)
    text = re.sub(r"(?m)^\s*[=_*~-]{3,}\s*$", "", text)

    # Compress 3 or more newlines into double newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()