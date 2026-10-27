# -*- coding: utf-8 -*-
"""
gemini_models.py
Dynamically fetches active text models for your API key.
Filters out non-text/audio/image/live models and ranks them by version.
Caches results for 1 hour to ensure zero performance overhead.
Optimized for high-speed response generation across modern Gemini SDK versions.
"""

import os
import re
import time

_SKIP = (
    "image", "tts", "audio", "live", "embedding", "robotics",
    "imagen", "veo", "lyria", "vision", "bison", "gecko"
)
_cache = {"t": 0.0, "names": []}

# Production fallbacks prioritizing fast flash models
DEFAULT_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]


def list_text_models(client):
    """Fetches all model names supporting content generation for your active API key."""
    names = []
    try:
        # Handles modern google.genai Client and legacy SDKs
        if hasattr(client, "models") and hasattr(client.models, "list"):
            model_pager = client.models.list()
        elif hasattr(client, "list_models"):
            model_pager = client.list_models()
        else:
            return DEFAULT_FALLBACK_MODELS

        for m in model_pager:
            raw_name = getattr(m, "name", str(m))
            model_name = raw_name.replace("models/", "").strip()

            actions = (
                getattr(m, "supported_actions", None)
                or getattr(m, "supported_generation_methods", [])
                or []
            )

            # Check if model supports text generation
            supports_generation = (
                "generateContent" in actions
                or "generate_content" in actions
                or not actions
            )

            if supports_generation:
                names.append(model_name)

    except Exception as e:
        print(f"--> [WARN] Failed to dynamically fetch model list: {e}")
        return DEFAULT_FALLBACK_MODELS

    return names


def rank_models(names, tiers=("flash", "flash-lite", "pro")):
    """Ranks available models preferring newer versions and stable builds."""
    filtered = [n for n in names if not any(s in n.lower() for s in _SKIP)]

    if not filtered:
        return DEFAULT_FALLBACK_MODELS

    def parse_score(name):
        lower_name = name.lower()

        # Extract version number if present (e.g. 2.5, 2.0, 1.5)
        match = re.search(r"(\d+(?:\.\d+)?)", lower_name)
        ver = float(match.group(1)) if match else 1.0

        # Rank by tier preference (flash -> flash-lite -> pro)
        tier_score = len(tiers)
        for idx, t in enumerate(tiers):
            if t in lower_name:
                tier_score = idx
                break

        # Prefer stable models over experimental/preview
        is_preview = 1 if ("preview" in lower_name or "exp" in lower_name) else 0

        # Primary sort: Tier (flash first), Secondary: Higher Version (-ver), Tertiary: Stable over preview
        return (tier_score, -ver, is_preview)

    filtered.sort(key=parse_score)
    return filtered


def get_models(client, ttl=3600):
    """Returns an ordered fallback list of active models. Caches for 1 hour."""
    env = os.environ.get("GEMINI_MODELS")
    if env:
        return [x.strip() for x in env.split(",") if x.strip()]

    now = time.time()
    if now - _cache["t"] > ttl or not _cache["names"]:
        fetched = list_text_models(client)
        ranked = rank_models(fetched)

        # Ensure cache array is non-empty
        _cache["names"] = ranked if ranked else DEFAULT_FALLBACK_MODELS
        _cache["t"] = now

    return _cache["names"]


def invalidate_cache():
    """Flushes model cache if a 404 occurs so retired models are purged immediately."""
    _cache["t"] = 0.0
    _cache["names"] = []