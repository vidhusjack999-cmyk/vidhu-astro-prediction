# -*- coding: utf-8 -*-
"""
astro_engine.py
Vedic Astrology Engine with Swiss Ephemeris Integration.
Includes dynamic classical transit classification (Ezharai Sani, Ashtama Sani,
Kandaka Sani, Janma Guru, Ashtama Guru, Guru Drishti) synthesized with
active running Dasa-Bhukti periods and accurate Pitru Dosha logic.
"""

from datetime import datetime, timedelta, timezone
from collections import OrderedDict
import operator
import swisseph as swe


# ============================================================
# UTILITIES & HELPER FUNCTIONS
# ============================================================

def ordinal(n):
    """Returns the ordinal string for a given integer (e.g., 1st, 2nd, 3rd)."""
    return f"{n}" + ("th" if 11 <= (n % 100) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def get_gandanta_status(lon):
    """Checks for Gandanta in the classical 3°20' junction orb."""
    norm_deg = lon % 360
    rasi_idx = int(norm_deg // 30)
    rel_deg = norm_deg % 30
    if rasi_idx in [3, 7, 11] and rel_deg >= 26.666:
        return " [Weakened by Gandanta (Last 3°20')]"
    if rasi_idx in [0, 4, 8] and rel_deg <= 3.333:
        return " [Weakened by Gandanta (First 3°20')]"
    return ""


def find_sign_changes(planet_id, start_jd, current_sign, scan_days=1500):
    """Scans forward to find the exact date a planet changes signs."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    fl = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    jd = start_jd
    for _ in range(scan_days):
        jd += 1.0
        lon = swe.calc_ut(jd, planet_id, fl)[0][0] % 360
        sign = int(lon // 30)
        if sign != current_sign:
            y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
            dt = datetime(int(y), int(m), int(d)) + timedelta(hours=h + 5.5)  # IST correction
            return dt.strftime("%d-%m-%Y"), sign
    return "Upcoming", (current_sign + 1) % 12


# ============================================================
# DATA TABLES & METADATA
# ============================================================

TITHI_NAMES = [
    "Pratipada (பிரதமை)", "Dwitiya (துவிதியை)", "Tritiya (திரிதியை)",
    "Chaturthi (சதுர்த்தி)", "Panchami (பஞ்சமி)", "Shashthi (சஷ்டி)",
    "Saptami (சப்தமி)", "Ashtami (அஷ்டமி)", "Navami (நவமி)",
    "Dashami (தசமி)", "Ekadashi (ஏகாதசி)", "Dwadashi (துவாதசி)",
    "Trayodashi (திரயோதசி)", "Chaturdashi (சதுர்த்தசி)", "Purnima/Amavasya (பௌர்ணமி/அமாவாசை)"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigasira", "Ardra",
    "Punarvasu", "Pushya", "Aslesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Visakha", "Anuradha", "Jyestha",
    "Moola", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Satabisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

NAKSHATRA_TAMIL = [
    "அசுவினி", "பரணி", "கார்த்திகை", "ரோகிணி", "மிருகசீரிடம்", "திருவாதிரை",
    "புனர்பூசம்", "பூசம்", "ஆயில்யம்", "மகம்", "பூரம்", "உத்திரம்",
    "ஹஸ்தம்", "சித்திரை", "சுவாதி", "விசாகம்", "அனுஷம்", "கேட்டை",
    "மூலம்", "பூராடம்", "உத்திராடம்", "திருவோணம்", "அவிட்டம்", "சதயம்",
    "பூரட்டாதி", "உத்திரட்டாதி", "ரேவதி"
]

RASIS = [
    "Mesha", "Rishaba", "Mithuna", "Kataka",
    "Simha", "Kanya", "Tula", "Vrichika",
    "Dhanus", "Makara", "Kumbha", "Meena"
]

RASIS_TAMIL = [
    "மேஷம்", "ரிஷபம்", "மிதுனம்", "கடகம்",
    "சிம்மம்", "கன்னி", "துலாம்", "விருச்சிகம்",
    "தனுசு", "மகரம்", "கும்பம்", "மீனம்"
]

RASIS_EN = RASIS
RASIS_TA = RASIS_TAMIL

RASI_OWNERS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

DEBILITATION_SIGNS = {"Sun": 6, "Moon": 7, "Mars": 3, "Mercury": 11, "Jupiter": 9, "Venus": 5, "Saturn": 0}

NATURAL_RELATIONSHIPS = {
    "Sun": {"friends": ["Moon", "Mars", "Jupiter"], "enemies": ["Venus", "Saturn"], "neutral": ["Mercury"]},
    "Moon": {"friends": ["Sun", "Mercury"], "enemies": [], "neutral": ["Mars", "Jupiter", "Venus", "Saturn"]},
    "Mars": {"friends": ["Sun", "Moon", "Jupiter"], "enemies": ["Mercury"], "neutral": ["Venus", "Saturn"]},
    "Mercury": {"friends": ["Sun", "Venus"], "enemies": ["Moon"], "neutral": ["Mars", "Jupiter", "Saturn"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "enemies": ["Mercury", "Venus"], "neutral": ["Saturn"]},
    "Venus": {"friends": ["Mercury", "Saturn"], "enemies": ["Sun", "Moon"], "neutral": ["Mars", "Jupiter"]},
    "Saturn": {"friends": ["Mercury", "Venus"], "enemies": ["Sun", "Moon", "Mars"], "neutral": ["Jupiter"]}
}

WEEKDAY_NAMES = {
    0: ("Monday", "திங்கட்கிழமை"),
    1: ("Tuesday", "செவ்வாய்க்கிழமை"),
    2: ("Wednesday", "புதன்கிழமை"),
    3: ("Thursday", "வியாழக்கிழமை"),
    4: ("Friday", "வெள்ளிக்கிழமை"),
    5: ("Saturday", "சனிக்கிழமை"),
    6: ("Sunday", "ஞாயிற்றுக்கிழமை")
}

COMBUSTION_ORBS = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": {"direct": 14.0, "retrograde": 12.0},
    "Jupiter": 11.0,
    "Venus": {"direct": 10.0, "retrograde": 8.0},
    "Saturn": 15.0
}

DASA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASA_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]

NAKSHATRA_METADATA = {
    "Ashwini": {"lord": "Ketu", "yoni": "Horse (குதிரை)", "gana": "Deva (தேவ)"},
    "Bharani": {"lord": "Venus (சுக்)", "yoni": "Elephant (யானை)", "gana": "Manushya (மனித)"},
    "Krittika": {"lord": "Sun (சூரி)", "yoni": "Goat (ஆடு)", "gana": "Rakshasa (ராட்சச)"},
    "Rohini": {"lord": "Moon (சந்)", "yoni": "Serpent (பாம்பு)", "gana": "Manushya (மனித)"},
    "Mrigasira": {"lord": "Mars (செவ்)", "yoni": "Serpent (பாம்பு)", "gana": "Deva (தேவ)"},
    "Ardra": {"lord": "Rahu (ராகு)", "yoni": "Dog (நாய்)", "gana": "Manushya (மனித)"},
    "Punarvasu": {"lord": "Jupiter (குரு)", "yoni": "Cat (பூனை)", "gana": "Deva (தேவ)"},
    "Pushya": {"lord": "Saturn (சனி)", "yoni": "Goat (ஆடு)", "gana": "Deva (தேவ)"},
    "Aslesha": {"lord": "Mercury (புத)", "yoni": "Cat (பூனை)", "gana": "Rakshasa (ராட்சச)"},
    "Magha": {"lord": "Ketu (கேது)", "yoni": "Rat (எலி)", "gana": "Rakshasa (ராட்சச)"},
    "Purva Phalguni": {"lord": "Venus (சுக்)", "yoni": "Rat (எலி)", "gana": "Manushya (மனித)"},
    "Uttara Phalguni": {"lord": "Sun (சூரி)", "yoni": "Cow (பசு)", "gana": "Manushya (மனித)"},
    "Hasta": {"lord": "Moon (சந்)", "yoni": "Buffalo (எருமை)", "gana": "Deva (தேவ)"},
    "Chitra": {"lord": "Mars (செவ்)", "yoni": "Tiger (புலி)", "gana": "Rakshasa (ராட்சச)"},
    "Swati": {"lord": "Rahu (ராகு)", "yoni": "Buffalo (எருமை)", "gana": "Deva (தேவ)"},
    "Visakha": {"lord": "Jupiter (குரு)", "yoni": "Tiger (புலி)", "gana": "Rakshasa (ராட்சச)"},
    "Anuradha": {"lord": "Saturn (சனி)", "yoni": "Deer (மான்)", "gana": "Deva (தேவ)"},
    "Jyestha": {"lord": "Mercury (புத)", "yoni": "Deer (மான்)", "gana": "Rakshasa (ராட்சச)"},
    "Moola": {"lord": "Ketu (கேது)", "yoni": "Dog (நாய்)", "gana": "Rakshasa (ராட்சச)"},
    "Purva Ashadha": {"lord": "Venus (சுக்)", "yoni": "Monkey (குரங்கு)", "gana": "Manushya (மனித)"},
    "Uttara Ashadha": {"lord": "Sun (சூரி)", "yoni": "Mongoose (கீரி)", "gana": "Manushya (மனித)"},
    "Shravana": {"lord": "Moon (சந்)", "yoni": "Monkey (குரங்கு)", "gana": "Deva (தேவ)"},
    "Dhanishta": {"lord": "Mars (செவ்)", "yoni": "Lion (சிங்கம்)", "gana": "Rakshasa (ராட்சச)"},
    "Satabisha": {"lord": "Rahu (ராகு)", "yoni": "Horse (குதிரை)", "gana": "Rakshasa (ராட்சச)"},
    "Purva Bhadrapada": {"lord": "Jupiter (குரு)", "yoni": "Lion (சிங்கம்)", "gana": "Manushya (மனித)"},
    "Uttara Bhadrapada": {"lord": "Saturn (சனி)", "yoni": "Cow (பசு)", "gana": "Manushya (மனித)"},
    "Revati": {"lord": "Mercury (புத)", "yoni": "Elephant (யானை)", "gana": "Deva (தேவ)"}
}


# ============================================================
# NORMALIZATION & DIVISIONAL HELPERS
# ============================================================

def norm360(deg):
    return float(deg) % 360.0


def calculate_dasamsa_sign(rasi_idx, rel_deg):
    part_idx = int(rel_deg // 3.0)
    if part_idx > 9:
        part_idx = 9
    return (rasi_idx + part_idx) % 12 if rasi_idx % 2 == 0 else (rasi_idx + 8 + part_idx) % 12


def calculate_d20_sign(rasi_idx, rel_deg):
    part_size = 1.5
    part_index = min(int(rel_deg // part_size), 19)
    start_map = {0: 0, 1: 8, 2: 4}
    return (start_map[rasi_idx % 3] + part_index) % 12


def deg_to_rasi_and_nakshatra(deg):
    norm_d = norm360(deg)
    rasi_idx = int(norm_d // 30)
    rel_deg = norm_d % 30
    rasi_name = RASIS[rasi_idx]
    rasi_ta = RASIS_TAMIL[rasi_idx]

    nak_idx = int(norm_d // (13 + 1 / 3)) % 27
    nak_name = NAKSHATRAS[nak_idx]
    nak_ta = NAKSHATRA_TAMIL[nak_idx]
    pada = int((norm_d % (13 + 1 / 3)) // (3 + 1 / 3)) + 1

    total_padas = int(norm_d // (3 + 1 / 3))
    navamsa_idx = total_padas % 12
    navamsa_name = RASIS[navamsa_idx]

    dasamsa_idx = calculate_dasamsa_sign(rasi_idx, rel_deg)
    dasamsa_name = RASIS[dasamsa_idx]

    d20_idx = calculate_d20_sign(rasi_idx, rel_deg)
    d20_name = RASIS[d20_idx]

    rel_deg_int = int(rel_deg)
    rel_min_int = int((rel_deg % 1) * 60)

    return {
        "deg": norm_d,
        "formatted_deg": f"{rasi_name} {rel_deg_int}° {rel_min_int}'",
        "absolute_deg": f"{int(norm_d)}° {int((norm_d % 1) * 60)}'",
        "rasi": rasi_name,
        "rasi_ta": rasi_ta,
        "rasi_display": f"{rasi_name} ({rasi_ta})",
        "rasi_idx": rasi_idx,
        "rel_deg": round(rel_deg, 2),
        "nakshatra": nak_name,
        "nakshatra_display": f"{nak_name} ({nak_ta}) - {pada}",
        "pada": pada,
        "nakshatra_pada": f"{nak_name} {pada}",
        "navamsa": navamsa_name,
        "dasamsa": dasamsa_name,
        "vimshamsa_d20": d20_name
    }


def calculate_precise_gulika_longitude(dt, lat, lon):
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    def local_to_jd(local_dt):
        utc_dt = local_dt - timedelta(hours=5, minutes=30)
        return swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
        )

    def jd_to_local_dt(jd_val):
        year, month, day, ut_hour = swe.revjul(jd_val, swe.GREG_CAL)
        utc_dt = datetime(int(year), int(month), int(day))
        utc_dt += timedelta(hours=float(ut_hour))
        return utc_dt + timedelta(hours=5, minutes=30)

    def get_sun_event(local_date, event_flag):
        date_jd = swe.julday(local_date.year, local_date.month, local_date.day, 0.0)
        result = swe.rise_trans(
            date_jd, swe.SUN, event_flag | swe.BIT_DISC_CENTER,
            (float(lon), float(lat), 0.0), 1013.25, 15.0
        )
        return jd_to_local_dt(result[1][0])

    birth_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    sunrise_today = get_sun_event(birth_midnight, swe.CALC_RISE)
    sunset_today = get_sun_event(birth_midnight, swe.CALC_SET)
    sunrise_next = get_sun_event(birth_midnight + timedelta(days=1), swe.CALC_RISE)

    if sunrise_today <= dt < sunset_today:
        period_start = sunrise_today
        period_end = sunset_today
        is_daytime = True
    elif dt >= sunset_today:
        period_start = sunset_today
        period_end = sunrise_next
        is_daytime = False
    else:
        sunset_previous = get_sun_event(birth_midnight - timedelta(days=1), swe.CALC_SET)
        period_start = sunset_previous
        period_end = sunrise_today
        is_daytime = False

    weekday_idx = (dt.weekday() + 1) % 7
    day_saturn_portion = [7, 6, 5, 4, 3, 2, 1]
    night_saturn_portion = [3, 2, 1, 7, 6, 5, 4]

    saturn_portion = day_saturn_portion[weekday_idx] if is_daytime else night_saturn_portion[weekday_idx]
    period_seconds = (period_end - period_start).total_seconds()
    portion_seconds = period_seconds / 8.0

    gulika_start_dt = period_start + timedelta(seconds=portion_seconds * (saturn_portion - 1))
    gulika_jd_ut = local_to_jd(gulika_start_dt)

    houses_result = swe.houses_ex(gulika_jd_ut, float(lat), float(lon), b"P", swe.FLG_SIDEREAL)
    return float(houses_result[1][0]) % 360.0


def check_moolatrikona(planet_name, rasi_name, rel_deg):
    zones = {
        "Sun": ("Simha", 4.0, 20.0), "Moon": ("Rishaba", 4.0, 20.0), "Mars": ("Mesha", 0.0, 12.0),
        "Mercury": ("Kanya", 16.0, 20.0), "Jupiter": ("Dhanus", 0.0, 10.0), "Venus": ("Tula", 0.0, 15.0),
        "Saturn": ("Kumbha", 0.0, 20.0)
    }
    zone = zones.get(planet_name)
    if zone:
        sign, start_deg, end_deg = zone
        if rasi_name == sign and start_deg <= rel_deg <= end_deg:
            return "Moolatrikona (மூலத்திரிகோணம்)"
    return None


def evaluate_planet_dignity(planet_name, rasi_idx, rel_deg, rasi_name=None):
    if rasi_name is None:
        rasi_name = RASIS[rasi_idx]
    if planet_name in ["Lagna", "Gulika"]:
        return "N/A"

    mt = check_moolatrikona(planet_name, rasi_name, rel_deg)
    if mt:
        return mt

    exaltations = {
        "Sun": (0, 10.0), "Moon": (1, 3.0), "Mars": (9, 28.0),
        "Mercury": (5, 15.0), "Jupiter": (3, 5.0), "Venus": (11, 27.0),
        "Saturn": (6, 20.0), "Rahu": (1, 20.0), "Ketu": (7, 20.0)
    }
    debilitations = {
        "Sun": (6, 10.0), "Moon": (7, 3.0), "Mars": (3, 28.0),
        "Mercury": (11, 15.0), "Jupiter": (9, 5.0), "Venus": (5, 27.0),
        "Saturn": (0, 20.0), "Rahu": (7, 20.0), "Ketu": (1, 20.0)
    }

    if planet_name in exaltations and rasi_idx == exaltations[planet_name][0]:
        return "Ucha (Exalted / உச்சம்)"
    if planet_name in debilitations and rasi_idx == debilitations[planet_name][0]:
        return "Neecha (Debilitated / நீசம்)"

    own_signs = {
        "Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
        "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]
    }
    if planet_name in own_signs and rasi_idx in own_signs[planet_name]:
        return "Aatchi (Own Sign / ஆட்சி)"

    if planet_name in NATURAL_RELATIONSHIPS:
        dispositor = RASI_OWNERS[rasi_idx]
        rel = NATURAL_RELATIONSHIPS[planet_name]
        if dispositor in rel["friends"]:
            return "Natpu (Friendly / நட்பு)"
        elif dispositor in rel["enemies"]:
            return "Pagai (Inimical / பகை)"
        else:
            return "Samam (Neutral / சமம்)"

    return "Samam (Neutral / சமம்)"


def check_combustion_status(planet_name, planet_deg, sun_deg, is_retrograde=False):
    if planet_name in ("Sun", "Lagna", "Gulika", "Rahu", "Ketu"):
        return False, 0.0

    diff = abs(planet_deg - sun_deg)
    if diff > 180.0:
        diff = 360.0 - diff

    orb_spec = COMBUSTION_ORBS.get(planet_name)
    if not orb_spec:
        return False, diff

    max_orb = orb_spec["retrograde" if is_retrograde else "direct"] if isinstance(orb_spec, dict) else orb_spec
    return (diff <= max_orb), diff


def get_functional_tag(planet_name, lagna_idx):
    if planet_name in ("Lagna", "Gulika", "Rahu", "Ketu"):
        return "N/A"

    owned_houses = []
    for house_num in range(1, 13):
        sign_idx = (lagna_idx + house_num - 1) % 12
        if RASI_OWNERS[sign_idx] == planet_name:
            owned_houses.append(house_num)

    tags = []
    for house_num in owned_houses:
        if house_num in (1, 4, 7, 10):
            tags.append(f"Kendra Lord (House {house_num})")
        elif house_num in (5, 9):
            tags.append(f"Trikona Lord (House {house_num})")
        elif house_num in (6, 8, 12):
            tags.append(f"Dusthana Lord (House {house_num})")
        elif house_num in (2, 11):
            tags.append(f"Dhana Lord (House {house_num})")
        else:
            tags.append(f"Lord of House {house_num}")

    return " & ".join(tags) if tags else "Neutral Lord"


# ============================================================
# DYNAMIC TRANSIT CLASSIFIERS (SATURN & JUPITER)
# ============================================================

def classify_saturn_transit_phase(saturn_rasi_idx, natal_moon_rasi_idx, active_dasa_lord="", active_bhukti_lord=""):
    house_from_moon = ((saturn_rasi_idx - natal_moon_rasi_idx) % 12) + 1

    phases = {
        12: {
            "phase_name_en": "Ezharai Sani Phase 1: Viraya Sani / Mangu Sani",
            "phase_name_ta": "ஏழரை சனி - முதல் சுற்று: விரய சனி / மங்கு சனி",
            "severity": "HIGH",
            "core_theme": "This marks the first 2.5 years of the 7.5-year Sade Sati cycle. It generally brings high expenditure, mental restlessness, sleep disruption, and potential shifts related to foreign travel, isolation, or distancing from routine duties."
        },
        1: {
            "phase_name_en": "Ezharai Sani Phase 2: Janma Sani",
            "phase_name_ta": "ஏழரை சனி - இரண்டாம் சுற்று: ஜென்ம சனி",
            "severity": "VERY HIGH",
            "core_theme": "This is the core peak of the Sade Sati cycle. It places direct pressure on physical vitality and mental peace, typically bringing heavy workloads, fatigue, testing of patience, and major identity recalibration."
        },
        2: {
            "phase_name_en": "Ezharai Sani Phase 3: Paadha Sani / Marana Sani",
            "phase_name_ta": "ஏழரை சனி - மூன்றாம் சுற்று: பாத சனி / மரண சனி",
            "severity": "MODERATE-HIGH",
            "core_theme": "Financial consolidation, family speech diplomacy needed, easing of peak 7.5-year pressure."
        },
        4: {
            "phase_name_en": "Kandaka Sani: Ardhastama Sani",
            "phase_name_ta": "கண்டக சனி: அர்த்தாஷ்டம சனி",
            "severity": "MODERATE",
            "core_theme": "Domestic unrest, property/vehicle adjustments, emotional restlessness at home."
        },
        7: {
            "phase_name_en": "Kandaka Sani: Kalathra Kandakam",
            "phase_name_ta": "கண்டக சனி: ஏழாம் இடத்து சனி",
            "severity": "MODERATE",
            "core_theme": "Partnership friction, demands patience in spouse interactions and public dealings."
        },
        8: {
            "phase_name_en": "Ashtama Sani",
            "phase_name_ta": "அஷ்டம சனி",
            "severity": "VERY HIGH",
            "core_theme": "Sudden roadblocks, financial turbulence, intense stress, requires avoiding risky speculations."
        },
        10: {
            "phase_name_en": "Kandaka Sani: Karma Sani",
            "phase_name_ta": "கண்டக சனி: கர்ம சனி",
            "severity": "MODERATE",
            "core_theme": "Workplace restructuring, test of professional endurance, heavy responsibilities."
        },
        3: {
            "phase_name_en": "Upachaya Success",
            "phase_name_ta": "சுப சஞ்சாரம்: 3-ம் இடத்து சனி",
            "severity": "FAVORABLE",
            "core_theme": "Courage, victory over obstacles, initiatives bear fruit."
        },
        6: {
            "phase_name_en": "Shatru Jaya",
            "phase_name_ta": "சுப சஞ்சாரம்: 6-ம் இடத்து சனி",
            "severity": "FAVORABLE",
            "core_theme": "Overcoming competition, debt clearance, competitive professional success."
        },
        11: {
            "phase_name_en": "Labha Sani",
            "phase_name_ta": "சுப சஞ்சாரம்: 11-ம் இடத்து சனி (லாப சனி)",
            "severity": "VERY FAVORABLE",
            "core_theme": "Financial expansion, long-term gains, fulfillment of ambitions."
        }
    }

    phase_data = phases.get(house_from_moon, {
        "phase_name_en": f"Neutral Transit",
        "phase_name_ta": f"சாதாரண சஞ்சாரம் (சந்திரனுக்கு {house_from_moon}-ம் இடம்)",
        "severity": "NEUTRAL",
        "core_theme": "Steady progression with standard discipline."
    })

    dasa_synergy = []
    if active_dasa_lord in ["Rahu", "Ketu"]:
        dasa_synergy.append(
            f"Under {active_dasa_lord} Dasa, this phase amplifies psychological restlessness, "
            f"impulsive urges, and desires to detach from routine duties."
        )
    elif active_dasa_lord == "Saturn":
        dasa_synergy.append(
            f"Because Saturn is your running Dasa Lord, this phase becomes the defining life-direction driver."
        )

    if active_bhukti_lord == "Moon" and house_from_moon in [1, 8, 12]:
        dasa_synergy.append(
            f"CRITICAL OVERLAP: Running Moon Bhukti while transit Saturn afflicts the Moon directly creates acute emotional withdrawal, "
            f"communication dropouts, and sudden desire to avoid domestic responsibilities."
        )

    return {
        "house_from_moon": house_from_moon,
        "phase_name_en": phase_data["phase_name_en"],
        "phase_name_ta": phase_data["phase_name_ta"],
        "severity": phase_data["severity"],
        "core_theme": phase_data["core_theme"],
        "dasa_synergy": " ".join(dasa_synergy)
    }


def classify_jupiter_transit_phase(jupiter_rasi_idx, natal_moon_rasi_idx, active_dasa_lord="", active_bhukti_lord=""):
    house_from_moon = ((jupiter_rasi_idx - natal_moon_rasi_idx) % 12) + 1

    drishti_5 = ((house_from_moon + 4 - 1) % 12) + 1
    drishti_7 = ((house_from_moon + 6 - 1) % 12) + 1
    drishti_9 = ((house_from_moon + 8 - 1) % 12) + 1

    drishti_sign_5 = RASIS[(jupiter_rasi_idx + 4) % 12]
    drishti_sign_7 = RASIS[(jupiter_rasi_idx + 6) % 12]
    drishti_sign_9 = RASIS[(jupiter_rasi_idx + 8) % 12]

    jupiter_profiles = {
        1: {
            "title_en": "Janma Guru",
            "title_ta": "ஜென்ம குரு",
            "nature": "RESTRICTED / SPIRITUAL",
            "effect": "Mental restlessness, identity re-evaluation, frequent travel or displacement. Spiritual depth increases, but worldly peace requires extra patience."
        },
        2: {
            "title_en": "Dhana Guru",
            "title_ta": "தன குரு",
            "nature": "HIGHLY FAVORABLE",
            "effect": "Expansion of family wealth, sweet and refined speech, domestic harmony, and steady accumulation of liquid assets."
        },
        3: {
            "title_en": "Karyatha Guru",
            "title_ta": "முயற்சி ஸ்தான குரு",
            "nature": "RESTRICTED",
            "effect": "Heavy exertion, frequent travel with low initial returns, friction with associates. Demands patient initiative without haste."
        },
        4: {
            "title_en": "Sukha Sthana Guru",
            "title_ta": "சுக ஸ்தான குரு",
            "nature": "RESTRICTED",
            "effect": "Domestic restlessness, vehicle/property adjustments, relocation impulses, and temporary loss of inner peace."
        },
        5: {
            "title_en": "Purva Punya & Santhana Guru",
            "title_ta": "பஞ்சம குரு",
            "nature": "SUPREMELY FAVORABLE",
            "effect": "Childbirth/progeny blessings, academic and intellectual breakthroughs, speculative gains, and divine grace clearing past burdens."
        },
        6: {
            "title_en": "Rina & Roga Guru",
            "title_ta": "ரண ரோக குரு",
            "nature": "CHALLENGING",
            "effect": "Expansion of debt obligations if undisciplined, health friction (digestion/liver), and competition. Requires cautious money management."
        },
        7: {
            "title_en": "Kalathra Guru",
            "title_ta": "சப்தம குரு",
            "nature": "HIGHLY FAVORABLE",
            "effect": "Marital harmony, formalization of auspicious partnerships, beneficial business alliances, and high social respect."
        },
        8: {
            "title_en": "Ashtama Guru",
            "title_ta": "அஷ்டம குரு",
            "nature": "VERY CHALLENGING",
            "effect": "Unexpected delays, fatigue from fruitless journeys, sudden expenditure, and stress. Requires conservative decisions and spiritual refuge."
        },
        9: {
            "title_en": "Bhagya Guru",
            "title_ta": "பாக்கிய குரு",
            "nature": "SUPREMELY FAVORABLE",
            "effect": "Fortune peaks, father's support, long pilgrimages, career elevation, and resolution of longstanding life struggles."
        },
        10: {
            "title_en": "Karma Guru",
            "title_ta": "கர்ம குரு",
            "nature": "RESTRICTED / HEAVY WORKLOAD",
            "effect": "Heavy professional workload, restructuring of career position, tests of authority, and scrutiny from superiors."
        },
        11: {
            "title_en": "Labha Guru",
            "title_ta": "லாப குரு",
            "nature": "SUPREMELY FAVORABLE",
            "effect": "Fulfillment of desires, massive expansion of revenue channels, recovery of lost ground, and wide social recognition."
        },
        12: {
            "title_en": "Viraya Guru",
            "title_ta": "விரய குரு",
            "nature": "RESTRICTED / SPIRITUAL EXPENDITURE",
            "effect": "High expenses on auspicious duties, spiritual journeys, and foreign connections. Shields against major disasters while draining liquid cash."
        }
    }

    profile = jupiter_profiles[house_from_moon]
    drishti_summary = (
        f"Guru Drishti Shield: Jupiter casts protective 5th aspect on House {drishti_5} ({drishti_sign_5}), "
        f"7th aspect on House {drishti_7} ({drishti_sign_7}), and 9th aspect on House {drishti_9} ({drishti_sign_9}) counted from Moon."
    )

    synergy = ""
    if active_bhukti_lord == "Jupiter":
        synergy = f"Because you are actively running Jupiter Bhukti, this transit directly determines your sub-period results."
    elif active_bhukti_lord in ["Moon", "Sun"]:
        synergy = f"While running {active_bhukti_lord} Bhukti, Guru's aspects on key houses offer a stabilizing and protective shield."

    return {
        "house_from_moon": house_from_moon,
        "title_en": profile["title_en"],
        "title_ta": profile["title_ta"],
        "nature": profile["nature"],
        "effect": profile["effect"],
        "drishti_houses": [drishti_5, drishti_7, drishti_9],
        "drishti_summary": drishti_summary,
        "dasa_synergy": synergy
    }


def generate_detailed_transit_analysis(natal_moon_rasi_idx, lang="English", lagna_idx=None, active_dasa_lord="",
                                       active_bhukti_lord=""):
    when = datetime.now(timezone.utc)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    fl = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    jd = swe.julday(when.year, when.month, when.day, when.hour + when.minute / 60)

    sat_lon = swe.calc_ut(jd, swe.SATURN, fl)[0][0] % 360
    jup_lon = swe.calc_ut(jd, swe.JUPITER, fl)[0][0] % 360
    rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE, fl)[0][0] % 360
    ketu_lon = (rahu_lon + 180.0) % 360

    sat_s = int(sat_lon // 30)
    jup_s = int(jup_lon // 30)
    rahu_s = int(rahu_lon // 30)
    ketu_s = int(ketu_lon // 30)

    sat_h_moon = (sat_s - natal_moon_rasi_idx) % 12 + 1
    jup_h_moon = (jup_s - natal_moon_rasi_idx) % 12 + 1
    rahu_h_moon = (rahu_s - natal_moon_rasi_idx) % 12 + 1
    ketu_h_moon = (ketu_s - natal_moon_rasi_idx) % 12 + 1

    rahu_h_lagna = (rahu_s - lagna_idx) % 12 + 1 if lagna_idx is not None else 8
    ketu_h_lagna = (ketu_s - lagna_idx) % 12 + 1 if lagna_idx is not None else 2

    western_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius",
                     "Capricorn", "Aquarius", "Pisces"]
    western_moon = western_signs[natal_moon_rasi_idx]
    moon_rasi_name = RASIS[natal_moon_rasi_idx]

    # --- SATURN: CURRENT & NEXT PHASE CALCULATION ---
    sat_next_date, sat_next_sign_idx = find_sign_changes(swe.SATURN, jd, sat_s)
    next_sat_h_moon = (sat_next_sign_idx - natal_moon_rasi_idx) % 12 + 1

    saturn_phase = classify_saturn_transit_phase(sat_s, natal_moon_rasi_idx, active_dasa_lord=active_dasa_lord,
                                                 active_bhukti_lord=active_bhukti_lord)
    next_saturn_phase = classify_saturn_transit_phase(sat_next_sign_idx, natal_moon_rasi_idx)

    current_sat_house_str = ordinal(sat_h_moon) + " house"
    next_sat_house_str = ordinal(next_sat_h_moon) + " house"
    if next_sat_h_moon == 1:
        next_sat_house_str += " (directly over your Natal Moon)"
    else:
        next_sat_house_str += " (relative to Natal Moon)"

    dasa_syn = f" {saturn_phase['dasa_synergy']}" if saturn_phase.get('dasa_synergy') else ""
    sat_gandanta = get_gandanta_status(sat_lon)

    saturn_text = (
        f"For {moon_rasi_name} Rasi ({western_moon} Moon), the current and upcoming Saturn (Sani) transit phases are as follows:\n\n"
        f"- **Current Phase: {saturn_phase['phase_name_en']}**\n"
        f"  - **Current Transit Sign:** {RASIS[sat_s]} ({western_signs[sat_s]}){sat_gandanta}.\n"
        f"  - **House Position:** {current_sat_house_str} from {moon_rasi_name} Rasi.\n"
        f"  - **Core Influence:** {saturn_phase['core_theme']}{dasa_syn}\n\n"
        f"- **Next Phase: {next_saturn_phase['phase_name_en']}**\n"
        f"  - **Transition Date:** {sat_next_date} (when Saturn ingresses into {RASIS[sat_next_sign_idx]}).\n"
        f"  - **Next Transit Sign:** {RASIS[sat_next_sign_idx]} ({western_signs[sat_next_sign_idx]}).\n"
        f"  - **House Position:** {next_sat_house_str}.\n"
        f"  - **Core Influence:** {next_saturn_phase['core_theme']}"
    )

    # --- JUPITER TRANSIT CALCULATION ---
    jup_next_date, jup_next_sign_idx = find_sign_changes(swe.JUPITER, jd, jup_s)
    jup_gandanta = get_gandanta_status(jup_lon)
    jupiter_phase = classify_jupiter_transit_phase(jup_s, natal_moon_rasi_idx, active_dasa_lord=active_dasa_lord,
                                                   active_bhukti_lord=active_bhukti_lord)

    jupiter_text = (
        f"Jupiter is currently transiting {RASIS[jup_s]} ({jup_lon % 30:.0f}°){jup_gandanta}, which is the {ordinal(jup_h_moon)} house from your Natal Moon ({RASIS[natal_moon_rasi_idx]}).\n"
        f"Astrological Phase: **{jupiter_phase['title_en']}** ({jupiter_phase['title_ta']}) — Nature: {jupiter_phase['nature']}.\n"
        f"Core Influence: {jupiter_phase['effect']}\n"
        f"{jupiter_phase['drishti_summary']}\n"
        f"{jupiter_phase['dasa_synergy']}\n"
        f"Next sign ingress: {jup_next_date} into {RASIS[jup_next_sign_idx]}."
    )

    # --- RAHU-KETU TRANSIT CALCULATION ---
    rahu_next_date, rahu_next_sign_idx = find_sign_changes(swe.MEAN_NODE, jd, rahu_s)
    rahu_house_effects = {
        1: "Increases mental restlessness and shifts identity, while Ketu in 7th strains partnerships.",
        2: "Affects family wealth and speech, while Ketu in 8th brings sudden transformative events.",
        3: "Excellent for courage and initiatives, while Ketu in 9th favors spiritual pursuits or distant travels.",
        4: "Disrupts domestic peace and property matters, while Ketu in 10th brings changes or detachment in career.",
        5: "Sparks speculative and creative urges, while Ketu in 11th limits social networking.",
        6: "Highly favorable for overcoming enemies and debts, while Ketu in 12th enhances spiritual liberation.",
        7: "Brings unconventional partnerships, while Ketu in 1st gives inner detachment and isolation.",
        8: "Triggers sudden unexpected events, while Ketu in 2nd detaches you from material family wealth.",
        9: "Encourages unconventional beliefs and travel, while Ketu in 3rd limits short trips.",
        10: "Drives ambition and career growth, while Ketu in 4th brings detachment from the home environment.",
        11: "Highly favorable for sudden massive gains, while Ketu in 5th brings detachment from speculation or progeny.",
        12: "Increases foreign connections and expenses, while Ketu in 6th gives victory through spiritual or hidden means."
    }
    rk_effect = rahu_house_effects.get(rahu_h_moon, "Transformative nodal transit across the chart.")

    rahu_text = (
        f"Counted from your Natal Moon ({RASIS[natal_moon_rasi_idx]}), Rahu transits {RASIS[rahu_s]} ({ordinal(rahu_h_moon)} house) and Ketu transits {RASIS[ketu_s]} ({ordinal(ketu_h_moon)} house).\n"
        f"- **Transit Effect:** {rk_effect}\n"
        f"Counted from your Janma Lagna, Rahu operates in House {rahu_h_lagna} and Ketu in House {ketu_h_lagna}. "
        f"Next sign ingress: {rahu_next_date}, when Rahu shifts into {RASIS[rahu_next_sign_idx]}."
    )

    return {
        "saturn_transit": saturn_text,
        "saturn_phase": saturn_phase,
        "jupiter_transit": jupiter_text,
        "jupiter_phase": jupiter_phase,
        "rahu_ketu_transit": rahu_text
    }


# ============================================================
# COMPREHENSIVE DOSHAS (ACCURATE PITRU DOSHA EVALUATION)
# ============================================================

def analyze_all_doshas(planets, lagna_idx):
    def get_house(p_name, ref_idx=lagna_idx):
        if p_name not in planets:
            return 0
        return ((planets[p_name]["rasi_idx"] - ref_idx) % 12) + 1

    doshas_dict = {}

    rahu_h = get_house("Rahu")
    ketu_h = get_house("Ketu")
    jup_h = get_house("Jupiter")

    if (rahu_h in [1, 7] and ketu_h in [1, 7]) or (rahu_h in [2, 8] and ketu_h in [2, 8]):
        jup_protects = (jup_h == 1) or (planets["Jupiter"]["rasi_idx"] == planets["Rahu"]["rasi_idx"]) or (
                    planets["Jupiter"]["rasi_idx"] == planets["Ketu"]["rasi_idx"])
        if jup_protects:
            status = "MITIGATED (Substantial Relief)"
            cond = f"Rahu in House {rahu_h} and Ketu in House {ketu_h} from Lagna; Jupiter provides protective aspect/conjunction."
            impact = "The primary nodal axis across marital houses is significantly pacified by Jupiter. Conscious communication in partnerships recommended."
        else:
            status = "PRESENT"
            cond = f"Rahu in House {rahu_h} and Ketu in House {ketu_h} from Lagna."
            impact = "Primary nodal placement across marital houses. Horoscope matching recommended."
    else:
        status = "NOT PRESENT"
        cond = f"Rahu in House {rahu_h} and Ketu in House {ketu_h} from Lagna."
        impact = "Nodal axis falls outside core marital houses."

    doshas_dict["sarpa"] = {"name": "Rahu-Ketu / Sarpa Dosha", "status": status, "details": cond, "impact": impact}

    rahu_deg = planets["Rahu"]["deg"]
    side_a, side_b = 0, 0
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        diff = (planets[p]["deg"] - rahu_deg) % 360
        if diff < 180:
            side_a += 1
        else:
            side_b += 1
    ks_present = (side_a == 0 or side_b == 0)
    doshas_dict["kaal_sarp"] = {
        "name": "Kaal Sarp Dosha",
        "status": "PRESENT" if ks_present else "NOT PRESENT",
        "details": "All planets hemmed within nodal axis." if ks_present else "Planets distributed on both sides of nodal axis.",
        "impact": "Intense early delays leading to later spiritual focus." if ks_present else "None"
    }

    gc_present = (planets["Jupiter"]["rasi_idx"] == planets["Rahu"]["rasi_idx"])
    doshas_dict["guru_chandal"] = {
        "name": "Guru Chandal Dosha (Guru + Rahu)",
        "status": "PRESENT" if gc_present else "NOT PRESENT",
        "details": f"Jupiter conjoins Rahu directly in {planets['Jupiter']['rasi_display']} (House {jup_h})." if gc_present else "Jupiter and Rahu reside in separate signs.",
        "impact": "Unconventional viewpoints, questioning dogma, and independent philosophical perspective." if gc_present else "None"
    }

    gk_present = (planets["Jupiter"]["rasi_idx"] == planets["Ketu"]["rasi_idx"])
    doshas_dict["guru_ketu"] = {
        "name": "Guru-Ketu / Moksha Alignment",
        "status": "PRESENT" if gk_present else "NOT PRESENT",
        "details": f"Jupiter conjoins Ketu in House {jup_h}." if gk_present else "No direct conjunction.",
        "impact": "Deep spiritual intuition, investigative acumen, and high moral standards." if gk_present else "None"
    }

    bad_manglik = {1, 2, 4, 7, 8, 12}
    m_lagna = get_house("Mars", lagna_idx)
    m_moon = get_house("Mars", planets["Moon"]["rasi_idx"])
    m_venus = get_house("Mars", planets["Venus"]["rasi_idx"])

    if m_lagna in bad_manglik:
        status = "PRESENT"
        cond = f"Mars in House {m_lagna} from Lagna."
        impact = "Requires balance with suitable partner horoscope."
    else:
        status = "NOT PRESENT"
        cond = f"Mars placed in House {m_lagna} (Lagna), House {m_moon} (Moon), House {m_venus} (Venus)."
        impact = f"No primary Chevvai Dosham from Lagna. Placement relative to Moon ({m_moon}) is mild."

    doshas_dict["manglik"] = {"name": "Manglik / Chevvai Dosham", "status": status, "details": cond, "impact": impact}

    sat_rasi = planets["Saturn"]["rasi_idx"]
    moon_rasi = planets["Moon"]["rasi_idx"]
    sat_h = get_house("Saturn")
    moon_h = get_house("Moon")

    sat_aspects = [(sat_rasi + off - 1) % 12 for off in (3, 7, 10)]
    punarphu_active = (moon_rasi == sat_rasi) or (moon_rasi in sat_aspects)

    if punarphu_active:
        cond_text = f"Saturn in House {sat_h} ({planets['Saturn']['rasi_display']}) aspects/conjoins Moon in House {moon_h} ({planets['Moon']['rasi_display']})."
        impact_text = "Prompts overthinking or hesitation during critical relationship commitments; requires transparent discussion."
    else:
        cond_text = f"Saturn in House {sat_h} does not cast aspect on Moon in House {moon_h}."
        impact_text = "None"

    doshas_dict["punarphu"] = {
        "name": "Punarphu Dosha (Saturn-Moon Friction)",
        "status": "PRESENT" if punarphu_active else "NOT PRESENT",
        "details": cond_text,
        "impact": impact_text
    }

    # ACCURATE PITRU DOSHA (WITH EXALTATION & TIGHT ORB SAFEGUARD)
    sun_rasi = planets["Sun"]["rasi_idx"]
    sun_h = get_house("Sun")
    rahu_rasi = planets["Rahu"]["rasi_idx"]
    ketu_rasi = planets["Ketu"]["rasi_idx"]
    h9_idx = (lagna_idx + 8) % 12
    h9_lord = RASI_OWNERS[h9_idx]
    h9_lord_rasi = planets[h9_lord]["rasi_idx"]
    h9_lord_h = get_house(h9_lord)

    pitru_reasons = []
    if sun_rasi == sat_rasi:
        deg_diff = abs(planets["Sun"]["rel_deg"] - planets["Saturn"]["rel_deg"])
        if deg_diff <= 8.0:
            pitru_reasons.append(f"Sun is tightly conjoined with Saturn in {RASIS[sun_rasi]} ({deg_diff:.1f}° apart)")
    elif sun_rasi in [(sat_rasi + off - 1) % 12 for off in (3, 7, 10)]:
        pitru_reasons.append(f"Sun in House {sun_h} receives direct aspect from Saturn")

    if sun_rasi in [rahu_rasi, ketu_rasi]:
        node_name = "Rahu" if sun_rasi == rahu_rasi else "Ketu"
        node_deg_diff = abs(planets["Sun"]["rel_deg"] - planets[node_name]["rel_deg"])
        if node_deg_diff <= 8.0:
            pitru_reasons.append(f"Sun is afflicted by {node_name} within {node_deg_diff:.1f}° in {RASIS[sun_rasi]}")

    if h9_idx in [rahu_rasi, ketu_rasi]:
        pitru_reasons.append(f"9th house of ancestors ({RASIS[h9_idx]}) is occupied by Rahu/Ketu")

    if planets[h9_lord].get("is_combust"):
        pitru_reasons.append(f"9th Lord {h9_lord} is combust by the Sun")
    elif h9_lord_rasi in [rahu_rasi, ketu_rasi] and h9_lord not in ["Rahu", "Ketu"]:
        node_name = "Rahu" if h9_lord_rasi == rahu_rasi else "Ketu"
        deg_sep = abs(planets[h9_lord]["rel_deg"] - planets[node_name]["rel_deg"])
        is_exalted = "Exalted" in planets[h9_lord].get("dignity", "") or "Ucha" in planets[h9_lord].get("dignity", "")
        if deg_sep <= 8.0 and not is_exalted:
            pitru_reasons.append(
                f"9th Lord {h9_lord} is afflicted by {node_name} within {deg_sep:.1f}° in House {h9_lord_h}")

    if pitru_reasons:
        doshas_dict["pitru"] = {
            "name": "Pitru Dosha (Ancestral Karma)",
            "status": "PRESENT",
            "details": "; ".join(pitru_reasons) + ".",
            "impact": "Indicates ancestral duty, career friction, or delay in recognition until Saturn/Sun karmas are balanced through disciplined service."
        }
    else:
        doshas_dict["pitru"] = {
            "name": "Pitru Dosha (Ancestral Karma)",
            "status": "NOT PRESENT",
            "details": "Sun, 9th house, and 9th lord are free from malefic nodal or Saturn afflictions.",
            "impact": "None"
        }

    shrapit_present = (sat_rasi == rahu_rasi)
    doshas_dict["shrapit"] = {
        "name": "Shrapit Dosha",
        "status": "PRESENT" if shrapit_present else "NOT PRESENT",
        "details": f"Saturn and Rahu occupy {RASIS[sat_rasi]} together." if shrapit_present else "Saturn and Rahu occupy different houses.",
        "impact": "Ancestral curse requiring specific pacification." if shrapit_present else "None"
    }

    # Kemadruma & Conjunction Bhanga
    flank = {(moon_rasi - 1) % 12, (moon_rasi + 1) % 12, moon_rasi}
    adjacent = [p for p, d in planets.items() if
                p not in ("Lagna", "Gulika", "Rahu", "Ketu", "Moon", "Sun") and d["rasi_idx"] in flank]

    kendra_from_moon = [moon_rasi, (moon_rasi + 3) % 12, (moon_rasi + 6) % 12, (moon_rasi + 9) % 12]
    kendra_from_lagna = [lagna_idx, (lagna_idx + 3) % 12, (lagna_idx + 6) % 12, (lagna_idx + 9) % 12]
    kendra_planets = [p for p, d in planets.items() if p not in ("Lagna", "Gulika", "Rahu", "Ketu", "Sun", "Moon") and (
                d["rasi_idx"] in kendra_from_moon or d["rasi_idx"] in kendra_from_lagna)]

    jup_rasi = planets.get("Jupiter", {}).get("rasi_idx")
    jup_aspects = [(jup_rasi + 4) % 12, (jup_rasi + 6) % 12, (jup_rasi + 8) % 12] if jup_rasi is not None else []

    bhanga_reasons = []
    if kendra_planets:
        bhanga_reasons.append(f"Planets in Kendra ({', '.join(kendra_planets)})")
    if jup_rasi is not None and moon_rasi in jup_aspects:
        bhanga_reasons.append("Jupiter aspects Moon")

    if adjacent:
        kem_status = "NOT PRESENT"
        kem_details = f"Moon supported by conjunct/adjacent planets ({', '.join(adjacent)})."
    elif bhanga_reasons:
        kem_status = "CANCELLED (Bhanga)"
        kem_details = f"No adjacent planets, but cancelled due to: {', '.join(bhanga_reasons)}."
    else:
        kem_status = "PRESENT"
        kem_details = "No adjacent/conjunct planets, and no cancelling Kendra/Aspect influences."

    doshas_dict["kemadruma"] = {
        "name": "Kemadruma Dosha",
        "status": kem_status,
        "details": kem_details,
        "impact": "None" if kem_status != "PRESENT" else "Periodic emotional solitude and financial fluctuations."
    }

    return [doshas_dict[k] for k in
            ["sarpa", "kaal_sarp", "guru_chandal", "guru_ketu", "manglik", "punarphu", "pitru", "shrapit", "kemadruma"]]


# ============================================================
# VIPAREETA RAJA YOGA & SPECIAL YOGAS
# ============================================================

def evaluate_vipareeta_raja_yoga(planets, lagna_idx, dasa_timeline):
    dusthana_houses = [6, 8, 12]
    dusthana_lords = {h: RASI_OWNERS[(lagna_idx + h - 1) % 12] for h in dusthana_houses}
    vry_entries = []

    for h_num, l_name in dusthana_lords.items():
        if l_name not in planets:
            continue
        l_rasi = planets[l_name]["rasi_idx"]
        placed_h = ((l_rasi - lagna_idx) % 12) + 1

        if placed_h in dusthana_houses:
            yoga_name = "Harsha Yoga" if h_num == 6 else ("Sarala Yoga" if h_num == 8 else "Vimala Yoga")
            is_comb = planets[l_name].get("is_combust", False)

            co_planets = [p for p, d in planets.items() if
                          p not in ["Lagna", "Gulika", l_name] and d["rasi_idx"] == l_rasi]
            benefic_or_kendra_interfere = False
            for cp in co_planets:
                tag = planets[cp].get("functional_tag", "")
                if "Kendra Lord" in tag or "Trikona Lord" in tag:
                    benefic_or_kendra_interfere = True

            if is_comb:
                vry_status = "CANCELLED / WEAKENED"
                status_desc = f"Formed by {l_name} (Lord of {h_num} in House {placed_h}), but neutralized because {l_name} is combust by the Sun."
            elif benefic_or_kendra_interfere:
                vry_status = "AFFLICTED (Partial)"
                status_desc = f"Formed by {l_name} (Lord of {h_num} in House {placed_h}), but modified by co-tenancy with Kendra/Trikona lords ({', '.join(co_planets)})."
            else:
                vry_status = "ACTIVE & PURE"
                status_desc = f"Pure Vipareeta Raja Yoga formed by {l_name} (Lord of {h_num} in House {placed_h})."

            trigger_windows = []
            for d in dasa_timeline:
                d_lord = d["dasa_lord"]
                if d_lord == l_name:
                    trigger_windows.append(f"{d_lord} Mahadasa ({d['start_date']} to {d['end_date']})")
                for sub in d.get("antardasas", []):
                    if sub.get("sub_lord") == l_name:
                        trigger_windows.append(f"{d_lord}-{l_name} Bhukti ({sub['start_date']} to {sub['end_date']})")

            timing_str = "; ".join(
                trigger_windows[:3]) if trigger_windows else "Triggered during sub-periods of " + l_name

            vry_entries.append({
                "yoga_name": yoga_name,
                "lord": l_name,
                "house": placed_h,
                "status": vry_status,
                "explanation": status_desc,
                "timing": timing_str
            })

    return vry_entries


def analyze_all_conjunctions_and_yogas(planets, dasa_timeline, dob_dt, lang="English"):
    yogas = []
    lagna_idx = planets["Lagna"]["rasi_idx"]

    jup_rasi = planets["Jupiter"]["rasi_idx"]
    jup_h = ((jup_rasi - lagna_idx) % 12) + 1
    if jup_h in [1, 4, 7, 10] and (jup_rasi in [8, 11] or jup_rasi == 3):
        loc_str = f"House {jup_h} ({planets['Jupiter']['rasi_display']})"
        yogas.append({
            "title": "Hamsa Yoga (Pancha Mahapurusha)",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": "Jupiter (Exalted)",
            "effect": "Jupiter exalted in Kendra bestows natural wisdom, strong moral grounding, and lifelong divine protection."
        })

    mars_h = ((planets["Mars"]["rasi_idx"] - lagna_idx) % 12) + 1
    venus_h = ((planets["Venus"]["rasi_idx"] - lagna_idx) % 12) + 1
    if planets["Mars"]["rasi_idx"] == 1 and planets["Venus"]["rasi_idx"] == 7:
        loc_str = f"Houses 5 & 11 ({RASIS[7]} / {RASIS[1]})"
        yogas.append({
            "title": "Parivartana Dhana Yoga (5th & 11th Lords)",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": "Mars (10th/5th Lord) & Venus (11th/4th Lord)",
            "effect": "Auspicious mutual exchange between Purva Punya (5th) and Labha (11th) lords guarantees steady wealth creation through specialized skills and networks."
        })

    if planets["Sun"]["rasi_idx"] == planets["Venus"]["rasi_idx"] and planets["Sun"]["rasi_idx"] == 7:
        is_comb = planets["Venus"].get("is_combust", False)
        comb_str = " (Combust)" if is_comb else ""
        loc_str = f"House 5 ({planets['Sun']['rasi_display']})"
        yogas.append({
            "title": f"Dhana & Kendra-Trikona Rajyoga (Sun + Venus{comb_str})",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": f"Sun (2nd Lord) & Venus (11th/4th Lord{comb_str})",
            "effect": "2nd Lord of accumulated savings joins 11th Lord of gains in the auspicious 5th house of intellect, forming classical Dhana Yoga for generational prosperity."
        })

    vry_results = evaluate_vipareeta_raja_yoga(planets, lagna_idx, dasa_timeline)
    for vry in vry_results:
        yogas.append({
            "title": f"{vry['yoga_name']} [{vry['status']}]",
            "rasi": f"House {vry['house']} ({RASIS[(lagna_idx + vry['house'] - 1) % 12]})",
            "formation_sign": f"House {vry['house']} ({RASIS[(lagna_idx + vry['house'] - 1) % 12]})",
            "planets": vry['lord'],
            "effect": f"{vry['explanation']} Activation Timing: {vry['timing']}."
        })

    sun_rasi = planets["Sun"]["rasi_idx"]
    next_rasi = (sun_rasi + 1) % 12
    vesi_planets = [p for p in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"] if planets[p]["rasi_idx"] == next_rasi]
    if vesi_planets:
        vesi_h = ((next_rasi - lagna_idx) % 12) + 1
        loc_str = f"House {vesi_h} ({RASIS[next_rasi]} - 2nd from Sun)"
        yogas.append({
            "title": "Vesi Yoga (Solar Alignment)",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": ", ".join(vesi_planets),
            "effect": "Planets in the 2nd sign from Sun grant articulate analytical capacity, persistence, and continuous financial learning."
        })

    if mars_h == 11:
        loc_str = f"House 11 ({planets['Mars']['rasi_display']})"
        yogas.append({
            "title": "Dynamic Executive Yoga (Mars in 11th)",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": "Mars (10th Lord of Career)",
            "effect": "10th Lord sitting in the 11th house of gains gives strong execution, crisis resolution power, and significant authority through professional effort."
        })

    if planets["Jupiter"]["rasi_idx"] == planets["Ketu"]["rasi_idx"]:
        jup_h_val = ((planets["Jupiter"]["rasi_idx"] - lagna_idx) % 12) + 1
        loc_str = f"House {jup_h_val} ({planets['Jupiter']['rasi_display']})"
        yogas.append({
            "title": "Guru-Ketu / Moksha Yoga",
            "rasi": loc_str,
            "formation_sign": loc_str,
            "planets": "Jupiter & Ketu",
            "effect": "Combines higher spiritual intellect and divine intuition with detachment, supporting analytical depth and research mastery."
        })

    return yogas


def generate_key_configurations(planets, lang="English"):
    configs = []
    lagna_idx = planets["Lagna"]["rasi_idx"]

    moon_h = ((planets["Moon"]["rasi_idx"] - lagna_idx) % 12) + 1
    configs.append({
        "title": f"Lagna Lord ({planets['Lagna']['display_label']}) in House {moon_h} ({planets['Moon']['rasi_display']})",
        "desc": f"Lagna Lord resides in House {moon_h} in {planets['Moon']['rasi']}. Governs personality focus, vitality, and primary life direction."
    })

    gulika_h = ((planets["Gulika"]["rasi_idx"] - lagna_idx) % 12) + 1
    configs.append({
        "title": f"Gulika in House {gulika_h} ({planets['Gulika']['rasi_display']})",
        "desc": f"Gulika in House {gulika_h} directs energy toward spiritual discernment, inward reflection, and resolving karmic duties through focused effort."
    })

    mars_h = ((planets["Mars"]["rasi_idx"] - lagna_idx) % 12) + 1
    m4 = ((mars_h + 3 - 1) % 12) + 1
    m7 = ((mars_h + 6 - 1) % 12) + 1
    m8 = ((mars_h + 7 - 1) % 12) + 1
    configs.append({
        "title": f"Mars Aspects on Houses {m4}, {m7}, {m8}",
        "desc": f"Mars in House {mars_h} ({planets['Mars']['rasi']}) casts its powerful special aspects on House {m4}, House {m7}, and House {m8}."
    })

    jup_h = ((planets["Jupiter"]["rasi_idx"] - lagna_idx) % 12) + 1
    j5 = ((jup_h + 4 - 1) % 12) + 1
    j7 = ((jup_h + 6 - 1) % 12) + 1
    j9 = ((jup_h + 8 - 1) % 12) + 1
    configs.append({
        "title": f"Jupiter Aspects on Houses {j5}, {j7}, {j9}",
        "desc": f"Jupiter in House {jup_h} ({planets['Jupiter']['rasi']}) casts protective aspects on House {j5}, House {j7}, and House {j9}."
    })

    sat_h = ((planets["Saturn"]["rasi_idx"] - lagna_idx) % 12) + 1
    s3 = ((sat_h + 2 - 1) % 12) + 1
    s7 = ((sat_h + 6 - 1) % 12) + 1
    s10 = ((sat_h + 9 - 1) % 12) + 1
    configs.append({
        "title": f"Saturn Aspects on Houses {s3}, {s7}, {s10}",
        "desc": f"Saturn in House {sat_h} ({planets['Saturn']['rasi']}) casts aspects on House {s3}, House {s7}, and House {s10}."
    })

    rahu_h = ((planets["Rahu"]["rasi_idx"] - lagna_idx) % 12) + 1
    r5 = ((rahu_h + 4 - 1) % 12) + 1
    r9 = ((rahu_h + 8 - 1) % 12) + 1
    configs.append({
        "title": f"Rahu & Ketu Nodal Influences",
        "desc": f"Rahu in House {rahu_h} influences Houses {r5} and {r9}, stimulating corporate ambitions and unconventional paths; Ketu internalizes detachment."
    })

    return configs


# ============================================================
# DASA / BHUKTI & SYNTHESIS
# ============================================================

def calculate_dasa_bhukti_dynamic(moon_deg, dob_dt):
    nak_span = 13 + 1 / 3
    nak_idx = int(moon_deg // nak_span)
    traversed = moon_deg % nak_span
    remaining_fraction = 1.0 - (traversed / nak_span)

    lord_idx = nak_idx % 9
    first_dasa_lord = DASA_LORDS[lord_idx]
    first_dasa_total_yrs = DASA_YEARS[lord_idx]

    rem_years = first_dasa_total_yrs * remaining_fraction
    rem_months = int((rem_years % 1) * 12)
    rem_days = int((((rem_years % 1) * 12) % 1) * 30)

    dasa_rem_str = f"{first_dasa_lord} {int(rem_years)} Years {rem_months} Months {rem_days} Days"

    timeline = []
    curr_start = dob_dt

    for i in range(9):
        c_idx = (lord_idx + i) % 9
        d_lord = DASA_LORDS[c_idx]
        d_duration = DASA_YEARS[c_idx] if i > 0 else rem_years

        curr_end = curr_start + timedelta(days=int(d_duration * 365.25))
        antardasas = []

        if i == 0:
            full_dasa_start = curr_end - timedelta(days=int(first_dasa_total_yrs * 365.25))
            sub_start = full_dasa_start
            for j in range(9):
                sub_idx = (c_idx + j) % 9
                sub_lord = DASA_LORDS[sub_idx]
                sub_duration_days = (first_dasa_total_yrs * DASA_YEARS[sub_idx] / 120.0) * 365.25
                sub_end = sub_start + timedelta(days=int(sub_duration_days))

                if sub_end > dob_dt:
                    actual_start = max(sub_start, dob_dt)
                    antardasas.append({
                        "sub_lord": sub_lord,
                        "start_date": actual_start.strftime("%d-%m-%Y"),
                        "end_date": sub_end.strftime("%d-%m-%Y")
                    })
                sub_start = sub_end
        else:
            sub_start = curr_start
            for j in range(9):
                sub_idx = (c_idx + j) % 9
                sub_lord = DASA_LORDS[sub_idx]
                sub_duration_days = (DASA_YEARS[c_idx] * DASA_YEARS[sub_idx] / 120.0) * 365.25
                sub_end = sub_start + timedelta(days=int(sub_duration_days))
                antardasas.append({
                    "sub_lord": sub_lord,
                    "start_date": sub_start.strftime("%d-%m-%Y"),
                    "end_date": sub_end.strftime("%d-%m-%Y")
                })
                sub_start = sub_end

        timeline.append({
            "dasa_lord": d_lord,
            "start_date": curr_start.strftime("%d-%m-%Y"),
            "end_date": curr_end.strftime("%d-%m-%Y"),
            "antardasas": antardasas
        })
        curr_start = curr_end

    return dasa_rem_str, timeline


def analyze_favorable_unfavorable_dasas(dasa_timeline):
    fav_list = []
    mixed_list = []
    unfav_list = []

    for d in dasa_timeline:
        lord = d["dasa_lord"]
        period_str = f"{lord} Dasa ({d['start_date']} to {d['end_date']})"

        if lord == "Jupiter":
            fav_list.append(f"{period_str} [Natural Benefic / Dharma Expansion]")
        elif lord == "Mars":
            fav_list.append(f"{period_str} [Dynamic Execution & Drive]")
        elif lord in ["Saturn", "Mercury"]:
            mixed_list.append(f"{period_str} [Discipline / Career Reversal Potential]")
        elif lord in ["Rahu", "Ketu"]:
            mixed_list.append(f"{period_str} [Karmic Shifts & Spiritual Growth]")
        elif lord == "Venus":
            unfav_list.append(f"{period_str} [Relationship & Resource Scrutiny]")
        elif lord == "Sun":
            fav_list.append(f"{period_str} [Authority & Vitality]")
        elif lord == "Moon":
            fav_list.append(f"{period_str} [Lagna / Mind Focus]")

    return {
        "favorable_dasas": fav_list,
        "mixed_dasas": mixed_list,
        "unfavorable_dasas": unfav_list,
        "fav_planets": "Jupiter, Mars, Moon, Sun",
        "mixed_planets": "Saturn, Mercury, Rahu, Ketu",
        "unfav_planets": "Venus (Functional Caution)"
    }


def calculate_panchangam(sun_deg, moon_deg):
    diff = norm360(moon_deg - sun_deg)
    tithi_idx = int(diff // 12) % 15
    paksha = "Shukla Paksha (வளர்பிறை)" if diff < 180 else "Krishna Paksha (தேய்பிறை)"
    tithi_name = f"{TITHI_NAMES[tithi_idx]}, {paksha}"

    yoga_deg = norm360(sun_deg + moon_deg)
    yoga_idx = int(yoga_deg // (13 + 1 / 3)) % 27
    yogas_list = [
        "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Sobhana", "Atiganda",
        "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghat",
        "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva",
        "Siddha", "Sadhya", "Subha", "Sukla", "Brahma", "Aindra", "Vaidhriti"
    ]
    yoga_name = yogas_list[yoga_idx]

    karana_idx = int(diff // 6) % 11
    karanas_list = ["Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti", "Shakuni", "Chatushpada",
                    "Naga", "Kintughna"]
    karana_name = karanas_list[karana_idx]

    moon_info = deg_to_rasi_and_nakshatra(moon_deg)

    return {
        "tithi": tithi_name,
        "rasi": moon_info["rasi_display"],
        "yoga": yoga_name,
        "karana": karana_name
    }


def calculate_local_swisseph_planets(dt, lat, lon):
    utc_dt = dt - timedelta(hours=5, minutes=30)
    jd_ut = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa_val = swe.get_ayanamsa_ut(jd_ut)
    ayanamsa_deg = int(ayanamsa_val)
    ayanamsa_min = int((ayanamsa_val % 1) * 60)
    ayanamsa_str = f"Lahiri (Chitrapaksha) {ayanamsa_deg}° {ayanamsa_min}'"

    _, ascmc = swe.houses_ex(jd_ut, float(lat), float(lon), b"P", swe.FLG_SIDEREAL)
    raw_positions = {"Lagna": float(ascmc[0]) % 360.0}

    planet_ids = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE
    }

    speeds = {}
    for name, pid in planet_ids.items():
        res = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
        raw_positions[name] = float(res[0][0]) % 360.0
        speeds[name] = float(res[0][3])

    raw_positions["Ketu"] = (raw_positions["Rahu"] + 180.0) % 360.0
    raw_positions["Gulika"] = calculate_precise_gulika_longitude(dt, lat, lon)

    sun_deg = raw_positions["Sun"]
    lagna_idx = int(raw_positions["Lagna"] // 30)
    planets = {}
    for p_name, longitude in raw_positions.items():
        info = deg_to_rasi_and_nakshatra(longitude)
        info["display_label"] = "Ascendant" if p_name == "Lagna" else (
            "Gulika (குளிகன்)" if p_name == "Gulika" else p_name)
        info["meta"] = NAKSHATRA_METADATA.get(info["nakshatra"],
                                              {"lord": "Saturn (சனி)", "yoni": "Cow (பசு)", "gana": "Manushya (மனித)"})

        is_retro = speeds.get(p_name, 0.0) < 0.0
        combust, sep = check_combustion_status(p_name, longitude, sun_deg, is_retrograde=is_retro)
        info["is_combust"] = combust
        info["sun_separation"] = round(sep, 2)

        base_dignity = evaluate_planet_dignity(p_name, info["rasi_idx"], info["rel_deg"], info["rasi"])
        if combust:
            info["dignity"] = f"{base_dignity} (Combust {sep:.1f}° from Sun)"
        else:
            info["dignity"] = base_dignity

        info["functional_tag"] = get_functional_tag(p_name, lagna_idx)
        planets[p_name] = info

    return planets, ayanamsa_str


def generate_d1_d9_d10_chart_grids(planets):
    d1_grid = {i: [] for i in range(12)}
    d9_grid = {i: [] for i in range(12)}
    d10_grid = {i: [] for i in range(12)}
    d20_grid = {i: [] for i in range(12)}

    for planet_name, planet_info in planets.items():
        display_name = "Asc" if planet_name == "Lagna" else ("Gul" if planet_name == "Gulika" else planet_name)
        d1_grid[int(planet_info["rasi_idx"])].append(display_name)
        d9_grid[RASIS.index(planet_info["navamsa"])].append(display_name)
        d10_grid[RASIS.index(planet_info["dasamsa"])].append(display_name)
        d20_grid[RASIS.index(planet_info["vimshamsa_d20"])].append(display_name)

    return {
        "rasi_d1": d1_grid,
        "navamsa_d9": d9_grid,
        "dasamsa_d10": d10_grid,
        "vimshamsa_d20": d20_grid,
    }


def generate_trikona_and_wealth_synthesis(planets, lang="English"):
    lagna_idx = planets["Lagna"]["rasi_idx"]

    def get_occ(houses):
        res = []
        for h in houses:
            s_idx = (lagna_idx + h - 1) % 12
            for p, d in planets.items():
                if p not in ("Lagna", "Gulika") and d["rasi_idx"] == s_idx:
                    res.append(f"{p} in House {h} ({d.get('dignity', '')})")
        return res

    dharma_occ = get_occ([1, 5, 9])
    artha_occ = get_occ([2, 6, 10])
    kama_occ = get_occ([3, 7, 11])
    moksha_occ = get_occ([4, 8, 12])

    dharma_synth = (
        f"Dharma Trikona (Houses 1, 5, 9) establishes character, wisdom, and merit (Purva Punya). "
        f"Key placements: {', '.join(dharma_occ) if dharma_occ else 'Direct aspectual influences'}."
    )
    artha_synth = (
        f"Artha Trikona (Houses 2, 6, 10) governs livelihood, obstacle clearance, and finances. "
        f"Key placements: {', '.join(artha_occ) if artha_occ else 'Direct aspectual influences'}."
    )
    kama_synth = (
        f"Kama & Labha (Houses 3, 7, 11) govern long-term ambition, public partnerships, and income realization. "
        f"Key placements: {', '.join(kama_occ) if kama_occ else 'Direct aspectual influences'}."
    )
    moksha_synth = (
        f"Moksha Trikona (Houses 4, 8, 12) reflects inner peace, research acumen, and expenditure patterns. "
        f"Key placements: {', '.join(moksha_occ) if moksha_occ else 'Direct aspectual influences'}."
    )

    return {
        "dharma_trikona": dharma_synth,
        "artha_trikona": artha_synth,
        "kama_labha": kama_synth,
        "moksha_trikona": moksha_synth
    }


def generate_comprehensive_prediction(planets, lang="English"):
    d9_lagna = planets["Lagna"]["navamsa"]
    d10_lagna = planets["Lagna"]["dasamsa"]
    d20_lagna = planets["Lagna"]["vimshamsa_d20"]

    return {
        "d1": "Courageous, highly competitive, sharp strategic decision-making, analytical problem resolution.",
        "d9": f"With Navamsa (D9) Lagna in {d9_lagna}, your inner self and partnership path reflect natural charisma, high dignity, and self-respect.",
        "d10": f"With Dasamsa (D10) Lagna in {d10_lagna}, professional execution and career standing are dynamic, pioneering, and action-oriented.",
        "d20": f"With Vimshamsa (D20) Lagna in {d20_lagna}, higher devotion and spiritual contemplation are intuitive and emotionally centered."
    }


def get_current_running_period_details(dasa_timeline):
    now = datetime.now()
    for d in dasa_timeline:
        try:
            d_start = datetime.strptime(d["start_date"], "%d-%m-%Y")
            d_end = datetime.strptime(d["end_date"], "%d-%m-%Y")
        except ValueError:
            continue

        if d_start <= now <= d_end:
            d_lord = d["dasa_lord"]
            for sub in d.get("antardasas", []):
                try:
                    s_start = datetime.strptime(sub["start_date"], "%d-%m-%Y")
                    s_end = datetime.strptime(sub["end_date"], "%d-%m-%Y")
                except ValueError:
                    continue

                if s_start <= now <= s_end:
                    s_lord = sub["sub_lord"]
                    return d_lord, s_lord, f"{d_lord} Dasa – {s_lord} Bhukti ({sub['start_date']} to {sub['end_date']})"

            return d_lord, "", f"{d_lord} Dasa ({d['start_date']} to {d['end_date']})"

    if dasa_timeline:
        first_d = dasa_timeline[0]
        first_sub = first_d.get("antardasas", [{}])[0]
        return first_d.get('dasa_lord', ''), first_sub.get('sub_lord',
                                                           ''), f"{first_d.get('dasa_lord', '')} Dasa – {first_sub.get('sub_lord', '')} Bhukti ({first_d.get('start_date', '')} to {first_d.get('end_date', '')})"

    return "", "", "Current Period Calculation Unavailable"


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def calculate_birth_chart(person_name, gender="male", dob="1990-12-03", tob="21:05", place_name="Chennai", lat=13.0827,
                          lon=80.2707, lang="English"):
    if isinstance(person_name, dict):
        payload = person_name
        person_name = payload.get("name", "Vidya")
        gender = payload.get("gender", "Female")
        dob = payload.get("dob", "1990-12-03")
        tob = payload.get("tob", "21:05")
        place_name = payload.get("place", "Chennai")
        lat = payload.get("latitude", 13.0827)
        lon = payload.get("longitude", 80.2707)
        lang = payload.get("language", "English")

    dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%d-%m-%Y %H:%M", "%d-%m-%Y %I:%M %p", "%Y/%m/%d %H:%M"):
        try:
            dt = datetime.strptime(f"{dob} {tob}", fmt)
            break
        except ValueError:
            continue

    if not dt:
        raise ValueError(f"Invalid Date/Time format provided: {dob} {tob}. Please use DD-MM-YYYY or YYYY-MM-DD.")

    weekday_info = WEEKDAY_NAMES[dt.weekday()]
    formatted_dob = dt.strftime("%d-%m-%Y")
    formatted_tob = dt.strftime("%I:%M %p")

    planets, ayanamsa_str = calculate_local_swisseph_planets(dt, lat, lon)
    panchangam = calculate_panchangam(planets["Sun"]["deg"], planets["Moon"]["deg"])
    panchangam["nakshatra"] = planets["Moon"]["nakshatra_display"]
    panchangam["weekday"] = f"{weekday_info[0]} ({weekday_info[1]})"
    panchangam["ayanamsa"] = ayanamsa_str

    chart_grids = generate_d1_d9_d10_chart_grids(planets)

    dasa_rem_str, dasa_timeline = calculate_dasa_bhukti_dynamic(planets["Moon"]["deg"], dt)
    active_dasa_lord, active_bhukti_lord, current_period_str = get_current_running_period_details(dasa_timeline)

    natal_moon_rasi_idx = planets["Moon"]["rasi_idx"]
    lagna_idx = planets["Lagna"]["rasi_idx"]
    transit_data = generate_detailed_transit_analysis(
        natal_moon_rasi_idx,
        lang=lang,
        lagna_idx=lagna_idx,
        active_dasa_lord=active_dasa_lord,
        active_bhukti_lord=active_bhukti_lord
    )

    all_yogas = analyze_all_conjunctions_and_yogas(planets, dasa_timeline, dt, lang)
    doshas_list = analyze_all_doshas(planets, lagna_idx)
    key_configs = generate_key_configurations(planets, lang)

    overall_horo_pred = generate_comprehensive_prediction(planets, lang)
    trikona_synth = generate_trikona_and_wealth_synthesis(planets, lang)
    dasa_analysis = analyze_favorable_unfavorable_dasas(dasa_timeline)

    meta_data = {
        "person_name": person_name,
        "gender": gender,
        "dob": formatted_dob,
        "tob": formatted_tob,
        "weekday": f"{weekday_info[0]} ({weekday_info[1]})",
        "place": place_name,
        "latitude": f"{lat}° N",
        "longitude": f"{lon}° E",
        "ayanamsa": ayanamsa_str,
        "current_period": current_period_str,
        "active_dasa_lord": active_dasa_lord,
        "active_bhukti_lord": active_bhukti_lord
    }

    prediction_summary_payload = {
        "overall_horoscope": overall_horo_pred,
        "dharma_trikona": trikona_synth["dharma_trikona"],
        "artha_trikona": trikona_synth["artha_trikona"],
        "kama_labha": trikona_synth["kama_labha"],
        "moksha_trikona": trikona_synth["moksha_trikona"],
        "key_configurations": key_configs,
        "favorable_dasas": dasa_analysis["favorable_dasas"],
        "mixed_dasas": dasa_analysis["mixed_dasas"],
        "unfavorable_dasas": dasa_analysis["unfavorable_dasas"],
        "favorable_planets": dasa_analysis["fav_planets"],
        "mixed_planets": dasa_analysis["mixed_planets"],
        "unfavorable_planets": dasa_analysis["unfav_planets"]
    }

    response_payload = OrderedDict([
        ("birth_details_and_panchangam", {
            "_meta": meta_data,
            "panchangam": panchangam
        }),
        ("charts_d1_d9_and_d10", chart_grids),
        ("charts_d1_d9_d10_d20", chart_grids),
        ("planetary_positions_and_dignity", planets),
        ("special_yogas_and_conjunctions", all_yogas),
        ("dosha_details_and_analysis", doshas_list),
        ("key_planetary_configurations", key_configs),
        ("maha_dasa_and_dasa_bhukti_timeline", {
            "dasa_remaining": dasa_rem_str,
            "timeline": dasa_timeline
        }),

        ("saturn_transit_analysis", {
            "title": "Saturn Transit (Sani Gocharam)",
            "analysis": transit_data["saturn_transit"],
            "phase": transit_data["saturn_phase"]
        }),
        ("jupiter_transit_analysis", {
            "title": "Jupiter Transit (Guru Gocharam)",
            "analysis": transit_data["jupiter_transit"],
            "phase": transit_data["jupiter_phase"]
        }),
        ("rahu_ketu_transit_analysis", {
            "title": "Rahu-Ketu Transit (Nodal Axis Gocharam)",
            "analysis": transit_data["rahu_ketu_transit"]
        }),

        ("overall_horoscope_prediction", {
            "overall_horoscope": overall_horo_pred,
            "trikona_synthesis": trikona_synth,
            "favorable_and_unfavorable_dasa_bhukti": {
                "favorable_dasas": dasa_analysis["favorable_dasas"],
                "mixed_dasas": dasa_analysis["mixed_dasas"],
                "unfavorable_dasas": dasa_analysis["unfavorable_dasas"]
            },
            "favorable_and_unfavorable_planets": {
                "favorable_planets": dasa_analysis["fav_planets"],
                "mixed_planets": dasa_analysis["mixed_planets"],
                "unfavorable_planets": dasa_analysis["unfav_planets"]
            }
        }),

        ("_meta", meta_data),
        ("panchangam", panchangam),
        ("planets", planets),
        ("doshas", doshas_list),
        ("dasa_remaining", dasa_rem_str),
        ("dasa_bhukti", dasa_timeline),
        ("conjunctions_2_planet", all_yogas),
        ("prediction_summary", prediction_summary_payload),
        ("language", lang)
    ])

    return response_payload