# -*- coding: utf-8 -*-
"""
chart_matching_engine.py

Needs in the same folder: dosha_rules.py and porutham_fixed.py
(or matching_engine.py as fallback).
Return shapes are kept consistent with chart_matching.html templates.
"""
import logging
from datetime import datetime

# Import dosha_rules module if available; fallback gracefully
try:
    import dosha_rules as dr
except ImportError:
    dr = None

try:
    from porutham_fixed import calculate_porutham, get_star_index_by_name, RASI_DATA, FRIENDS
except ImportError:
    from matching_engine import calculate_porutham, get_star_index_by_name, RASI_DATA

    FRIENDS = {}

logger = logging.getLogger(__name__)

TRADITION = "tamil"  # "tamil" = Mars houses 2,4,7,8,12 | "north" adds the 1st house


# ---------------------------------------------------------------- DATES / DASA
def parse_flexible_date(date_str):
    """Parses DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY or YYYY/MM/DD."""
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None


def _timeline_of(chart_or_timeline):
    if isinstance(chart_or_timeline, dict):
        return (
            chart_or_timeline.get("dasa_bhukti")
            or chart_or_timeline.get("maha_dasa_and_dasa_bhukti_timeline", {}).get("timeline")
            or []
        )
    return chart_or_timeline if isinstance(chart_or_timeline, list) else []


def get_current_active_dasa(chart_or_timeline, reference_date=None):
    """Running Mahadasa for reference_date. Never labels a guess as 'Current'."""
    reference_date = reference_date or datetime.now()
    timeline = _timeline_of(chart_or_timeline)

    if not timeline:
        logger.warning("No dasa timeline found in chart payload")
        return "Unknown (no timeline data)"

    for dasa in timeline:
        s = parse_flexible_date(dasa.get("start_date"))
        e = parse_flexible_date(dasa.get("end_date"))
        lord = dasa.get("dasa_lord") or dasa.get("lord")

        if s and e and lord and s <= reference_date <= e:
            return f"{lord} Dasa (Current)"

    logger.warning(
        "No dasa matched %s. Timeline %s to %s",
        reference_date.date(),
        timeline[0].get("start_date") if timeline else "N/A",
        timeline[-1].get("end_date") if timeline else "N/A"
    )
    return "Unknown (no dasa matched today's date)"


def get_current_bhukti(chart_or_timeline, reference_date=None):
    """Returns (dasa_lord, bhukti_lord, bhukti_end_date) or (None, None, None)."""
    reference_date = reference_date or datetime.now()
    for d in _timeline_of(chart_or_timeline):
        s = parse_flexible_date(d.get("start_date"))
        e = parse_flexible_date(d.get("end_date"))

        if s and e and s <= reference_date <= e:
            for a in d.get("antardasas", []) or []:
                bs = parse_flexible_date(a.get("start_date"))
                be = parse_flexible_date(a.get("end_date"))
                if bs and be and bs <= reference_date <= be:
                    return d.get("dasa_lord"), a.get("sub_lord"), a.get("end_date")
            return d.get("dasa_lord"), None, d.get("end_date")

    return None, None, None


# ---------------------------------------------------------------- HELPERS
def get_house_from_lagna(planet_rasi, lagna_rasi):
    """House number 1-12 of planet_rasi counted from lagna_rasi."""
    return ((planet_rasi - lagna_rasi) % 12) + 1


def get_jupiter_aspects(planets):
    """Calculates rasi indices aspected by Jupiter (5th, 7th, 9th houses from Jupiter)."""
    if "Jupiter" not in planets:
        return []
    j_idx = planets["Jupiter"]["rasi_idx"]
    return [(j_idx + offset - 1) % 12 for offset in (5, 7, 9)]


def is_aspected_by_jupiter(planets, target_rasi_idx):
    """Checks if a target Rasi index is under Jupiter's protective aspect or conjunction."""
    if "Jupiter" not in planets:
        return False
    jup_rasi = planets["Jupiter"]["rasi_idx"]
    return (target_rasi_idx == jup_rasi) or (target_rasi_idx in get_jupiter_aspects(planets))


