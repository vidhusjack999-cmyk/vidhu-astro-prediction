# -*- coding: utf-8 -*-
"""
app.py
Flask Web Application for Vidhu Astro Engine & AI Astrology Services.
Integrates Swiss Ephemeris calculations, Star Matching, Chart Matching,
PDF text extraction, and Gemini AI report generation via a Level 4 Pipeline.
"""
import os
import io
import re
import uuid
import time
import json
import sqlite3
import traceback
import warnings
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

# Suppress Google GenAI AFC deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")

# Explicitly target .env in the same directory as app.py
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)

print("[DEBUG] .env file exists:", ENV_FILE.is_file())
print("[DEBUG] Gemini key detected:", bool(os.environ.get("GEMINI_API_KEY", "").strip()))

from flask import (
    Flask, render_template, request,
    session, redirect, url_for, jsonify
)
from pypdf import PdfReader

# Google GenAI SDK imports
from google import genai
from google.genai import types
from google.genai.errors import APIError

import astro_engine
import matching_engine
import chart_matching_engine
import palan_service
import orchestrator
from gemini_models import get_models, invalidate_cache

app = Flask(__name__)

# Security & Upload Limit Configuration (10 MB max payload)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "dev-only-change-in-production"
)

# Server-side PDF text storage directory
TEMP_DATA_DIR = os.path.join(app.root_path, "temp_pdf_data")
os.makedirs(TEMP_DATA_DIR, exist_ok=True)

# Server-side Chart Cache directory (replaces large session cookies)
CHART_CACHE_DIR = os.path.join(app.root_path, "chart_cache")
os.makedirs(CHART_CACHE_DIR, exist_ok=True)

# SQLite Database for Thread-Safe API Usage Tracking
DB_PATH = os.path.join(app.root_path, "api_tracker.db")


def init_tracker_db():
    """Initializes the SQLite tracker database with WAL mode for thread safety."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                endpoint TEXT NOT NULL,
                model_used TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                is_retry INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"--> [WARN] Tracker DB Init Error: {e}")


# Initialize tracker DB on server startup
init_tracker_db()


def log_gemini_attempt(endpoint, model_used, status_code, is_retry=False):
    """Logs every Gemini call attempt to SQLite for accurate rate limit tracking."""
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
        print(f"--> [WARN] Tracker Log Error: {e}")


def get_usage_metrics(rpm_limit=15, rpd_limit=1500):
    """Calculates active RPM and today's total request count from SQLite logs."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        now = time.time()
        one_minute_ago = now - 60
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

        cursor.execute("SELECT COUNT(*) FROM api_logs WHERE timestamp >= ?", (one_minute_ago,))
        current_rpm = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM api_logs WHERE timestamp >= ?", (today_start,))
        total_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM api_logs WHERE timestamp >= ? AND status_code = 429", (today_start,))
        errors_429_today = cursor.fetchone()[0]

        conn.close()

        return {
            "current_rpm": current_rpm,
            "rpm_limit": rpm_limit,
            "requests_today": total_today,
            "rpd_limit": rpd_limit,
            "errors_429_today": errors_429_today,
            "quota_used_percentage": round((total_today / rpd_limit) * 100, 2)
        }
    except Exception as e:
        print(f"--> [WARN] Metrics Calculation Error: {e}")
        return {
            "current_rpm": 0, "rpm_limit": rpm_limit,
            "requests_today": 0, "rpd_limit": rpd_limit,
            "errors_429_today": 0, "quota_used_percentage": 0.0
        }


