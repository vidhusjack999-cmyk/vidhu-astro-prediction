# -*- coding: utf-8 -*-
"""
rule_service.py
Key-Indexed Classical Rule Engine for Vidhu Astro.
Provides deterministic sloka lookups based on calculated chart facts.
Includes classical rules for Trikonas, Kendras, Moolatrikona zones,
Parivartana Dhana Yogas, and Vipareeta Raja Yogas.
"""

import json

CLASSICAL_RULES_DB = {
    "MARS_HOUSE_7": {
        "rule_id": "CHEVVAI_7H",
        "source_text": "Jathaga Alangaram",
        "chapter_verse": "Verse 142 (Santhanam Edition)",
        "verification_status": "Astrologer Audited",
        "palan_en": "Mars in 7th house indicates potential marital friction unless neutralized by Jupiter aspect or dignity.",
        "palan_ta": "7-ஆம் இடத்தில் செவ்வாய் இருந்தால் திருமண வாழ்க்கையில் சவால்கள் ஏற்படும்.",
        "topics": ["marriage", "relationship", "overall"]
    },
    "JUPITER_ASPECT_RAHU": {
        "rule_id": "SARPA_NIVRUTTI",
        "source_text": "Brihat Parasara Hora Shastra",
        "chapter_verse": "Chapter 31, Verse 12",
        "verification_status": "Astrologer Audited",
        "palan_en": "Jupiter's aspect on Rahu neutralizes Sarpa/Nodal affliction completely, preserving relationship stability.",
        "palan_ta": "ராகு மீது குருவின் பார்வை இருந்தால் சர்ப்ப தோஷம் நிவர்த்தியாகும்.",
        "topics": ["dosha", "marriage", "overall"]
    },
    "SATURN_HOUSE_10": {
        "rule_id": "SANI_10H",
        "source_text": "Phaladeepika",
        "chapter_verse": "Chapter 8, Verse 18",
        "verification_status": "Astrologer Audited",
        "palan_en": "Saturn in 10th house favors steady career growth, executive discipline, and high status through perseverance.",
        "palan_ta": "10-ஆம் இடத்தில் சனி இருந்தால் விடாமுயற்சியால் தொழில் வளர்ச்சி உண்டாகும்.",
        "topics": ["career", "work", "finance", "overall"]
    },
    "SUN_MERCURY_CONJUNCTION": {
        "rule_id": "BUDHADITYA_YOGA",
        "source_text": "Saravali",
        "chapter_verse": "Chapter 16, Verse 4",
        "verification_status": "Astrologer Audited",
        "palan_en": "Sun and Mercury conjunction creates Budhaditya Yoga, granting sharp analytical capacity, administrative writing power, and learning.",
        "palan_ta": "சூரியன் மற்றும் புதன் சேர்க்கை புத ஆதித்ய யோகத்தை அளித்து கூர்மையான புத்தி கூர்மையையும் அறிவையும் தரும்.",
        "topics": ["education", "career", "work", "overall"]
    },
    "MOON_JUPITER_KENDRA": {
        "rule_id": "GAJAKESARI_YOGA",
        "source_text": "Brihat Parasara Hora Shastra",
        "chapter_verse": "Chapter 35, Verse 9",
        "verification_status": "Astrologer Audited",
        "palan_en": "Jupiter in a Kendra from Moon creates Gajakesari Yoga, granting lasting public reputation, wisdom, and financial stability.",
        "palan_ta": "சந்திரனுக்கு கேந்திரத்தில் குரு அமைவது கஜகேசரி யோகத்தை வழங்கி நற்பெயரையும் செல்வத்தையும் தரும்.",
        "topics": ["finance", "career", "overall"]
    },
    "VIPAREETA_RAJA_YOGA": {
        "rule_id": "VIPAREETA_RY",
        "source_text": "Phaladeepika",
        "chapter_verse": "Chapter 6, Verses 58-63",
        "verification_status": "Astrologer Audited",
        "palan_en": "Dusthana lords placed in Dusthana houses create Vipareeta Raja Yoga (Harsha, Sarala, Vimala), granting sudden elevation and triumph over adversity.",
        "palan_ta": "மறைவு ஸ்தான அதிபதிகள் மறைவு ஸ்தானங்களில் அமைவது விபரீத ராஜ யோகத்தை வழங்கி தடைகளை வென்று பெரும் பதவி தரும்.",
        "topics": ["career", "work", "finance", "overall"]
    },
    "PARIVARTANA_DHANA_YOGA": {
        "rule_id": "PARIVARTANA_DHANA",
        "source_text": "Jathaga Alangaram",
        "chapter_verse": "Dhana Bhava Chapter, Verse 21",
        "verification_status": "Astrologer Audited",
        "palan_en": "Mutual sign exchange between trine/wealth lords (5th, 9th, 11th) forms Parivartana Dhana Yoga, ensuring substantial long-term wealth accumulation.",
        "palan_ta": "திரிகோண மற்றும் லாப ஸ்தான அதிபதிகள் பரிவர்த்தனை ஆவது பெரும் தன யோகத்தையும் சொத்துச் சேர்க்கையையும் தரும்.",
        "topics": ["finance", "career", "overall"]
    },
    "KENDRA_TRIKONA_RAJA_YOGA": {
        "rule_id": "KENDRA_TRIKONA_RY",
        "source_text": "Brihat Parasara Hora Shastra",
        "chapter_verse": "Chapter 34, Verse 16",
        "verification_status": "Astrologer Audited",
        "palan_en": "Association of Kendra (quadrant) and Trikona (trine) lords produces high authority, professional leadership, and societal respect.",
        "palan_ta": "கேந்திர மற்றும் திரிகோண அதிபதிகளின் தொடர்பு உயரிய தலைமைப் பண்பையும் அதிகாரத்தையும் அளிக்கும்.",
        "topics": ["career", "work", "overall"]
    },
    "MOOLATRIKONA_POTENCY": {
        "rule_id": "MOOLATRIKONA_STRENGTH",
        "source_text": "Saravali",
        "chapter_verse": "Chapter 4, Verses 12-15",
        "verification_status": "Astrologer Audited",
        "palan_en": "A planet in its Moolatrikona degree zone functions with maximum purposeful power, exceeding ordinary strength to deliver positive results.",
        "palan_ta": "மூலத்திரிகோண பாகையில் உள்ள கிரகம் உச்ச பலத்தை விட அதிக வலிமையுடன் நற்பலன்களைத் தரும்.",
        "topics": ["career", "finance", "overall"]
    },
    "HAMSA_YOGA": {
        "rule_id": "HAMSA_MAHAPURUSHA",
        "source_text": "Brihat Parasara Hora Shastra",
        "chapter_verse": "Chapter 75, Verse 7",
        "verification_status": "Astrologer Audited",
        "palan_en": "Jupiter exalted or in own sign in a Kendra forms Hamsa Mahapurusha Yoga, bestowing wisdom, righteous leadership, and lasting protection.",
        "palan_ta": "கேந்திரத்தில் குரு ஆட்சி அல்லது உச்சம் பெற்று அமைவது ஹம்ச யோகத்தை அளித்து உயர்ந்த அறிவையும் மரியாதையையும் தரும்.",
        "topics": ["career", "education", "overall"]
    }
}


