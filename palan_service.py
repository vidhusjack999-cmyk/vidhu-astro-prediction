# -*- coding: utf-8 -*-
"""
palan_service.py
Grounded Astrological Interpretation & Prediction Engine for Vidhu Astro.
Includes multi-layer cross-synthesis connecting running Dasa-Bhuktis
with dynamic classical transits (Ezharai, Ashtama, Kandaka Sani & Guru Drishti).
100% DYNAMIC: Supports all 12 Rasis without static sign fallbacks.
"""

import json
import logging
import os
import random
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from google import genai
from google.genai import types
from google.genai.errors import APIError

from gemini_models import get_models, invalidate_cache
from human_voice import style_block, find_bad_dates, allowed_dates, tidy
import dosha_rules

try:
    import validation_service
except ImportError:
    validation_service = None

try:
    import analyzer_service
except ImportError:
    analyzer_service = None

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
DB_PATH = os.path.join(os.path.dirname(__file__), "api_tracker.db")

RETRYABLE_CODES = {429, 500, 502, 503, 504}
MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "4096"))
FAST_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

FRIENDLY_BUSY = {
    "prediction": "Vidhu AI is currently experiencing high demand. Please try again in a minute.",
    "chat": "Vidhu Chat is experiencing high traffic. Please wait a few seconds and ask your question again.",
}
FRIENDLY_FAIL = {
    "prediction": "Vidhu AI could not generate your prediction right now. Please try again shortly.",
    "chat": "Vidhu Chat could not answer right now. Please try again shortly.",
}


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=45000)
    )


def log_attempt_to_db(endpoint: str, model_used: str, status_code: int, is_retry: bool = False):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO api_logs (timestamp, endpoint, model_used, status_code, is_retry) VALUES (?, ?, ?, ?, ?)",
            (time.time(), endpoint, model_used, status_code, 1 if is_retry else 0)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Tracker DB logging error in palan_service: %s", e)


def execute_gemini_with_fallback(client, prompt: str, endpoint_name: str) -> tuple[str, str]:
    if not client:
        client = get_client()

    if not client:
        raise RuntimeError("GEMINI_API_KEY is not configured in environment variables.")

    last_error = None

    try:
        listed_models = get_models(client)
        models = [m for m in listed_models if "flash" in m]
        if not models:
            models = FAST_MODELS
    except Exception as e:
        logger.warning("Could not list Gemini models: %s", e)
        models = FAST_MODELS

    for model_name in models:
        for attempt in range(2):
            is_retry = (attempt > 0)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=MAX_OUTPUT_TOKENS,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                    )
                )
                text = (response.text or "").strip()
                if text:
                    log_attempt_to_db(endpoint_name, model_name, 200, is_retry=is_retry)
                    return text, model_name

                log_attempt_to_db(endpoint_name, model_name, 500, is_retry=is_retry)
                last_error = RuntimeError("Gemini returned an empty response.")
                break

            except APIError as e:
                last_error = e
                code = getattr(e, "code", 500)
                log_attempt_to_db(endpoint_name, model_name, code, is_retry=is_retry)

                if code in (400, 401, 403):
                    raise e
                if code == 404:
                    invalidate_cache()
                    break
                if code in RETRYABLE_CODES and attempt == 0:
                    time.sleep(1.0 + random.random())
                    continue
                break
            except Exception as e:
                last_error = e
                log_attempt_to_db(endpoint_name, model_name, 500, is_retry=is_retry)
                break

    raise last_error or RuntimeError("Gemini request failed on all available models.")


def _friendly_error(e: Exception, kind: str) -> str:
    logger.error("Gemini %s request failed: %s", kind, e)
    msg = str(e)
    if "429" in msg or "ResourceExhausted" in msg or getattr(e, "code", None) == 429:
        return f'<div class="reading"><p>{FRIENDLY_BUSY[kind]}</p></div>'
    return f'<div class="reading"><p>{FRIENDLY_FAIL[kind]}</p></div>'


def generate_prediction_llm(prompt_text: str) -> str:
    client = get_client()
    if not client:
        return (
            "**Vidhu AI Local Mode:**\n\n"
            "Set the `GEMINI_API_KEY` environment variable to enable live Gemini AI predictions."
        )

    raw_text, _ = execute_gemini_with_fallback(client, prompt_text, endpoint_name="/api/orchestrated_prediction")
    return raw_text