# ---------------------------------------------------------------- DOSHAS
def evaluate_chevvai_dosha(planets, lagna_idx=None, tradition=TRADITION):
    """
    Mars dosham counted from Lagna, Moon AND Venus (Lagna strongest).
    strength: strong = from Lagna | moderate = from Moon and Venus | mild = from one of them.
    """
    if lagna_idx is None:
        lagna_idx = planets["Lagna"]["rasi_idx"]

    mars = planets["Mars"]["rasi_idx"]
    h_lagna = get_house_from_lagna(mars, lagna_idx)
    h_moon = get_house_from_lagna(mars, planets["Moon"]["rasi_idx"])
    h_venus = get_house_from_lagna(mars, planets["Venus"]["rasi_idx"])

    if dr and hasattr(dr, "mars_dosham"):
        r = dr.mars_dosham(planets, tradition)
        refs = r.get("refs", [])
        raw = bool(refs)
        cancelled = raw and r.get("status") == "CANCELLED"
        cancellation_reason = ", ".join(r.get("cancelled_by", [])) or None
    else:
        # Standalone Chevvai Evaluation Logic
        bad_manglik_houses = [1, 2, 4, 7, 8, 12] if tradition == "north" else [2, 4, 7, 8, 12]
        raw = h_lagna in bad_manglik_houses
        refs = ["Lagna"] if raw else []
        cancelled = False
        reasons = []

        if raw:
            is_own_or_exalted = mars in [0, 7, 9]
            is_jup_aspected = is_aspected_by_jupiter(planets, mars)
            is_moon_conjunct = (planets["Moon"]["rasi_idx"] == mars)

            if is_own_or_exalted or is_jup_aspected or is_moon_conjunct:
                cancelled = True
                if is_own_or_exalted: reasons.append("Mars in Own/Exalted sign")
                if is_jup_aspected: reasons.append("Jupiter aspect/conjunction on Mars")
                if is_moon_conjunct: reasons.append("Chandra-Mangala conjunction")

        cancellation_reason = ", ".join(reasons) if reasons else None

    strength = (
        "none" if not raw else "strong" if "Lagna" in refs
        else "moderate" if len(refs) == 2 else "mild"
    )

    return {
        "has_dosha": raw and not cancelled,
        "raw_present": raw,
        "cancelled": cancelled,
        "cancellation_reason": cancellation_reason,
        "counted_from": refs,
        "strength": strength,
        "from_lagna": h_lagna,
        "from_moon": h_moon,
        "from_venus": h_venus,
    }


def compare_chevvai(g, b):
    """Graded comparison instead of a strict yes/no equality."""
    rank = {"none": 0, "mild": 1, "moderate": 2, "strong": 3}
    gs = g["strength"] if g["has_dosha"] else "none"
    bs = b["strength"] if b["has_dosha"] else "none"

    if gs == "none" and bs == "none":
        level = "none"
    elif gs != "none" and bs != "none":
        level = "balanced" if abs(rank[gs] - rank[bs]) <= 1 else "unequal"
    else:
        level = "minor_gap" if max(rank[gs], rank[bs]) == 1 else "mismatch"

    return level, level != "mismatch"


def evaluate_sarpa_dosha(planets, lagna_idx=None):
    """Rahu or Ketu in 1, 2, 5, 7, or 8 from Lagna. Jupiter's aspect/conjunction cancels."""
    if lagna_idx is None:
        lagna_idx = planets["Lagna"]["rasi_idx"]

    if dr and hasattr(dr, "sarpa_dosham"):
        r = dr.sarpa_dosham(planets)
        return {
            "has_dosha": r.get("status") == "PRESENT",
            "raw_present": r.get("status") != "NOT PRESENT",
            "cancelled": r.get("status") == "CANCELLED",
            "counted_from": r.get("refs", ["Lagna"]),
            "rahu_house": get_house_from_lagna(planets["Rahu"]["rasi_idx"], lagna_idx),
            "ketu_house": get_house_from_lagna(planets["Ketu"]["rasi_idx"], lagna_idx),
        }

    rahu_h = get_house_from_lagna(planets["Rahu"]["rasi_idx"], lagna_idx)
    ketu_h = get_house_from_lagna(planets["Ketu"]["rasi_idx"], lagna_idx)
    dosha_houses = [1, 2, 5, 7, 8]
    raw = (rahu_h in dosha_houses) or (ketu_h in dosha_houses)
    cancelled = False

    if raw:
        rahu_rasi = planets["Rahu"]["rasi_idx"]
        ketu_rasi = planets["Ketu"]["rasi_idx"]
        if is_aspected_by_jupiter(planets, rahu_rasi) or is_aspected_by_jupiter(planets, ketu_rasi):
            cancelled = True

    return {
        "has_dosha": raw and not cancelled,
        "raw_present": raw,
        "cancelled": cancelled,
        "counted_from": ["Lagna"] if raw else [],
        "rahu_house": rahu_h,
        "ketu_house": ketu_h,
    }