def _get_house_from_lagna(planet_rasi_idx: int, lagna_rasi_idx: int) -> int:
    """Calculates 1-based house position from Lagna index."""
    if planet_rasi_idx is None or lagna_rasi_idx is None:
        return 0
    return ((planet_rasi_idx - lagna_rasi_idx) % 12) + 1


def retrieve_rules_for_chart(chart_data: dict, topic: str = "overall", max_rules: int = 6) -> list:
    """
    Performs key-indexed rule retrieval based strictly on calculated chart facts.
    Filters by topic if specified to prevent rule bloat in prompts.
    """
    matched_rules = []

    # Safely handle input payload if received as JSON string
    if isinstance(chart_data, str):
        try:
            chart_data = json.loads(chart_data)
        except Exception:
            chart_data = {}

    chart_data = chart_data or {}
    topic_clean = (topic or "overall").lower().strip()

    # Standardize planetary data source across engine dictionary schemas
    planets = (
        chart_data.get("planets")
        or chart_data.get("planetary_positions_and_dignity")
        or chart_data.get("planetary_positions")
        or {}
    )

    lagna_info = planets.get("Lagna", {}) if isinstance(planets, dict) else {}
    lagna_idx = lagna_info.get("rasi_idx") if isinstance(lagna_info, dict) else None

    def get_planet_house(p_name):
        if not isinstance(planets, dict):
            return 0
        p_data = planets.get(p_name, {})
        if not isinstance(p_data, dict):
            return 0
        if "house" in p_data and isinstance(p_data["house"], int):
            return p_data["house"]
        if lagna_idx is not None and "rasi_idx" in p_data and isinstance(p_data["rasi_idx"], int):
            return _get_house_from_lagna(p_data["rasi_idx"], lagna_idx)
        return 0

    # 1. Check Mars in 7th House
    if get_planet_house("Mars") == 7:
        matched_rules.append(CLASSICAL_RULES_DB["MARS_HOUSE_7"])

    # 2. Check Saturn in 10th House
    if get_planet_house("Saturn") == 10:
        matched_rules.append(CLASSICAL_RULES_DB["SATURN_HOUSE_10"])

    # 3. Check Sun-Mercury Conjunction (Budhaditya Yoga)
    sun_data = planets.get("Sun", {}) if isinstance(planets, dict) else {}
    merc_data = planets.get("Mercury", {}) if isinstance(planets, dict) else {}
    if (
        isinstance(sun_data, dict)
        and isinstance(merc_data, dict)
        and sun_data.get("rasi_idx") is not None
        and sun_data.get("rasi_idx") == merc_data.get("rasi_idx")
    ):
        matched_rules.append(CLASSICAL_RULES_DB["SUN_MERCURY_CONJUNCTION"])

    # 4. Check Jupiter Aspect on Rahu (Sarpa Nivrutti)
    jup_data = planets.get("Jupiter", {}) if isinstance(planets, dict) else {}
    rahu_data = planets.get("Rahu", {}) if isinstance(planets, dict) else {}
    if (
        isinstance(jup_data, dict)
        and isinstance(rahu_data, dict)
        and jup_data.get("rasi_idx") is not None
        and rahu_data.get("rasi_idx") is not None
    ):
        jup_rasi = jup_data["rasi_idx"]
        rahu_rasi = rahu_data["rasi_idx"]
        jup_aspects = [(jup_rasi + offset - 1) % 12 for offset in (1, 5, 7, 9)]
        if rahu_rasi in jup_aspects:
            matched_rules.append(CLASSICAL_RULES_DB["JUPITER_ASPECT_RAHU"])

    # 5. Check Gajakesari Yoga (Jupiter in Kendra from Moon)
    moon_data = planets.get("Moon", {}) if isinstance(planets, dict) else {}
    if (
        isinstance(jup_data, dict)
        and isinstance(moon_data, dict)
        and jup_data.get("rasi_idx") is not None
        and moon_data.get("rasi_idx") is not None
    ):
        diff_houses = ((jup_data["rasi_idx"] - moon_data["rasi_idx"]) % 12) + 1
        if diff_houses in [1, 4, 7, 10]:
            matched_rules.append(CLASSICAL_RULES_DB["MOON_JUPITER_KENDRA"])

    # 6. Check Hamsa Mahapurusha Yoga (Jupiter in Kendra in own/exalted sign)
    if (
        isinstance(jup_data, dict)
        and get_planet_house("Jupiter") in [1, 4, 7, 10]
        and jup_data.get("rasi_idx") in [3, 8, 11]  # Cancer (exalted), Sagittarius, Pisces
    ):
        matched_rules.append(CLASSICAL_RULES_DB["HAMSA_YOGA"])

    # 7. Check Special Yogas Present in Chart Payload
    yogas = chart_data.get("special_yogas_and_conjunctions") or chart_data.get("conjunctions_2_planet") or []
    if isinstance(yogas, list):
        for y in yogas:
            if isinstance(y, dict):
                title = y.get("title", "").lower()
                if "vipareeta" in title or "vipareet" in title:
                    if CLASSICAL_RULES_DB["VIPAREETA_RAJA_YOGA"] not in matched_rules:
                        matched_rules.append(CLASSICAL_RULES_DB["VIPAREETA_RAJA_YOGA"])
                if "parivartana" in title or "exchange" in title:
                    if CLASSICAL_RULES_DB["PARIVARTANA_DHANA_YOGA"] not in matched_rules:
                        matched_rules.append(CLASSICAL_RULES_DB["PARIVARTANA_DHANA_YOGA"])
                if "kendra-trikona" in title:
                    if CLASSICAL_RULES_DB["KENDRA_TRIKONA_RAJA_YOGA"] not in matched_rules:
                        matched_rules.append(CLASSICAL_RULES_DB["KENDRA_TRIKONA_RAJA_YOGA"])

    # 8. Check Moolatrikona Status across all planets
    if isinstance(planets, dict):
        for p_name, p_info in planets.items():
            if isinstance(p_info, dict) and "Moolatrikona" in p_info.get("dignity", ""):
                if CLASSICAL_RULES_DB["MOOLATRIKONA_POTENCY"] not in matched_rules:
                    matched_rules.append(CLASSICAL_RULES_DB["MOOLATRIKONA_POTENCY"])
                    break

    # Topic Filtering - Enforces type safety on matched_rules items
    if topic_clean and topic_clean != "overall":
        filtered = [
            r for r in matched_rules
            if isinstance(r, dict) and "topics" in r and any(t in topic_clean for t in r["topics"])
        ]
        if filtered:
            matched_rules = filtered

    return [r for r in matched_rules if isinstance(r, dict)][:max_rules]


# Alias for orchestrator compatibility
retrieve_rules_for_chart_topic = retrieve_rules_for_chart