def _clean_topic_title(topic_str: str) -> str:
    cleaned = re.sub(r"(?i)\s+analysis$", "", topic_str.strip())
    cleaned = re.sub(r"(?i)\s+report$", "", cleaned.strip())
    return cleaned.strip().upper()


def _extract_verified_anchors(chart_data: dict, pdf_text: str) -> dict:
    """
    Guarantees reliable, un-corrupted extraction of Native Name, Lagna, Rasi,
    Active Dasa, and Active Bhukti from either chart_data or extracted PDF text.
    Prevents mistaking Kataka or other sign labels for the native's true Moon sign.
    """
    anchors = {
        "name": "",
        "lagna": "",
        "rasi": "",
        "nakshatra": "",
        "dasa": "",
        "bhukti": "",
        "current_period": ""
    }

    # 1. Inspect chart_data if present
    if chart_data:
        meta = chart_data.get("_meta") or chart_data.get("birth_details_and_panchangam", {}).get("_meta", {})
        anchors["name"] = meta.get("person_name") or chart_data.get("name", "")
        anchors["current_period"] = meta.get("current_period") or chart_data.get("current_period", "")
        anchors["dasa"] = meta.get("active_dasa_lord") or chart_data.get("active_dasa", "")
        anchors["bhukti"] = meta.get("active_bhukti_lord") or chart_data.get("active_bhukti", "")

        planets = chart_data.get("planets") or chart_data.get("planetary_positions_and_dignity", {})
        if "Lagna" in planets:
            anchors["lagna"] = planets["Lagna"].get("rasi_display") or planets["Lagna"].get("rasi", "")
        if "Moon" in planets:
            anchors["rasi"] = planets["Moon"].get("rasi_display") or planets["Moon"].get("rasi", "")
            anchors["nakshatra"] = planets["Moon"].get("nakshatra_display") or planets["Moon"].get("nakshatra", "")

    # 2. Extract from raw PDF text if fields remain missing
    if pdf_text:
        if not anchors["name"]:
            m = re.search(r"Name\s*[:\|]\s*([^\n\r\|]+)", pdf_text, re.IGNORECASE)
            if m: anchors["name"] = m.group(1).split("Date of Birth")[0].strip()

        if not anchors["rasi"]:
            # Priority: Look for Section 1 Panchangam line
            m_panch = re.search(
                r"Moon\s+Sign\s*\(Rasi\)\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\||\n|\r|Nakshatra|Gana)",
                pdf_text, re.IGNORECASE)
            if m_panch:
                anchors["rasi"] = m_panch.group(1).strip()
            else:
                m_table = re.search(r"\bMoon\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\|)", pdf_text, re.IGNORECASE)
                if m_table: anchors["rasi"] = m_table.group(1).strip()

        if not anchors["lagna"]:
            m_lag = re.search(r"(?:Ascendant|Lagna)\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\||\n|\r)", pdf_text,
                              re.IGNORECASE)
            if m_lag: anchors["lagna"] = m_lag.group(1).strip()

        if not anchors["current_period"]:
            m_p = re.search(r"CURRENT\s+RUNNING\s+PERIOD\s*[:\|]\s*([^\n\r]+)", pdf_text, re.IGNORECASE)
            if m_p:
                anchors["current_period"] = m_p.group(1).replace("⏳", "").strip()

    # Decompose period string if dasa/bhukti lords were not populated directly
    if anchors["current_period"] and (not anchors["dasa"] or not anchors["bhukti"]):
        parts = re.search(r"([A-Za-z]+)\s+Dasa\s*[–\-]\s*([A-Za-z]+)\s+Bhukti", anchors["current_period"],
                          re.IGNORECASE)
        if parts:
            anchors["dasa"] = parts.group(1).strip()
            anchors["bhukti"] = parts.group(2).strip()

    return anchors