def evaluate_rahu_ketu_dosha(rahu_house, ketu_house, jupiter_house=None, is_jupiter_exalted=False):
    """Evaluates Rahu-Ketu / Sarpa Dosha based on classical Parashari rules."""
    jupiter_aspects_rahu = False
    if jupiter_house is not None:
        jup_aspects = [((jupiter_house + k - 2) % 12) + 1 for k in (1, 5, 7, 9)]
        if rahu_house in jup_aspects or ketu_house in jup_aspects:
            jupiter_aspects_rahu = True

    if (rahu_house in [1, 7] and ketu_house in [1, 7]) or (rahu_house in [2, 8] and ketu_house in [2, 8]):
        if jupiter_aspects_rahu or is_jupiter_exalted:
            return {
                "dosha_name": "Rahu-Ketu / Sarpa Dosha",
                "status": "NOT PRESENT (CANCELLED)",
                "forming_condition": f"Rahu in House {rahu_house} and Ketu in House {ketu_house} from Lagna.",
                "impact_analysis": "Primary 1/7 or 2/8 nodal axis placement is neutralized by Jupiter's aspect."
            }
        return {
            "dosha_name": "Rahu-Ketu / Sarpa Dosha",
            "status": "PRESENT",
            "forming_condition": f"Rahu in House {rahu_house} and Ketu in House {ketu_house} from Lagna.",
            "impact_analysis": "Rahu-Ketu / Sarpa affliction present in core marriage houses (1/7 or 2/8 axis)."
        }

    elif (rahu_house in [5, 11] and ketu_house in [5, 11]):
        return {
            "dosha_name": "Rahu-Ketu / Sarpa Dosha",
            "status": "PARTIALLY PRESENT",
            "forming_condition": f"Rahu in House {rahu_house} and Ketu in House {ketu_house} from Lagna.",
            "impact_analysis": "Affects areas of creativity, intellect, romance, and children (5th house)."
        }

    return {
        "dosha_name": "Rahu-Ketu / Sarpa Dosha",
        "status": "NOT PRESENT",
        "forming_condition": f"Rahu in House {rahu_house} and Ketu in House {ketu_house} from Lagna.",
        "impact_analysis": "Nodal placement falls outside core marital houses."
    }


def cleanup_old_temp_files(max_age_hours=4):
    """Deletes temporary extracted PDF text files and cached charts older than specified hours."""
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    try:
        for folder in [TEMP_DATA_DIR, CHART_CACHE_DIR]:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
    except Exception as e:
        print(f"--> [WARN] Temp file cleanup error: {e}")


