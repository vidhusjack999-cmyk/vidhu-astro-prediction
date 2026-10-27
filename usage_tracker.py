# -*- coding: utf-8 -*-
"""
usage_tracker.py - Thread-Safe SQLite Usage & API Health Tracker
Monitors request throughput and API health.
Handles dynamic keyword args from orchestrator.py and auto-migrates missing columns.
"""

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = os.environ.get("USAGE_DB", os.path.join(os.path.dirname(__file__), "api_tracker.db"))
QUOTA_TZ = ZoneInfo("America/Los_Angeles")


@contextmanager
def _conn():
    """Context manager ensuring thread-safe connections with WAL mode enabled."""
    con = sqlite3.connect(DB_PATH, timeout=10.0)
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    """Initializes tables and dynamically migrates schema if columns are missing."""
    with _conn() as c:
        cursor = c.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                endpoint TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                http_code INTEGER,
                latency_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                endpoint TEXT DEFAULT '',
                is_retry INTEGER DEFAULT 0
            )
        """)

        # Execute dynamic schema migration using cursor.fetchall()
        cursor.execute("PRAGMA table_info(api_attempts);")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if "endpoint" not in existing_cols:
            cursor.execute("ALTER TABLE api_attempts ADD COLUMN endpoint TEXT DEFAULT '';")
            print("[DEBUG] Added missing 'endpoint' column to api_attempts")

        if "is_retry" not in existing_cols:
            cursor.execute("ALTER TABLE api_attempts ADD COLUMN is_retry INTEGER DEFAULT 0;")
            print("[DEBUG] Added missing 'is_retry' column to api_attempts")

        cursor.execute("CREATE INDEX IF NOT EXISTS ix_cr_ts ON customer_requests(ts)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_aa_ts ON api_attempts(ts)")


def log_customer_request(endpoint: str = ""):
    """Logs user-initiated actions at the route layer."""
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO customer_requests (ts, endpoint) VALUES (?, ?)",
                (time.time(), endpoint)
            )
    except Exception as e:
        print(f"--> [WARN] Tracker Customer Log Error: {e}")


def log_api_attempt(
    model: str = None,
    status: str = "ok",
    http_code: int = None,
    latency_ms: int = None,
    tokens_in: int = None,
    tokens_out: int = None,
    endpoint: str = "/api/prediction",
    model_used: str = None,
    status_code: int = None,
    is_retry: bool = False
):
    """
    Logs Gemini API attempts.
    Flexible signature accepts both positional args and keyword args (endpoint, model_used, status_code, is_retry).
    """
    selected_model = model_used or model or "gemini-2.0-flash"
    code = status_code if status_code is not None else (http_code or 200)
    status_str = status if status else ("ok" if code == 200 else f"error_{code}")
    retry_int = 1 if is_retry else 0

    try:
        with _conn() as c:
            c.execute(
                """INSERT INTO api_attempts (ts, model, status, http_code, latency_ms, tokens_in, tokens_out, endpoint, is_retry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), selected_model, status_str, code, latency_ms, tokens_in, tokens_out, endpoint, retry_int)
            )
    except Exception as e:
        print(f"--> [WARN] Tracker API Attempt Log Error: {e}")


def _quota_day_start_ts(now=None):
    now = now or datetime.now(QUOTA_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _limit(env_name: str):
    v = os.environ.get(env_name)
    return int(v) if v and v.isdigit() else None


def get_stats():
    start = _quota_day_start_ts()
    now = time.time()

    with _conn() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchone()[0] or 0

        cust_today = q("SELECT COUNT(*) FROM customer_requests WHERE ts >= ?", start)
        calls_today = q("SELECT COUNT(*) FROM api_attempts WHERE ts >= ?", start)
        calls_60s = q("SELECT COUNT(*) FROM api_attempts WHERE ts >= ?", now - 60)
        e429 = q("SELECT COUNT(*) FROM api_attempts WHERE ts >= ? AND (http_code = 429 OR status = 'rate_limit')", start)
        e503 = q("SELECT COUNT(*) FROM api_attempts WHERE ts >= ? AND (http_code = 503 OR status = 'unavailable')", start)

        tok = c.execute(
            "SELECT COALESCE(SUM(tokens_in), 0), COALESCE(SUM(tokens_out), 0) FROM api_attempts WHERE ts >= ?",
            (start,)
        ).fetchone()

        per_model = c.execute(
            "SELECT model, COUNT(*) FROM api_attempts WHERE ts >= ? GROUP BY model",
            (start,)
        ).fetchall()

    rpd, rpm = _limit("GEMINI_RPD_LIMIT"), _limit("GEMINI_RPM_LIMIT")

    return {
        "customer_requests_today": cust_today,
        "api_calls_today": calls_today,
        "api_calls_last_60s": calls_60s,
        "errors_429_503_today": e429 + e503,
        "errors_429_today": e429,
        "errors_503_today": e503,
        "tokens_in_today": tok[0],
        "tokens_out_today": tok[1],
        "calls_by_model": dict(per_model),
        "daily_limit": rpd,
        "rpm_limit": rpm,
        "daily_used_pct": round(100 * calls_today / rpd, 1) if rpd else None,
        "alert_80pct": bool(rpd and calls_today >= 0.8 * rpd),
        "quota_day_resets": "midnight Pacific (America/Los_Angeles)"
    }


# Auto-initialize database schema on import
init_db()