def evaluate_kaalsarpa_dosha(planets):
    """All 7 classical planets on one side of the Rahu-Ketu axis."""
    rahu_deg = planets["Rahu"]["deg"]
    main_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    sides = [((planets[p]["deg"] - rahu_deg) % 360) < 180 for p in main_planets]
    return all(sides) or not any(sides)


def evaluate_pitru_dosha(planets, lagna_idx=None):
    """Sun with Rahu/Ketu/Saturn (or afflicted in 5th/9th), or a node in the 5th/9th house."""
    if lagna_idx is None:
        lagna_idx = planets["Lagna"]["rasi_idx"]

    sun_h = get_house_from_lagna(planets["Sun"]["rasi_idx"], lagna_idx)
    rahu_h = get_house_from_lagna(planets["Rahu"]["rasi_idx"], lagna_idx)
    ketu_h = get_house_from_lagna(planets["Ketu"]["rasi_idx"], lagna_idx)

    has, details = False, "Clear"

    if dr and hasattr(dr, "pitru"):
        sun_based = dr.pitru(planets)
        if sun_based.get("status") == "PRESENT":
            has, details = True, "Sun afflicted by Rahu/Ketu/Saturn (Pitru Dosham)"
        elif sun_based.get("status") == "CANCELLED":
            details = "Sun affliction present but cancelled: " + ", ".join(sun_based.get("cancelled_by", []))
        elif rahu_h in (5, 9) or ketu_h in (5, 9):
            node, h = ("Rahu", rahu_h) if rahu_h in (5, 9) else ("Ketu", ketu_h)
            has, details = True, f"{node} in House {h} (Ancestral Karma Affliction)"
    else:
        if (rahu_h in [5, 9] or ketu_h in [5, 9]) and sun_h in [5, 9]:
            has, details = True, "Sun conjunct Node in 5th/9th House (Grahan / Pitru Dosham)"
        elif rahu_h in [5, 9] or ketu_h in [5, 9]:
            node, h = ("Rahu", rahu_h) if rahu_h in [5, 9] else ("Ketu", ketu_h)
            has, details = True, f"{node} in House {h} (Ancestral Karma Affliction)"

    return {"has_dosha": has, "details": details}


def _lords_friendly(a, b):
    return a == b or (b in FRIENDS.get(a, set()) and a in FRIENDS.get(b, set()))


def evaluate_shashtashtaka(girl_moon_rasi, boy_moon_rasi):
    """6/8 rasi relationship. Cancelled when the two rasi lords are the same planet or mutual friends."""
    count = ((boy_moon_rasi - girl_moon_rasi) % 12) + 1
    is_6_8 = count in (6, 8)
    cancelled = False

    if is_6_8:
        girl_lord = RASI_DATA[girl_moon_rasi]["lord_en"]
        boy_lord = RASI_DATA[boy_moon_rasi]["lord_en"]
        cancelled = _lords_friendly(girl_lord, boy_lord)

    return {
        "is_6_8": is_6_8,
        "count": count,
        "cancelled": cancelled,
        "harmful": is_6_8 and not cancelled
    }


