# -*- coding: utf-8 -*-

# 27 Nakshatras Data
NAKSHATRA_DATA = [
    {"en": "Ashwini", "ta": "அஸ்வினி"},
    {"en": "Bharani", "ta": "பரணி"},
    {"en": "Krittika", "ta": "கார்த்திகை"},
    {"en": "Rohini", "ta": "ரோகிணி"},
    {"en": "Mrigashirsha", "ta": "மிருகசீரிஷம்"},
    {"en": "Ardra", "ta": "திருவாதிரை"},
    {"en": "Punarvasu", "ta": "புனர்பூசம்"},
    {"en": "Pushya", "ta": "பூசம்"},
    {"en": "Ashlesha", "ta": "ஆயில்யம்"},
    {"en": "Magha", "ta": "மகம்"},
    {"en": "Purva Phalguni", "ta": "பூரம்"},
    {"en": "Uttara Phalguni", "ta": "உத்திரம்"},
    {"en": "Hasta", "ta": "ஹஸ்தம்"},
    {"en": "Chitra", "ta": "சித்திரை"},
    {"en": "Swati", "ta": "சுவாதி"},
    {"en": "Vishakha", "ta": "விசாகம்"},
    {"en": "Anuradha", "ta": "அனுஷம்"},
    {"en": "Jyeshtha", "ta": "கேட்டை"},
    {"en": "Mula", "ta": "மூலம்"},
    {"en": "Purva Ashadha", "ta": "பூராடம்"},
    {"en": "Uttara Ashadha", "ta": "உத்திராடம்"},
    {"en": "Shravana", "ta": "திருவோணம்"},
    {"en": "Dhanishta", "ta": "அவிட்டம்"},
    {"en": "Shatabhisha", "ta": "சதயம்"},
    {"en": "Purva Bhadrapada", "ta": "பூரட்டாதி"},
    {"en": "Uttara Bhadrapada", "ta": "உத்திரட்டாதி"},
    {"en": "Revati", "ta": "ரேவதி"}
]

# 12 Rasis Data
RASI_DATA = [
    {"en": "Mesham", "ta": "மேஷம்", "lord_en": "Mars"},
    {"en": "Rishabam", "ta": "ரிஷபம்", "lord_en": "Venus"},
    {"en": "Mithunam", "ta": "மிதுனம்", "lord_en": "Mercury"},
    {"en": "Katakam", "ta": "கடகம்", "lord_en": "Moon"},
    {"en": "Simham", "ta": "சிம்மம்", "lord_en": "Sun"},
    {"en": "Kanni", "ta": "கன்னி", "lord_en": "Mercury"},
    {"en": "Tula", "ta": "துலாம்", "lord_en": "Venus"},
    {"en": "Vrichika", "ta": "விருச்சிகம்", "lord_en": "Mars"},
    {"en": "Dhanus", "ta": "தனுசு", "lord_en": "Jupiter"},
    {"en": "Makaram", "ta": "மகரம்", "lord_en": "Saturn"},
    {"en": "Kumbham", "ta": "கும்பம்", "lord_en": "Saturn"},
    {"en": "Meenam", "ta": "மீனம்", "lord_en": "Jupiter"}
]

# Traditional Tamil Vashya Pairs Index Map
VASHYA_PAIR_MAP = {
    0: [4, 7],     # Mesham -> Simham, Vrichikam
    1: [2, 3],     # Rishabam -> Mithunam, Katakam
    2: [5],        # Mithunam -> Kanni
    3: [7, 8],     # Katakam -> Vrichikam, Dhanus
    4: [9],        # Simham -> Makaram
    5: [2, 6],     # Kanni -> Mithunam, Tula
    6: [5, 9],     # Tula -> Kanni, Makaram
    7: [3],        # Vrichikam -> Katakam
    8: [11],       # Dhanus -> Meenam
    9: [10, 11],   # Makaram -> Kumbham, Meenam
    10: [11],      # Kumbham -> Meenam
    11: [9]        # Meenam -> Makaram
}


def get_star_index_by_name(star_name):
    """Returns the index of a Nakshatra given its name."""
    if not star_name:
        return 0
    clean_name = star_name.split("-")[0].split("(")[0].strip().lower()
    for idx, s in enumerate(NAKSHATRA_DATA):
        if s["en"].lower() in clean_name or s["ta"].lower() in clean_name:
            return idx
    return 0