def _build_or_extract_fact_pack(chart_data: dict, topic: str, user_query: str = "") -> dict:
    if analyzer_service and hasattr(analyzer_service, "build_fact_pack"):
        try:
            return analyzer_service.build_fact_pack(chart_data, topic=topic, query=user_query)
        except Exception as e:
            logger.warning("analyzer_service.build_fact_pack failed: %s. Using dynamic engine.", e)

    planets = chart_data.get("planets") or chart_data.get("planetary_positions_and_dignity") or {}
    timeline = chart_data.get("dasa_timeline") or chart_data.get("maha_dasa_and_dasa_bhukti_timeline", {}).get(
        "timeline", [])

    windows = []
    for d in timeline:
        d_lord = d.get("dasa_lord", "")
        for sub in d.get("antardasas", []):
            s_lord = sub.get("sub_lord", "")
            s_start = sub.get("start_date", "")
            s_end = sub.get("end_date", "")
            if s_start and s_end:
                windows.append({
                    "period": f"{d_lord} Dasa - {s_lord} Bhukti",
                    "window": f"{s_start} to {s_end}",
                    "start": s_start,
                    "end": s_end
                })

    supporting = []
    opposing = []

    for p_name, p_info in planets.items():
        if p_name in ["Lagna", "Gulika"]:
            continue
        dignity = p_info.get("dignity", "")
        rasi = p_info.get("rasi", "")
        tag = p_info.get("functional_tag", "")
        is_comb = p_info.get("is_combust", False)

        if "Exalted" in dignity or "Own Sign" in dignity or "Friendly" in dignity:
            supporting.append(f"{p_name} in {rasi} ({dignity}) acts with supportive strength ({tag})")
        if is_comb:
            opposing.append(f"{p_name} is combust by the Sun in {rasi}, causing stress under its periods")
        elif "Debilitated" in dignity or "Inimical" in dignity:
            opposing.append(f"{p_name} in {rasi} ({dignity}) introduces friction or delay ({tag})")

    if not supporting:
        supporting = ["Chart placements require balanced effort and steady execution"]
    if not opposing:
        opposing = ["Transits require disciplined navigation and realistic expectations"]

    saturn_transit = chart_data.get("saturn_transit_analysis", {})
    jupiter_transit = chart_data.get("jupiter_transit_analysis", {})

    transit_alerts = []
    if saturn_transit.get("analysis"):
        transit_alerts.append(f"Saturn Transit: {saturn_transit['analysis']}")
    if jupiter_transit.get("analysis"):
        transit_alerts.append(f"Jupiter Transit: {jupiter_transit['analysis']}")

    return {
        "verdict_code": "ANALYSIS_GROUNDED",
        "verdict": "ANALYSIS_GROUNDED",
        "approved_phrases": [
            "the planetary configurations indicate",
            "the chart dynamics reveal",
            "according to the planetary positions",
            "the active astrological periods show"
        ],
        "supporting_factors": supporting[:5],
        "opposing_factors": opposing[:4],
        "favorable_windows": windows[:6],
        "transit_alerts": transit_alerts
    }


