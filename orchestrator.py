# -*- coding: utf-8 -*-
"""
orchestrator.py - Deterministic Chained Pipeline with Evaluator/Validator Loop.
Coordinates Research (rule_service), Interpretation (palan_service), and
Critic Validation (validation_service + human_voice) with payload caching & bounded retries.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime

import dosha_rules as dr
import human_voice
import rule_service
import validation_service

logger = logging.getLogger(__name__)

MAX_RETRIES = 1  # Bounded retry to prevent latency accumulation
MAX_RULES = 6
CACHE_TTL_SECONDS = 12 * 3600  # Cleaned up line-break syntax error
CACHE_MAX_ITEMS = 256
PIPELINE_VERSION = "2"
STRICT = False  # Set to False so LLM drafts are returned even if validation retries expire

LOOKS_LIKE_ERROR = (
    "high demand", "high traffic", "could not generate",
    "could not answer", "api key is not configured", "prediction generation failed"
)


class _TTLCache:
    """Thread-safe TTL execution cache to save API quotas."""

    def __init__(self, maxsize, ttl):
        self._d, self._lock, self.maxsize, self.ttl = OrderedDict(), threading.Lock(), maxsize, ttl

    def get(self, key):
        with self._lock:
            item = self._d.get(key)
            if not item:
                return None
            if time.time() - item[0] > self.ttl:
                del self._d[key]
                return None
            self._d.move_to_end(key)
            return item[1]

    def set(self, key, value):
        with self._lock:
            self._d[key] = (time.time(), value)
            self._d.move_to_end(key)
            while len(self._d) > self.maxsize:
                self._d.popitem(last=False)


_CACHE = _TTLCache(CACHE_MAX_ITEMS, CACHE_TTL_SECONDS)


def _cache_key(chart, topic, language, today):
    raw = json.dumps(chart or {}, sort_keys=True, default=str)
    return hashlib.sha256(f"{PIPELINE_VERSION}|{raw}|{topic}|{language}|{today:%Y-%m-%d}".encode()).hexdigest()


def _enrich(chart):
    """Calculates ground-truth doshas using dosha_rules."""
    if isinstance(chart, str):
        try:
            chart = json.loads(chart)
        except Exception:
            chart = {}

    chart = chart or {}
    planets = chart.get("planets") or chart.get("planetary_positions_and_dignity") or {}
    out = dict(chart)

    if isinstance(planets, dict) and planets.get("Lagna") and planets.get("Moon"):
        out["doshas"] = [
            {
                "name": r.get("name", "") if isinstance(r, dict) else str(r),
                "status": r.get("status", "") if isinstance(r, dict) else "",
                "details": r.get("details", "") if isinstance(r, dict) else "",
                "cancelled_by": r.get("cancelled_by", []) if isinstance(r, dict) else []
            }
            for r in dr.analyze_doshas(planets)
        ]
    return out


def build_ground_truth(chart, today):
    """Constructs complete, un-hallucinated astrological ground truth payload."""
    if isinstance(chart, str):
        try:
            chart = json.loads(chart)
        except Exception:
            chart = {}

    chart = chart or {}
    planets = (
        chart.get("planets")
        or chart.get("planetary_positions_and_dignity")
        or chart.get("planetary_positions")
        or {}
    )

    if not isinstance(planets, dict):
        planets = {}

    lagna_info = planets.get("Lagna", {}) if isinstance(planets.get("Lagna"), dict) else {}
    lagna_idx = lagna_info.get("rasi_idx", 0)

    sign = lambda i: dr.RASIS[i % 12] if hasattr(dr, "RASIS") else f"Sign {i}"
    house = lambda i: ((i - lagna_idx) % 12) + 1
    L = []

    meta = chart.get("_meta", {}) if isinstance(chart.get("_meta"), dict) else {}
    name = meta.get("person_name", "")
    L.append(f"Today's date: {today:%d-%m-%Y}" + (f" | Person: {name}" if name else ""))

    if lagna_info:
        lagna_deg = lagna_info.get("deg", 0.0)
        lagna_lord = dr.RASI_LORD[lagna_idx] if hasattr(dr, "RASI_LORD") else "Unknown"
        L.append(f"Lagna: {sign(lagna_idx)} ({lagna_deg % 30:.0f} deg). Lagna lord: {lagna_lord}.")

    panchangam = chart.get("panchangam", {}) if isinstance(chart.get("panchangam"), dict) else {}
    nak = panchangam.get("nakshatra")
    moon_info = planets.get("Moon", {}) if isinstance(planets.get("Moon"), dict) else {}
    if moon_info:
        L.append(f"Moon sign: {sign(moon_info.get('rasi_idx', 0))}" + (f", nakshatra {nak}" if nak else "") + ".")

    # Planetary positions, house numbers, and functional dignity
    L.append("Planets (sign, house counted from Lagna, dignity, functional lord):")
    for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu", "Gulika"):
        d = planets.get(p)
        if isinstance(d, dict):
            p_rasi = d.get("rasi_idx", 0)
            p_deg = d.get("deg", 0.0)
            dignity = d.get("dignity", "Neutral")
            f_tag = d.get("functional_tag", "N/A")
            nav = d.get("navamsa", "")
            das = d.get("dasamsa", "")
            d20 = d.get("vimshamsa_d20", "")
            retro = ", retrograde" if d.get("retro") else ""
            vargas = f" [D9: {nav}, D10: {das}, D20: {d20}]" if nav else ""
            L.append(f"  {p}: {sign(p_rasi)}, house {house(p_rasi)}, {p_deg % 30:.0f} deg ({dignity}, {f_tag}){retro}{vargas}")

    comb = dr.combust_planets(planets) if hasattr(dr, "combust_planets") else []
    L.append("Combust planets: " + (", ".join(comb) if comb else "none"))

    # Active Special Yogas
    special_yogas = chart.get("special_yogas_and_conjunctions") or chart.get("conjunctions_2_planet") or []
    if isinstance(special_yogas, list) and special_yogas:
        L.append("Special Yogas Present:")
        for y in special_yogas:
            if isinstance(y, dict):
                title = y.get("title", "")
                eff = y.get("effect", "")
                L.append(f"  - {title}: {eff}")

    # Dosha status
    L.append("Dosha status (exact ground truth):")
    doshas_list = chart.get("doshas", [])
    if isinstance(doshas_list, list):
        for d in doshas_list:
            if isinstance(d, dict):
                extra = f" - cancelled by: {', '.join(d.get('cancelled_by', []))}" if d.get("cancelled_by") else ""
                L.append(f"  {d.get('name', 'Unknown')}: {d.get('status', 'Unknown')}{extra}")
            elif isinstance(d, str):
                L.append(f"  {d}: PRESENT")

    # Current Dasa & Bhukti
    dasa, bhukti, end = (
        human_voice.current_period(chart, today)
        if hasattr(human_voice, "current_period")
        else ("N/A", "N/A", "N/A")
    )
    if dasa and dasa != "N/A":
        L.append(f"RUNNING NOW: {dasa} dasa, {bhukti} bhukti (ends {end}).")

    # Real-time Planetary Transits (Gocharam)
    saturn_tr = chart.get("saturn_transit_analysis", {}).get("analysis", "")
    jupiter_tr = chart.get("jupiter_transit_analysis", {}).get("analysis", "")
    rahu_tr = chart.get("rahu_ketu_transit_analysis", {}).get("analysis", "")
    if saturn_tr or jupiter_tr or rahu_tr:
        L.append("Active Transits (Gocharam):")
        if saturn_tr:
            L.append(f"  Saturn Transit: {saturn_tr}")
        if jupiter_tr:
            L.append(f"  Jupiter Transit: {jupiter_tr}")
        if rahu_tr:
            L.append(f"  Rahu-Ketu Transit: {rahu_tr}")

    return "\n".join(L)


def deterministic_fallback(chart, topic, today):
    """Safe fallback output when retries are exhausted without pass."""
    if isinstance(chart, str):
        try:
            chart = json.loads(chart)
        except Exception:
            chart = {}

    chart = chart or {}
    planets = chart.get("planets") or chart.get("planetary_positions") or {}
    lagna_info = planets.get("Lagna", {}) if isinstance(planets, dict) and isinstance(planets.get("Lagna"), dict) else {}
    lagna_idx = lagna_info.get("rasi_idx", 0)

    sign_name = dr.RASIS[lagna_idx % 12] if hasattr(dr, "RASIS") else "Ascendant"
    dasa, bhukti, end = (
        human_voice.current_period(chart, today)
        if hasattr(human_voice, "current_period")
        else ("N/A", "N/A", "N/A")
    )

    return (
        f"**{(topic or 'OVERALL').upper()} PREDICTION SUMMARY:**\n\n"
        f"Chart Facts: Lagna in {sign_name}, running {dasa} Dasa and {bhukti} Bhukti.\n"
        f"Due to transient validation limits, a detailed paragraph reading could not be generated. "
        f"Please try again in a few moments."
    )


def execute_prediction_pipeline(
    chart_data, topic, generate_llm_fn, language="English", today=None, return_meta=False, greet=False
):
    today = today or datetime.now()

    # Safely deserialize chart_data if received as JSON string
    if isinstance(chart_data, str):
        try:
            chart_data = json.loads(chart_data)
        except Exception:
            chart_data = {}

    chart_data = chart_data or {}
    chart = _enrich(chart_data)
    kind = "report" if (topic or "").lower() in getattr(human_voice, "TOPIC_FOCUS", {}) else "chat"

    def done(text, valid, issues, cached=False, error=False):
        meta = {"valid": valid, "issues": issues, "cached": cached, "error": error}
        return (text, meta) if return_meta else text

    # Pre-check chart usability
    usable = human_voice.chart_is_usable(chart) if hasattr(human_voice, "chart_is_usable") else bool(chart)
    if not usable:
        return done("The birth chart data is incomplete or missing.", False, ["Incomplete chart"], error=True)

    # Check cache
    key = _cache_key(chart, topic, language, today)
    hit = _CACHE.get(key)
    if hit:
        return done(hit, True, [], cached=True)

    facts = build_ground_truth(chart, today)

    # Retrieve classical rules safely
    try:
        rules = rule_service.retrieve_rules_for_chart(chart, topic=topic, max_rules=MAX_RULES)
        rules_context_lines = []
        for r in rules:
            if isinstance(r, dict):
                source = r.get("source_text", "Classical Text")
                verse = r.get("chapter_verse", "")
                palan = r.get("palan_en", "")
                rules_context_lines.append(f"- [{source} {verse}]: {palan}")

        rules_context = "\n".join(rules_context_lines) if rules_context_lines else "Follow classical Parashari principles."
    except Exception as e:
        logger.warning(f"Rule retrieval fallback: {e}")
        rules_context = "Follow classical Parashari principles."

    # Extract first name safely from metadata if available
    first_name = ""
    if hasattr(human_voice, "person_name"):
        first_name = human_voice.person_name(chart)
    else:
        meta_data = chart.get("_meta", {}) if isinstance(chart.get("_meta"), dict) else {}
        p_name = meta_data.get("person_name", "")
        if p_name and p_name.strip().lower() not in ("native", ""):
            first_name = p_name.strip().split(" ")[0]

    voice = human_voice.style_block(topic=topic, language=language, greet=greet, first_name=first_name)
    base_prompt = f"""{voice}