def save_chart_to_cache(chart_dict):
    """Saves birth chart dict to disk and stores a lightweight UUID token in session to prevent cookie size limits."""
    cleanup_old_temp_files()
    cid = uuid.uuid4().hex
    filepath = os.path.join(CHART_CACHE_DIR, f"{cid}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(chart_dict, f, ensure_ascii=False)
    session["chart_id"] = cid


def load_chart_from_cache():
    """Retrieves birth chart dict from disk using the session UUID."""
    cid = session.get("chart_id", "")
    if not cid or not cid.isalnum():
        return None
    filepath = os.path.join(CHART_CACHE_DIR, f"{cid}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def extract_text_from_pdf(pdf_file_bytes):
    """Extracts raw structured text from an uploaded PDF file and validates readability."""
    try:
        reader = PdfReader(io.BytesIO(pdf_file_bytes))
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    except Exception as e:
        raise Exception(f"Failed to read PDF file: {str(e)}")

    if len(full_text.strip()) < 50:
        raise Exception(
            "No readable text found in this PDF. "
            "Please upload the text-based PDF generated by Vidhu Astro, "
            "not a scanned image."
        )

    return full_text


def save_extracted_text_to_file(text, prefix="chart"):
    """Saves extracted text server-side and returns the pointer filename."""
    cleanup_old_temp_files()
    filename = f"{prefix}_{uuid.uuid4().hex}.txt"
    filepath = os.path.join(TEMP_DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filename


def read_extracted_text_from_file(filename):
    """Reads extracted text from a server-side file."""
    if not filename:
        return ""
    filepath = os.path.join(TEMP_DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def parse_metadata_from_text(extracted_text):
    meta = {
        "person_name": "",
        "dob": "",
        "tob": "",
        "lagna": "",
        "rasi": "",
        "current_period": ""
    }

    if not extracted_text:
        return meta

    # 1. Native Name
    name_m = re.search(r"Name\s*[:\|]\s*([^\n\r\|]+)", extracted_text, re.IGNORECASE)
    if name_m:
        meta["person_name"] = name_m.group(1).split("Date of Birth")[0].strip()

    # 2. Date of Birth
    dob_m = re.search(r"Date\s+of\s+Birth\s*[:\|]\s*([\d\-\/]+)", extracted_text, re.IGNORECASE)
    if dob_m:
        meta["dob"] = dob_m.group(1).strip()

    # 3. Time of Birth
    tob_m = re.search(r"Time\s+of\s+Birth\s*[:\|]\s*([\d:\s]+(?:AM|PM|am|pm)?)", extracted_text, re.IGNORECASE)
    if tob_m:
        meta["tob"] = tob_m.group(1).split("Place of Birth")[0].strip()

    # 4. Ascendant / Lagna
    # Specifically targets "Ascendant | <Sign>" or "Lagna | <Sign>"
    lagna_m = re.search(r"(?:Ascendant|Lagna)\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\||\n|\r)", extracted_text, re.IGNORECASE)
    if lagna_m:
        meta["lagna"] = lagna_m.group(1).strip()
    else:
        lagna_fallback = re.search(r"(?:Ascendant|Lagna)\s*[:]\s*([^\n\r\|]+)", extracted_text, re.IGNORECASE)
        if lagna_fallback:
            meta["lagna"] = lagna_fallback.group(1).strip()

    # 5. Moon Sign (Rasi)
    # Specifically targets "Moon Sign (Rasi) | <Sign>" from Panchangam table, or "Moon | <Sign>" from Planetary table
    rasi_m = re.search(r"Moon\s+Sign\s*\(Rasi\)\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\||\n|\r|Nakshatra|Gana)", extracted_text, re.IGNORECASE)
    if rasi_m:
        meta["rasi"] = rasi_m.group(1).strip()
    else:
        # Fallback to Moon row in Section 3 table: "Moon | Simha (...) |"
        moon_row_m = re.search(r"\bMoon\s*\|\s*([A-Za-z\u0b80-\u0bff\s\(\)]+?)(?=\s*\|)", extracted_text, re.IGNORECASE)
        if moon_row_m:
            meta["rasi"] = moon_row_m.group(1).strip()

    # 6. Current Running Period
    period_m = re.search(r"CURRENT\s+RUNNING\s+PERIOD\s*[:\|]\s*([^\n\r]+)", extracted_text, re.IGNORECASE)
    if period_m:
        meta["current_period"] = period_m.group(1).replace("⏳", "").strip()

    return meta


# -------------------------------------------------------------------
# APPLICATION ROUTES
# -------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/admin/usage", methods=["GET"])
def admin_usage():
    """Secure usage endpoint for n8n monitoring and internal health checks."""
    auth_token = request.headers.get("X-Admin-Token") or request.args.get("token")
    expected_token = os.environ.get("ADMIN_METRICS_TOKEN", "vidhu-admin-secret")

    if auth_token != expected_token:
        return jsonify({"status": "error", "message": "Unauthorized access"}), 401

    metrics = get_usage_metrics()
    return jsonify({
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics
    })


@app.route("/birth_chart_form", methods=["GET"])
def birth_chart_form():
    return render_template("birth_chart_form.html")


@app.route("/birth_chart", methods=["GET", "POST"])
def birth_chart():
    if request.method == "POST":
        try:
            person_name = request.form.get("person_name", "").strip()
            place_name = request.form.get("place_name", "Chennai").strip()
            chart_language = request.form.get("chart_language", "English").strip()

            dob_day = str(request.form.get("dob_day", "1")).strip().zfill(2)
            dob_month = str(request.form.get("dob_month", "01")).strip().zfill(2)
            dob_year = str(request.form.get("dob_year", "1990")).strip()
            dob = f"{dob_year}-{dob_month}-{dob_day}"

            tob_hour = int(request.form.get("tob_hour", "12"))
            tob_minute = int(request.form.get("tob_minute", "0"))
            tob_ampm = request.form.get("tob_ampm", "AM").strip()

            if tob_ampm == "PM" and tob_hour < 12:
                tob_hour += 12
            elif tob_ampm == "AM" and tob_hour == 12:
                tob_hour = 0

            tob = f"{tob_hour:02d}:{tob_minute:02d}"

            lat_val = float(request.form.get("lat", "13.0827") or "13.0827")
            lon_val = float(request.form.get("lon", "80.2707") or "80.2707")

            chart = astro_engine.calculate_birth_chart(
                person_name=person_name,
                gender="Male",
                dob=dob,
                tob=tob,
                place_name=place_name,
                lat=lat_val,
                lon=lon_val,
                lang=chart_language
            )

            save_chart_to_cache(chart)
            return render_template(
                "birth_chart.html",
                chart=chart,
                saturn_transit_analysis=chart.get("saturn_transit_analysis", {}),
                jupiter_transit_analysis=chart.get("jupiter_transit_analysis", {}),
                rahu_ketu_transit_analysis=chart.get("rahu_ketu_transit_analysis", {})
            )

        except Exception as e:
            error_msg = f"Birth Chart Calculation Error: {str(e)}"
            return render_template("birth_chart_form.html", error=error_msg)

    chart = load_chart_from_cache()
    if not chart:
        return redirect(url_for("birth_chart_form"))
    return render_template(
        "birth_chart.html",
        chart=chart,
        saturn_transit_analysis=chart.get("saturn_transit_analysis", {}),
        jupiter_transit_analysis=chart.get("jupiter_transit_analysis", {}),
        rahu_ketu_transit_analysis=chart.get("rahu_ketu_transit_analysis", {})
    )


@app.route("/vidhu_prediction", methods=["GET"])
def vidhu_prediction():
    chart = load_chart_from_cache()
    return render_template("vidhu_prediction.html", chart=chart)


@app.route("/api/upload_pdf", methods=["POST"])
def upload_pdf():
    try:
        workflow_type = request.form.get("workflow_type", "individual")

        if workflow_type == "individual":
            if "ind_pdf" not in request.files:
                return jsonify({"status": "error", "message": "No file uploaded"}), 400
            file = request.files["ind_pdf"]
            extracted_text = extract_text_from_pdf(file.read())

            filename = save_extracted_text_to_file(extracted_text, prefix="ind")
            session["individual_pdf_file"] = filename

            meta = parse_metadata_from_text(extracted_text)
            return jsonify({
                "status": "success",
                "message": f"Individual Birth Chart PDF parsed successfully for {meta['person_name'] or 'Native'}!",
                "meta": meta,
                "pdf_text": extracted_text
            })

        elif workflow_type == "marriage_matching":
            if "match_pdf" not in request.files:
                return jsonify({"status": "error", "message": "No file uploaded"}), 400
            file = request.files["match_pdf"]
            extracted_text = extract_text_from_pdf(file.read())

            filename = save_extracted_text_to_file(extracted_text, prefix="match")
            session["matching_pdf_file"] = filename

            meta = parse_metadata_from_text(extracted_text)
            return jsonify({
                "status": "success",
                "message": "Matching Report PDF parsed successfully!",
                "meta": meta,
                "pdf_text": extracted_text
            })

        elif workflow_type == "married_couple":
            husband_file = request.files.get("husband_pdf")
            wife_file = request.files.get("wife_pdf")

            if not husband_file or not wife_file:
                return jsonify({"status": "error", "message": "Both Husband and Wife PDFs are required"}), 400

            husband_text = extract_text_from_pdf(husband_file.read())
            wife_text = extract_text_from_pdf(wife_file.read())

            h_filename = save_extracted_text_to_file(husband_text, prefix="husband")
            w_filename = save_extracted_text_to_file(wife_text, prefix="wife")

            session["husband_pdf_file"] = h_filename
            session["wife_pdf_file"] = w_filename

            combined_text = f"HUSBAND CHART:\n{husband_text}\n\nWIFE CHART:\n{wife_text}"
            meta = parse_metadata_from_text(husband_text)
            return jsonify({
                "status": "success",
                "message": "Both Husband & Wife Chart PDFs parsed successfully!",
                "meta": meta,
                "pdf_text": combined_text
            })

        return jsonify({"status": "error", "message": "Invalid workflow type"}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/generate_prediction", methods=["POST"])
def generate_prediction():
    try:
        data = request.get_json() or {}
        workflow_type = data.get("workflow_type", "individual")
        topic = data.get("topic", "Overall Prediction")
        chart_language = data.get("language", "English")
        user_feedback = data.get("user_feedback", "").strip()

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        print(f"--> [DEBUG] GEMINI_API_KEY Active: {bool(api_key)}")

        pdf_text = ""
        if workflow_type == "individual":
            filename = session.get("individual_pdf_file", "")
            pdf_text = read_extracted_text_from_file(filename)
        elif workflow_type == "marriage_matching":
            filename = session.get("matching_pdf_file", "")
            pdf_text = read_extracted_text_from_file(filename)
        elif workflow_type == "married_couple":
            h_filename = session.get("husband_pdf_file", "")
            w_filename = session.get("wife_pdf_file", "")
            h_text = read_extracted_text_from_file(h_filename)
            w_text = read_extracted_text_from_file(w_filename)
            if h_text and w_text:
                pdf_text = f"HUSBAND CHART:\n{h_text}\n\nWIFE CHART:\n{w_text}"

        chart_data = load_chart_from_cache() or session.get("chart_data") or {}

        if not pdf_text and not chart_data:
            return jsonify({
                "status": "error",
                "message": "Please generate a birth chart or upload the required PDF chart file(s) first."
            }), 400

        if pdf_text or not chart_data:
            prediction_text = palan_service.generate_topic_reading(
                chart_data=chart_data,
                topic=topic,
                language=chart_language,
                is_chat_reply=bool(user_feedback),
                user_feedback=user_feedback,
                pdf_text=pdf_text
            )
        else:
            prediction_text = orchestrator.execute_level4_prediction_pipeline(
                chart_data=chart_data,
                topic=topic,
                generate_llm_fn=palan_service.generate_prediction_llm,
                language=chart_language
            )

        return jsonify({
            "status": "success",
            "topic": topic,
            "prediction": prediction_text
        })

    except Exception as e:
        traceback.print_exc()
        msg = str(e)
        if "503" in msg or "UNAVAILABLE" in msg:
            msg = "Vidhu AI is experiencing high demand. Please try again in a minute."
        elif "API_KEY_INVALID" in msg or "401" in msg:
            msg = "The AI service key is not configured correctly. Please contact the administrator."
        return jsonify({"status": "error", "message": msg}), 500


@app.route("/star_matching", methods=["GET", "POST"])
def star_matching():
    lang = request.form.get("language", "English") if request.method == "POST" else "English"

    if request.method == "POST":
        girl_star = request.form.get("girl_star", "")
        girl_rasi = request.form.get("girl_rasi", "")
        boy_star = request.form.get("boy_star", "")
        boy_rasi = request.form.get("boy_rasi", "")

        girl_star_idx = matching_engine.get_star_index_by_name(girl_star)
        boy_star_idx = matching_engine.get_star_index_by_name(boy_star)
        girl_rasi_idx = matching_engine.get_rasi_index_by_name(girl_rasi)
        boy_rasi_idx = matching_engine.get_rasi_index_by_name(boy_rasi)

        match_report = matching_engine.calculate_porutham(
            girl_star_idx, boy_star_idx, girl_rasi_idx, boy_rasi_idx, lang=lang
        )

        return render_template(
            "star_matching.html",
            match_report=match_report,
            girl_star=girl_star,
            girl_rasi=girl_rasi,
            boy_star=boy_star,
            boy_rasi=boy_rasi,
            lang=lang,
            stars=[s["ta"] if lang == "Tamil" else s["en"] for s in matching_engine.NAKSHATRA_DATA],
            rasis=[r["ta"] if lang == "Tamil" else r["en"] for r in matching_engine.RASI_DATA]
        )

    return render_template(
        "star_matching.html",
        lang=lang,
        stars=[s["ta"] if lang == "Tamil" else s["en"] for s in matching_engine.NAKSHATRA_DATA],
        rasis=[r["ta"] if lang == "Tamil" else r["en"] for r in matching_engine.RASI_DATA]
    )


@app.route("/chart_matching", methods=["GET", "POST"])
def chart_matching():
    form_data = {
        "chart_language": "English",
        "boy_name": "Groom", "boy_dob_day": "03", "boy_dob_month": "12", "boy_dob_year": "1990",
        "boy_tob_hour": "09", "boy_tob_minute": "05", "boy_tob_ampm": "PM",
        "boy_place": "Chennai", "boy_latitude": "13.0827", "boy_longitude": "80.2707",
        "girl_name": "Bride", "girl_dob_day": "15", "girl_dob_month": "08", "girl_dob_year": "1995",
        "girl_tob_hour": "10", "girl_tob_minute": "30", "girl_tob_ampm": "AM",
        "girl_place": "Chennai", "girl_latitude": "13.0827", "girl_longitude": "80.2707"
    }

    if request.method == "POST":
        try:
            for key in form_data.keys():
                if request.form.get(key):
                    form_data[key] = request.form.get(key).strip()

            lang = form_data.get("chart_language", "English")

            boy_chart, girl_chart, report, error = chart_matching_engine.generate_chart_matching_report(form_data)

            if error:
                return render_template("chart_matching.html", error=error, form_data=form_data, report=None)

            return render_template(
                "chart_matching.html",
                report=report,
                girl_chart=girl_chart,
                boy_chart=boy_chart,
                form_data=form_data,
                lang=lang
            )
        except Exception as e:
            traceback.print_exc()
            return render_template("chart_matching.html", error=f"Calculation Error: {str(e)}", form_data=form_data,
                                   report=None)

    return render_template("chart_matching.html", form_data=form_data, report=None)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)