def generate_topic_reading(
        chart_data: dict = None,
        topic: str = "work",
        language: str = "English",
        is_chat_reply: bool = False,
        user_feedback: str = "",
        pdf_text: str = ""
) -> str:
    client = get_client()

    if not client:
        return (
            '<div class="reading">\n'
            f'<p><strong>[{language} Local Mode]</strong> API Key is not configured.</p>\n'
            f'<p>Please configure the <code>GEMINI_API_KEY</code> environment variable to enable live readings.</p>\n'
            '</div>'
        )

    try:
        chart_data = chart_data or {}
        dosha_results = dosha_rules.analyze_doshas(chart_data) if (
                    chart_data and hasattr(dosha_rules, 'analyze_doshas')) else []

        fact_pack = _build_or_extract_fact_pack(chart_data, topic, user_query=user_feedback)
        chart_data["fact_pack"] = fact_pack

        anchors = _extract_verified_anchors(chart_data, pdf_text)

        voice_instructions = style_block(topic=topic, language=language) if 'style_block' in globals() else ""
        lang_instruction = "Provide the entire response in CLEAR TAMIL." if language == "Tamil" else "Provide the response in ENGLISH."

        raw_topic_title = _clean_topic_title(topic)
        is_chat_mode = bool(is_chat_reply or user_feedback)

        windows_str = "\n".join(
            [f"- {w.get('period', '')}: {w.get('window', '')}" for w in fact_pack.get("favorable_windows", [])])
        transit_str = "\n".join([f"- {t}" for t in fact_pack.get("transit_alerts", [])])

        verified_anchor_block = f"""
======================================================================
VERIFIED NATIVE ASTROLOGICAL ANCHORS (ABSOLUTE GROUND TRUTH):
- Native Name: {anchors['name'] or 'Native'}
- Janma Lagna (Ascendant): {anchors['lagna'] or 'Recorded in Chart'}
- Janma Rasi (Moon Sign): {anchors['rasi'] or 'Recorded in Chart'}
- Janma Nakshatra: {anchors['nakshatra'] or 'Recorded in Chart'}
- Running Dasa: {anchors['dasa'] or 'Active Dasa'}
- Running Bhukti: {anchors['bhukti'] or 'Active Bhukti'}
- Current Period Window: {anchors['current_period'] or 'As active in timeline'}
======================================================================
* STRICT MANDATE: You MUST calculate all house transits (Gocharam) directly 
  from Janma Rasi ({anchors['rasi']}). 
* For example, if Janma Rasi is Simha (Leo) and Saturn is in Meena (Pisces), 
  Saturn is in the 8th house (Ashtama Sani), NEVER the 11th house.
======================================================================
"""

        astrological_guidelines = f"""
[CRITICAL ASTROLOGICAL RULES - NATAL PROMISE & MULTI-LAYER SYNTHESIS]:
1. THE "NATAL FIRST" MANDATE (D1 CHART FOUNDATION):
   - BEFORE discussing any current periods or transits, you MUST explicitly state the static planetary positions in the native's birth chart relevant to the topic.
   - For Marriage: Always analyze the planets in the 7th house (e.g., Rahu in 7th), planets in the 1st house (e.g., Ketu in 1st), the dignity of the 7th Lord, and Venus.
   - For Career: Always analyze the 10th house, the 10th Lord's placement (e.g., 10th Lord in 11th), and the 6th house.
   - You must explain what these natal placements fundamentally mean for the native's life before moving to transits.

2. DASA-BHUKTI & TRANSIT (GOCHARAM) MULTI-LAYER CROSS-EXAMINATION:
   - Identify the active Dasa Lord and active Bhukti Lord.
   - Synthesize the current transit of SATURN (Sani) relative to the Natal Moon ({anchors['rasi']}):
     * Check if the native is under Ezharai Sani, Ashtama Sani, or Kandaka Sani (4th, 7th, 10th from Moon).
     * Connect this to the active Dasa/Bhukti to explain current roadblocks or delays.
   - Synthesize the current transit of JUPITER (Guru) relative to the Natal Moon ({anchors['rasi']}):
     * Check if Jupiter is in a fruitful house or a restrictive house.
     * ALWAYS CITE GURU DRISHTI: Name the three specific houses receiving Jupiter's 5th, 7th, and 9th protective aspects from its current transit sign. Explain how these aspects specifically support the natal promise (e.g., "Jupiter's transit aspect falls on your 7th house, opening the door for marriage").
   - Cross-examine Rahu-Ketu transits across relationship or career axes.

3. TIMING & DATE ACCURACY:
   - Strictly use the actual timeline dates provided below:
{windows_str if windows_str else "As listed in the Dasa-Bhukti context"}

ACTIVE TRANSIT CONTEXT:
{transit_str if transit_str else "As detailed in the source context"}

4. FULL COMPLETION (NO TRUNCATION):
   - You MUST generate all 4 numbered sections completely.
   - Never stop mid-sentence, mid-thought, or on a dangling conjunction. Complete every sentence thoroughly.

5. LANGUAGE & ADDRESSING:
   - {lang_instruction}
   - Address the user directly as "you" or analyze the native's chart directly.
   - Do NOT include legal disclaimers.
"""

        context_payload = f"{verified_anchor_block}\n\nRAW ASTROLOGICAL SOURCE DATA:\n" + (
            pdf_text if pdf_text else json.dumps(chart_data, ensure_ascii=False, indent=2))

        if is_chat_mode:
            clean_query = user_feedback.strip()
            prompt = f"""
{voice_instructions}
{astrological_guidelines}

USER ASTROLOGICAL QUESTION:
"{clean_query}"

SOURCE ASTROLOGICAL CONTEXT:
--------------------------------------------------
{context_payload}
--------------------------------------------------

Answer the user's question directly, insightfully, and decisively (220-300 words). Follow the "NATAL FIRST" Mandate before synthesizing the active Dasa/Bhukti Lord with the active Saturn and Jupiter transit phases (including Guru Drishti) counted directly from the verified Janma Rasi ({anchors['rasi']}). Complete your answer fully with no dangling sentences.
"""
            endpoint_name = "/palan/chat"
        else:
            prompt = f"""
{voice_instructions}
{astrological_guidelines}

MANDATORY REPORT STRUCTURE - YOU MUST COMPLETE ALL 4 SECTIONS FULLY:
<h3>{raw_topic_title} ANALYSIS & CHART REPORT</h3>

<h4>1. CHART PROFILE & CORE ASTROLOGICAL FACTS SUMMARY (D1, D9 & D10 OVERVIEW)</h4>
(Strictly follow the "NATAL FIRST" mandate. Analyze Lagna, primary houses governing {raw_topic_title}, and relevant planetary positions completely before mentioning current timing.)

<h4>2. PAST PATTERNS & ROOT INFLUENCES</h4>
(Analyze historical planetary triggers, savings/relationship stability, and root causes.)

<h4>3. DETAILED {raw_topic_title} ANALYSIS, DASA-BHUKTI & TRANSIT (GOCHARAM) SYNTHESIS</h4>
(Cross-examine the running Dasa-Bhukti Lord with Saturn's transit phase [Ashtama/Kandaka/Ezharai], Jupiter's transit state [Subha/Restrictive], and the 5th, 7th, and 9th Guru Drishti shields counted strictly from the verified Janma Rasi: {anchors['rasi']}.)

<h4>4. STRATEGIC RECOMMENDATIONS & REMEDIAL GUIDANCE</h4>
(Provide actionable practical lifestyle advice and traditional remedies completely.)

SOURCE ASTROLOGICAL CONTEXT:
--------------------------------------------------
{context_payload}
--------------------------------------------------

Generate the complete, exhaustive report for "{raw_topic_title}". Finish every sentence completely.
"""
            endpoint_name = f"/palan/{topic.lower()}"

        cleaned_text = ""

        for attempt in range(2):
            raw_text, _ = execute_gemini_with_fallback(client, prompt, endpoint_name=endpoint_name)

            raw_text = re.sub(r"(?m)^###\s*(.*)$", r"<h4>\1</h4>", raw_text)
            raw_text = re.sub(r"(?m)^\*\*(?:\d+\.|\b[A-Z0-9\s]{4,}\b)(.*?)\*\*$", r"<h4>\1</h4>", raw_text)
            raw_text = re.sub(r"(?m)^([1-4]\.\s+[A-Z\s\(\)&]+)(?:\n|$)", r"<h4>\1</h4>\n", raw_text)

            raw_text = re.sub(r"(?i)disclaimer:\s*this astrological analysis is provided.*$", "", raw_text)
            raw_text = re.sub(r"\bHello\s+[A-Za-z]+,?", "", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"\bDear\s+[A-Za-z]+,?", "", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", raw_text)

            raw_lines = [p.strip() for p in raw_text.split("\n") if p.strip()]
            formatted_paragraphs = []
            curr_para = []

            for line in raw_lines:
                if line.startswith("<h3") or line.startswith("<h4"):
                    if curr_para:
                        formatted_paragraphs.append(f'<p class="reading-para">{" ".join(curr_para)}</p>')
                        curr_para = []
                    formatted_paragraphs.append(line)
                else:
                    curr_para.append(line)

            if curr_para:
                formatted_paragraphs.append(f'<p class="reading-para">{" ".join(curr_para)}</p>')

            cleaned_text = "\n".join(formatted_paragraphs)

            ends_cleanly = cleaned_text.rstrip().endswith((".", "!", "?", "</p>", "</h4>"))
            if not ends_cleanly and attempt == 0:
                logger.warning("Draft was truncated mid-sentence. Retrying...")
                continue

            break

        return f'<div class="reading">\n{cleaned_text}\n</div>'

    except Exception as e:
        return _friendly_error(e, "prediction")


def generate_tamil_palan(chart_data: dict, language: str = "English") -> str:
    return generate_topic_reading(chart_data, topic="work", language=language, is_chat_reply=False)


def generate_vidhu_chat_response(chat_payload: dict) -> str:
    chart = chat_payload.get("chart", {})
    language = chat_payload.get("language", "English")
    topic = chat_payload.get("topic", "work")
    user_query = chat_payload.get("user_feedback", "")

    return generate_topic_reading(
        chart_data=chart,
        topic=topic,
        language=language,
        is_chat_reply=True,
        user_feedback=user_query,
        pdf_text=chat_payload.get("pdf_text", "")
    )