def get_rasi_index_by_name(rasi_name):
    """Returns the index of a Rasi given its name."""
    if not rasi_name:
        return 0
    clean_name = rasi_name.split("-")[0].split("(")[0].strip().lower()
    for idx, r in enumerate(RASI_DATA):
        if r["en"].lower() in clean_name or r["ta"].lower() in clean_name:
            return idx
    return 0


def calculate_porutham(girl_star_idx, boy_star_idx, girl_rasi_idx, boy_rasi_idx, lang="English"):
    is_ta = (lang == "Tamil")
    poruthams = []
    total_score = 0.0
    mandatory_failed = False

    # 1. Dina Porutham
    count = ((boy_star_idx - girl_star_idx) % 27) + 1
    dina_score = 1.0 if count in [2, 4, 6, 8, 9, 11, 13, 15, 17, 18, 20, 22, 24, 26] else 0.0
    total_score += dina_score
    poruthams.append({
        "group": "1. தினப் பொருத்தம்" if is_ta else "1. Dina Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": dina_score,
        "mandatory": False,
        "result_text": ("உத்தமம்" if dina_score == 1.0 else "அதமம்") if is_ta else ("Uttama (1.0)" if dina_score == 1.0 else "Adhama (0.0)"),
        "benefit": ("ஆரோக்கியம் மற்றும் நீண்ட ஆயுள்" if dina_score == 1.0 else "பொருத்தம் இல்லை") if is_ta else ("Good Health & Longevity" if dina_score == 1.0 else "No Match")
    })

    # 2. Gana Porutham
    gana_groups = [[0, 4, 6, 7, 12, 14, 16, 21, 26], [1, 2, 3, 5, 10, 11, 20, 24, 25], [8, 9, 13, 15, 17, 18, 19, 22, 23]] # Deva, Manushya, Rakshasa
    g_gana = 0 if girl_star_idx in gana_groups[0] else (1 if girl_star_idx in gana_groups[1] else 2)
    b_gana = 0 if boy_star_idx in gana_groups[0] else (1 if boy_star_idx in gana_groups[1] else 2)
    gana_score = 1.0 if (g_gana == b_gana or (g_gana == 0 and b_gana == 1)) else 0.0
    total_score += gana_score
    poruthams.append({
        "group": "2. கணப் பொருத்தம்" if is_ta else "2. Gana Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": gana_score,
        "mandatory": False,
        "result_text": ("உத்தமம்" if gana_score == 1.0 else "அதமம்") if is_ta else ("Uttama (1.0)" if gana_score == 1.0 else "Adhama (0.0)"),
        "benefit": ("மன ஒற்றுமை மற்றும் குணப் பொருத்தம்" if gana_score == 1.0 else "பொருத்தம் இல்லை") if is_ta else ("Temperamental Harmony" if gana_score == 1.0 else "No Match")
    })

    # 3. Mahendra Porutham
    mahendra_score = 1.0 if count in [4, 7, 10, 13, 16, 19, 22, 25] else 0.0
    total_score += mahendra_score
    poruthams.append({
        "group": "3. மகேந்திரப் பொருத்தம்" if is_ta else "3. Mahendra Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": mahendra_score,
        "mandatory": True,
        "result_text": ("உத்தமம்" if mahendra_score == 1.0 else "அதமம்") if is_ta else ("Uttama (1.0)" if mahendra_score == 1.0 else "Adhama (0.0)"),
        "benefit": ("சந்ததி விருத்தி (வம்சம் வளர்தல்)" if mahendra_score == 1.0 else "பொருத்தம் இல்லை") if is_ta else ("Offspring & Family Continuation" if mahendra_score == 1.0 else "No Match")
    })

    # 4. Sthree Deerga Porutham
    stree_score = 1.0 if count > 13 else 0.0
    total_score += stree_score
    poruthams.append({
        "group": "4. ஸ்திரீ தீர்க்கப் பொருத்தம்" if is_ta else "4. Sthree Deerga Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": stree_score,
        "mandatory": True,
        "result_text": ("உத்தமம்" if stree_score == 1.0 else "அதமம்") if is_ta else ("Uttama (1.0)" if stree_score == 1.0 else "Adhama (0.0)"),
        "benefit": ("சுபக்ஷேமம் மற்றும் தீர்க்க சுமங்கலி பாக்கியம்" if stree_score == 1.0 else "பொருத்தம் இல்லை") if is_ta else ("Female Partner Prosperity" if stree_score == 1.0 else "No Match")
    })

    # 5. Yoni Porutham
    yoni_score = 1.0 if (girl_star_idx % 2) != (boy_star_idx % 2) else 0.5
    total_score += yoni_score
    poruthams.append({
        "group": "5. யோனிப் பொருத்தம்" if is_ta else "5. Yoni Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": yoni_score,
        "mandatory": True,
        "result_text": ("உத்தமம்" if yoni_score == 1.0 else "மத்திமம்") if is_ta else ("Uttama (1.0)" if yoni_score == 1.0 else "Madhyama (0.5)"),
        "benefit": ("தாம்பத்திய சுகம் மற்றும் உடலமைப்பு பொருத்தம்" if is_ta else "Physical Compatibility & Intimacy")
    })

    # 6. Rasi Porutham
    rasi_diff = ((boy_rasi_idx - girl_rasi_idx) % 12) + 1
    rasi_score = 1.0 if rasi_diff in [1, 7, 10, 11, 12] else (0.5 if rasi_diff in [3, 4, 5, 9] else 0.0)
    total_score += rasi_score
    poruthams.append({
        "group": "6. ராசிப் பொருத்தம்" if is_ta else "6. Rasi Porutham",
        "girl": RASI_DATA[girl_rasi_idx]["ta" if is_ta else "en"],
        "boy": RASI_DATA[boy_rasi_idx]["ta" if is_ta else "en"],
        "score": rasi_score,
        "mandatory": False,
        "result_text": ("உத்தமம்" if rasi_score == 1.0 else ("மத்திமம்" if rasi_score == 0.5 else "அதமம்")) if is_ta else ("Uttama (1.0)" if rasi_score == 1.0 else ("Madhyama (0.5)" if rasi_score == 0.5 else "Adhama (0.0)")),
        "benefit": ("வம்ச விருத்தி மற்றும் குடும்ப மேன்மை" if rasi_score >= 0.5 else "பொருத்தம் இல்லை") if is_ta else ("Family Lineage & Growth" if rasi_score >= 0.5 else "No Match")
    })

    # 7. Rasi Adhipathi (Lord) Porutham
    g_lord = RASI_DATA[girl_rasi_idx]["lord_en"]
    b_lord = RASI_DATA[boy_rasi_idx]["lord_en"]
    lord_score = 1.0 if g_lord == b_lord else 0.5
    total_score += lord_score
    poruthams.append({
        "group": "7. ராசியதிபதி பொருத்தம்" if is_ta else "7. Rasi Lord Porutham",
        "girl": g_lord,
        "boy": b_lord,
        "score": lord_score,
        "mandatory": False,
        "result_text": ("உத்தமம்" if lord_score == 1.0 else "மத்திமம்") if is_ta else ("Uttama (1.0)" if lord_score == 1.0 else "Madhyama (0.5)"),
        "benefit": ("சந்தான பாக்கியம் மற்றும் நட்பு" if is_ta else "Children Happiness & Friendship")
    })

    # 8. Vashya Porutham
    vashya_match = (
        boy_rasi_idx in VASHYA_PAIR_MAP.get(girl_rasi_idx, []) or
        girl_rasi_idx in VASHYA_PAIR_MAP.get(boy_rasi_idx, [])
    )
    vashya_score = 1.0 if vashya_match else 0.0
    total_score += vashya_score
    poruthams.append({
        "group": "8. வசியப் பொருத்தம்" if is_ta else "8. Vashya Porutham",
        "girl": RASI_DATA[girl_rasi_idx]["ta" if is_ta else "en"],
        "boy": RASI_DATA[boy_rasi_idx]["ta" if is_ta else "en"],
        "score": vashya_score,
        "mandatory": False,
        "result_text": ("உத்தமம் (1.0)" if vashya_score == 1.0 else "அதமம் (0.0)") if is_ta else ("Uttama (1.0)" if vashya_score == 1.0 else "Adhama (0.0)"),
        "benefit": ("பரஸ்பர அன்பு மற்றும் ஈர்ப்பு" if vashya_score == 1.0 else "வசியப் பொருத்தம் இல்லை") if is_ta else ("Mutual Attraction & Harmony" if vashya_score == 1.0 else "No Vashya Match")
    })

    # 9. Rajju Porutham (Mandatory Match)
    rajju_groups = [[0, 4, 9, 13, 18, 22], [1, 3, 5, 10, 12, 14, 19, 21, 23], [2, 6, 7, 8, 11, 15, 16, 17, 20, 24, 25, 26]]
    g_rajju = 0 if girl_star_idx in rajju_groups[0] else (1 if girl_star_idx in rajju_groups[1] else 2)
    b_rajju = 0 if boy_star_idx in rajju_groups[0] else (1 if boy_star_idx in rajju_groups[1] else 2)
    rajju_pass = (g_rajju != b_rajju)
    rajju_score = 1.0 if rajju_pass else 0.0
    if not rajju_pass:
        mandatory_failed = True
    total_score += rajju_score
    poruthams.append({
        "group": "9. ரஜ்ஜுப் பொருத்தம்" if is_ta else "9. Rajju Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": rajju_score,
        "mandatory": True,
        "result_text": ("உத்தமம்" if rajju_pass else "தோஷம் (அதமம்)") if is_ta else ("Uttama (1.0)" if rajju_pass else "Rajju Dosham (0.0)"),
        "benefit": ("மாங்கல்ய பாக்கியம் (தீர்க்க சுமங்கலி)" if rajju_pass else "ரஜ்ஜு தோஷம் உண்டு") if is_ta else ("Husband Longevity & Protection" if rajju_pass else "Rajju Dosha Present")
    })

    # 10. Vedha Porutham (Mandatory Match)
    vedha_pairs = [(0, 17), (1, 16), (2, 15), (3, 14), (4, 13), (5, 12), (6, 11), (7, 10), (8, 9), (18, 26), (19, 25), (20, 24), (21, 23)]
    has_vedha = False
    for p1, p2 in vedha_pairs:
        if (girl_star_idx == p1 and boy_star_idx == p2) or (girl_star_idx == p2 and boy_star_idx == p1):
            has_vedha = True
            break
    vedha_score = 0.0 if has_vedha else 1.0
    if has_vedha:
        mandatory_failed = True
    total_score += vedha_score
    poruthams.append({
        "group": "10. வேதைப் பொருத்தம்" if is_ta else "10. Vedha Porutham",
        "girl": NAKSHATRA_DATA[girl_star_idx]["ta" if is_ta else "en"],
        "boy": NAKSHATRA_DATA[boy_star_idx]["ta" if is_ta else "en"],
        "score": vedha_score,
        "mandatory": True,
        "result_text": ("உத்தமம்" if not has_vedha else "வேதை தோஷம் (0.0)") if is_ta else ("Uttama (1.0)" if not has_vedha else "Vedha Dosham (0.0)"),
        "benefit": ("துன்பமின்மை மற்றும் சுபவாழ்க்கை" if not has_vedha else "வேதை தோஷம் உண்டு") if is_ta else ("Freedom from Obstacles" if not has_vedha else "Vedha Dosha Present")
    })

    # Final Verdict Synthesis
    if not mandatory_failed and total_score >= 6.0:
        verdict = "திருமணம் செய்யலாம்\nஉத்தம பொருத்தம்" if is_ta else "Highly Compatible - Recommended"
        verdict_color = "#27ae60"
    elif not mandatory_failed and total_score >= 5.0:
        verdict = "மிதமான பொருத்தம்\nபரிகாரங்களுடன் செய்யலாம்" if is_ta else "Moderately Compatible"
        verdict_color = "#f39c12"
    else:
        verdict = "பொருத்தம் இல்லை\nதவிர்க்கவும்" if is_ta else "Not Recommended (Rajju/Vedha Dosham or Low Score)"
        verdict_color = "#d9534f"

    return {
        "total_score": total_score,
        "max_score": 10.0,
        "poruthams": poruthams,
        "mandatory_failed": mandatory_failed,
        "verdict": verdict,
        "verdict_color": verdict_color
    }