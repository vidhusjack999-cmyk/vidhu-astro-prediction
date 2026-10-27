# -*- coding: utf-8 -*-
"""
dosha_rules.py
Deterministic Vedic Astrological Dosha & Cancellation (Bhanga) Calculator.
"""

def analyze_doshas(chart_data: dict) -> dict:
    """
    Evaluates key Doshas and their classical cancellation rules deterministically.
    Returns a ground-truth dictionary to be passed into LLM prompts.
    """
    # Extract basic facts from chart_data
    lagna = chart_data.get("lagna", "")
    rasi = chart_data.get("rasi", "")
    planets = chart_data.get("planets", {})

    dosha_status = {}

    # 1. Kemadruma Dosha Assessment
    # Default rule: No physical planets in 2nd or 12th from Moon
    has_adjacent_planets = chart_data.get("has_planets_adjacent_to_moon", False)
    kendra_planets_present = chart_data.get("has_kendra_planets_from_moon_or_lagna", True)

    if not has_adjacent_planets:
        if kendra_planets_present:
            dosha_status["kemadruma"] = "NEUTRALIZED / CANCELLED (Supported by Kendra placements from Lagna/Moon)"
        else:
            dosha_status["kemadruma"] = "PRESENT (No adjacent planets or Kendra support)"
    else:
        dosha_status["kemadruma"] = "NOT PRESENT"

    # 2. Manglik / Chevvai Dosham Assessment
    mars_house_from_lagna = chart_data.get("mars_house_lagna", 5)
    mars_house_from_moon = chart_data.get("mars_house_moon", 4)

    if mars_house_from_lagna in (1, 2, 4, 7, 8, 12):
        dosha_status["manglik_chevvai"] = f"PRESENT from Lagna (Mars in House {mars_house_from_lagna})"
    elif mars_house_from_moon in (1, 2, 4, 7, 8, 12):
        dosha_status["manglik_chevvai"] = f"PRESENT from Moon (Mars in House {mars_house_from_moon} from Moon)"
    else:
        dosha_status["manglik_chevvai"] = "NOT PRESENT from Lagna"

    # 3. Punarphu Dosha Assessment (Saturn aspect on Moon)
    saturn_aspects_moon = chart_data.get("saturn_aspects_moon", True)
    if saturn_aspects_moon:
        dosha_status["punarphu"] = "PRESENT (Saturn aspects the Moon)"
    else:
        dosha_status["punarphu"] = "NOT PRESENT"

    # 4. Rahu-Ketu Axis Assessment
    rahu_house = chart_data.get("rahu_house", 1)
    ketu_house = chart_data.get("ketu_house", 7)
    if rahu_house in (1, 7) and ketu_house in (1, 7):
        dosha_status["rahu_ketu"] = f"PRESENT (Rahu in House {rahu_house}, Ketu in House {ketu_house})"
    else:
        dosha_status["rahu_ketu"] = "NOT PRESENT across primary axes"

    return dosha_status