# ---------------------------------------------------------------- STAR INDEX
def star_index_from_chart(chart):
    """Moon's nakshatra index straight from its longitude - no name matching, no silent defaults."""
    try:
        return int(chart["planets"]["Moon"]["deg"] // (360 / 27)) % 27
    except (KeyError, TypeError):
        name = chart.get("panchangam", {}).get("nakshatra") or ""
        return get_star_index_by_name(name)


# ---------------------------------------------------------------- MAIN MATCHING
def calculate_full_chart_matching(girl_chart, boy_chart, lang="English"):
    is_ta = (lang == "Tamil")

    girl_star_idx = star_index_from_chart(girl_chart)
    boy_star_idx = star_index_from_chart(boy_chart)
    girl_rasi_idx = girl_chart["planets"]["Moon"]["rasi_idx"]
    boy_rasi_idx = boy_chart["planets"]["Moon"]["rasi_idx"]

    porutham_res = calculate_porutham(girl_star_idx, boy_star_idx, girl_rasi_idx, boy_rasi_idx, lang=lang)
    score_str = f"{porutham_res['total_score']:g}/10"

    gp, bp = girl_chart["planets"], boy_chart["planets"]
    g_chevvai, b_chevvai = evaluate_chevvai_dosha(gp), evaluate_chevvai_dosha(bp)
    chevvai_level, chevvai_match = compare_chevvai(g_chevvai, b_chevvai)

    g_sarpa, b_sarpa = evaluate_sarpa_dosha(gp), evaluate_sarpa_dosha(bp)
    sarpa_match = (g_sarpa["has_dosha"] == b_sarpa["has_dosha"])

    g_kaal, b_kaal = evaluate_kaalsarpa_dosha(gp), evaluate_kaalsarpa_dosha(bp)
    g_pitru, b_pitru = evaluate_pitru_dosha(gp), evaluate_pitru_dosha(bp)
    shashtashtaka = evaluate_shashtashtaka(girl_rasi_idx, boy_rasi_idx)

    boy_current_dasa = get_current_active_dasa(boy_chart)
    girl_current_dasa = get_current_active_dasa(girl_chart)
    _, boy_bhukti, _ = get_current_bhukti(boy_chart)
    _, girl_bhukti, _ = get_current_bhukti(girl_chart)

    mandatory_failed, rajju_or_vedha_failed = [], False
    for p in porutham_res["poruthams"]:
        if p.get("mandatory") and p.get("score", 0) == 0:
            mandatory_failed.append(p["group"])
            if "rajju" in p["group"].lower() or "vedha" in p["group"].lower():
                rajju_or_vedha_failed = True

    all_mandatory_passed = not mandatory_failed
    total = porutham_res["total_score"]

    notes = []
    if chevvai_level == "minor_gap":
        notes.append("Mars dosham is mild (counted from Moon or Venus only) on one side.")
    elif chevvai_level == "unequal":
        notes.append("Both have Mars dosham but of different strength. Consult an astrologer.")
    elif chevvai_level == "mismatch":
        notes.append("Only one chart has a significant Mars dosham that is not cancelled.")
    if shashtashtaka["is_6_8"] and shashtashtaka["cancelled"]:
        notes.append("6/8 rasi relationship, cancelled because the rasi lords are mutual friends.")
    if mandatory_failed:
        notes.append("Missing key poruthams: " + ", ".join(mandatory_failed))

    if rajju_or_vedha_failed or shashtashtaka["harmful"] or not (chevvai_match and sarpa_match):
        overall_status = "பொருத்தம் இல்லை\nதவிர்க்கவும் (Not Recommended)" if is_ta else "Not Recommended"
        status_color = "#b71c1c"
        overall_text = (
            "தோஷ சமநிலையின்மை (செவ்வாய்/சர்ப்ப தோஷம்), ரஜ்ஜு/வேதை தோஷம், அல்லது 6/8 அஷ்டம ராசி "
            "காரணத்தினால் இந்த ஜாதக இணைப்பு பரிந்துரைக்கப்படவில்லை."
            if is_ta else
            "This match is not recommended due to an uncancelled Rajju/Vedha dosha, Chevvai/Sarpa imbalance, "
            "or an inauspicious 6/8 (Shashtashtaka) rasi relationship."
        )
    elif all_mandatory_passed and total >= 6.0:
        overall_status = "திருமணம் செய்யலாம்\nமிகச் சிறந்த பொருத்தம் (Highly Recommended)" if is_ta else "Highly Recommended"
        status_color = "#1b5e20"
        overall_text = (
            "5 முக்கிய கட்டாயப் பொருத்தங்கள் (ரஜ்ஜு, வேதை, யோனி, மகேந்திரம், ஸ்திரீ தீர்க்கம்) உட்பட "
            "அனைத்து பொருத்தங்களும் சிறப்பாக அமைந்துள்ளன."
            if is_ta else
            "All key poruthams (Rajju, Vedha, Yoni, Mahendra, Sthree Deerga) match and doshas are balanced."
        )
    else:
        overall_status = "மிதமான பொருத்தம்\nபரிகாரங்களுடன் செய்யலாம் (Moderately Recommended)" if is_ta else "Moderately Recommended"
        status_color = "#f39c12"
        overall_text = (
            "ரஜ்ஜு மற்றும் வேதை தோஷங்கள் இல்லை. ஆனால் சில முக்கிய பொருத்தங்கள் இல்லாததால் ஜோதிடரின் ஆலோசனையுடன் முடிவு செய்யவும்."
            if is_ta else
            "Rajju and Vedha are clear and doshas are balanced, but some key poruthams are missing. Proceed with remedies."
        )

    dasa_dict = {
        "girl": {"current_dasa": girl_current_dasa, "in_sandhi": False},
        "boy": {"current_dasa": boy_current_dasa, "in_sandhi": False},
        "boy_dasa": boy_current_dasa,
        "girl_dasa": girl_current_dasa,
        "boy_bhukti": boy_bhukti,
        "girl_bhukti": girl_bhukti,
        "both_in_sandhi": False,
        "is_favorable": True
    }

    return {
        "porutham_score": score_str,
        "porutham_details": porutham_res["poruthams"],
        "chevvai": {"girl": g_chevvai, "boy": b_chevvai, "is_match": chevvai_match, "level": chevvai_level},
        "sarpa": {"girl": g_sarpa, "boy": b_sarpa, "is_match": sarpa_match},
        "kaalsarpa": {"girl": g_kaal, "boy": b_kaal, "is_match": g_kaal == b_kaal},
        "pitru": {"girl": g_pitru, "boy": b_pitru},
        "shashtashtaka": shashtashtaka,
        "dasa": dasa_dict,
        "dasa_sandhi": dasa_dict,
        "notes": notes,
        "overall_status": overall_status,
        "status_color": status_color,
        "overall_summary": overall_text,
    }


# ---------------------------------------------------------------- FORM -> CHARTS
REQUIRED = (
    "name", "dob_day", "dob_month", "dob_year", "tob_hour", "tob_minute",
    "tob_ampm", "place", "latitude", "longitude"
)


def _person_payload(form_data, prefix, label):
    """Reads one person's fields. Missing or invalid input raises a clear error."""
    missing = [f"{prefix}_{k}" for k in REQUIRED if str(form_data.get(f"{prefix}_{k}", "")).strip() == ""]
    if missing:
        raise ValueError(f"{label}: missing {', '.join(missing)}. Check form field names.")

    try:
        day, month, year = (int(form_data[f"{prefix}_dob_{k}"]) for k in ("day", "month", "year"))
        datetime(year, month, day)  # Validates calendar day bounds
        hour, minute = int(form_data[f"{prefix}_tob_hour"]), int(form_data[f"{prefix}_tob_minute"])
        ampm = str(form_data[f"{prefix}_tob_ampm"]).upper()
        lat, lon = float(form_data[f"{prefix}_latitude"]), float(form_data[f"{prefix}_longitude"])
    except ValueError:
        raise ValueError(f"{label}: please check the date, time, and location values.")

    if not (1 <= hour <= 12 and 0 <= minute <= 59 and ampm in ("AM", "PM")):
        raise ValueError(f"{label}: time of birth is invalid (hour 1-12, minute 0-59, AM/PM).")

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"{label}: latitude or longitude is out of range.")

    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    person_name_clean = str(form_data[f"{prefix}_name"]).strip() or label

    return {
        "name": person_name_clean,              # Matches payload.get("name") in astro_engine.py
        "person_name": person_name_clean,       # Preserved for template consistency
        "dob": f"{year:04d}-{month:02d}-{day:02d}",
        "tob": f"{hour:02d}:{minute:02d}",
        "place": str(form_data[f"{prefix}_place"]).strip(),
        "latitude": lat,
        "longitude": lon,
    }


def generate_chart_matching_report(form_data):
    """Called by app.py. Returns (boy_chart, girl_chart, report, error)."""
    try:
        import astro_engine
        lang = form_data.get("chart_language", "English")

        boy_payload = _person_payload(form_data, "boy", "Groom")
        girl_payload = _person_payload(form_data, "girl", "Bride")

        logger.info(
            "Matching: boy %s %s (%s) | girl %s %s (%s)",
            boy_payload["dob"], boy_payload["tob"], boy_payload["person_name"],
            girl_payload["dob"], girl_payload["tob"], girl_payload["person_name"]
        )

        boy_chart = astro_engine.calculate_birth_chart(boy_payload)
        girl_chart = astro_engine.calculate_birth_chart(girl_payload)

        report = calculate_full_chart_matching(girl_chart, boy_chart, lang=lang)

        # Explicitly forward names to the report object
        report["boy_name"] = boy_payload["person_name"]
        report["girl_name"] = girl_payload["person_name"]

        return boy_chart, girl_chart, report, None

    except ValueError as e:
        return None, None, None, str(e)
    except Exception:
        logger.exception("Chart matching failed")
        return None, None, None, "Could not calculate the charts. Please check the details and try again."