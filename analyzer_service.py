# -*- coding: utf-8 -*-
"""
analyzer_service.py
Deterministic Jyotish Judgment Engine.
Evaluates birth facts, assigns weights, determines verdicts,
and computes timing windows before the LLM generates prose.
"""

from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

VERDICTS = {
    "CAREER_FIRST": ["career first", "career comes first", "career takes precedence"],
    "MARRIAGE_DELAYED": ["marriage is delayed", "marriage timing is delayed", "partnership unfolds later"],
    "CONDITIONAL": ["conditional", "depends on", "requires careful matching"],
    "POSSIBLE": ["possible with caveats", "indicates potential"],
    "UNLIKELY": ["unlikely during this window", "obstructed in this phase"]
}

SCORING_WEIGHTS = {
    "marriage": {
        "jupiter_aspect_7th": +2.0,
        "venus_in_d9_7th": +2.0,
        "7th_lord_in_dusthana": -2.0,
        "venus_combust": -2.5,
        "rahu_in_7th": -2.0,
        "punarphu_dosha": -1.5,
        "7th_lord_retrograde": -1.0
    },
    "career": {
        "10th_lord_in_11th": +3.0,
        "vipareeta_raja_yoga_6th": +2.5,
        "d10_mars_in_lagna": +2.5,
        "saturn_transit_10th_moon": -1.0  # Slow, disciplined work
    }
}

def compute_confidence(net_weight: float) -> str:
    if net_weight >= 6.0:
        return "high"
    elif net_weight >= 2.0:
        return "moderate"
    return "low"