[GROUND TRUTH - COMPUTED FACTUAL DATA]:
{facts}

[RETRIEVED CLASSICAL RULES]:
{rules_context}

TASK: Write a natural, detailed, and decisive reading for "{topic}". Start directly with the core prediction.
Synthesize the native's active Dasa/Bhukti, Gocharam transits, Dharma/Artha/Kama Trikonas, and divisional chart placements (D1, D9, D10). Do not contradict yourself or use speculative hedges. Complete all lists fully.
"""

    attempts = 0
    feedback = ""
    best = None

    while attempts <= MAX_RETRIES:
        attempts += 1
        prompt = base_prompt + feedback

        try:
            text = (generate_llm_fn(prompt) or "").strip()
        except Exception as e:
            logger.error(f"LLM execution error on attempt {attempts}: {e}")
            return done("Vidhu AI prediction service currently unavailable.", False, [str(e)], error=True)

        if not text or any(err in text[:200].lower() for err in LOOKS_LIKE_ERROR):
            return done("Vidhu AI service unavailable. Please try again.", False, ["LLM error output"], error=True)

        # Critic Pass
        if hasattr(validation_service, "validate_detailed"):
            val_res = validation_service.validate_detailed(text, chart, today=today, kind=kind)
            is_valid, errors = val_res["valid"], val_res["errors"]
        else:
            is_valid, errors = validation_service.validate_prediction_output(text, chart)

        if is_valid:
            final = human_voice.tidy(text)
            _CACHE.set(key, final)
            return done(final, True, [])

        if best is None or len(errors) < best[0]:
            best = (len(errors), text, errors)

        # Supply prior draft and specific issues to fix if retry is needed
        feedback = (
            f"\n\n[YOUR PREVIOUS DRAFT]:\n{text}\n\n"
            f"[CRITIC REVISION REQUIRED - ATTEMPT {attempts} FAILED]:\n"
            "Fix ONLY these specific discrepancies in your updated response:\n" +
            "\n".join([f"- {iss}" for iss in errors])
        )

    # Max retries reached — return the best draft cleanly
    _, text, errs = best
    if STRICT:
        return done(deterministic_fallback(chart, topic, today), False, errs)

    final = human_voice.tidy(text)
    _CACHE.set(key, final)
    return done(final, False, errs)


# Keep backward compatible function signature
execute_level4_prediction_pipeline = execute_prediction_pipeline