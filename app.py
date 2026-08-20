from collections import defaultdict, deque
import os
import sqlite3
import time
from datetime import datetime
import logging
import sys
import traceback

from flask import Flask, redirect, request, jsonify, render_template

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=not app.debug,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE="Lax",
    REMEMBER_COOKIE_SECURE=not app.debug,
)
DB_PATH = os.environ.get('IOT_DB_PATH') or os.path.join(os.path.dirname(os.path.abspath(__file__)), "iot_data.db")
# Configure logging to ensure stdout/stderr messages appear in Render logs
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
logger.info(f"DB_PATH set to: {DB_PATH}")
RATE_LIMITS = defaultdict(deque)
RATE_LIMIT_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = {
    "sensor": 15,
    "control": 10,
}


def format_timestamp(raw_timestamp):
    try:
        return datetime.strptime(raw_timestamp, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %I:%M:%S %p")
    except (TypeError, ValueError):
        return raw_timestamp


def get_db():
    parent = os.path.dirname(DB_PATH) or '.'
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
            logger.info(f"Created parent directory for DB at: {parent}")
        except Exception as e:
            logger.warning(f"Failed to create parent dir {parent}: {e}")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        logger.error("sqlite3.OperationalError opening DB_PATH=%s: %s", DB_PATH, e)
        try:
            parent_exists = os.path.exists(parent)
            parent_perm = oct(os.stat(parent).st_mode) if parent_exists else 'n/a'
            logger.error("parent_exists=%s parent_perm=%s", parent_exists, parent_perm)
            if parent_exists:
                logger.error("parent listing: %s", os.listdir(parent))
        except Exception as ex:
            logger.error("Error while logging parent info: %s", ex)
        # Re-raise so startup fails loudly (Render will capture stack trace)
        raise


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def check_rate_limit():
    if app.debug:
        return False

    endpoint_name = request.endpoint
    if endpoint_name not in {"post_sensor", "control"}:
        return False

    now = time.time()
    bucket_key = f"{client_ip()}:{endpoint_name}"
    bucket = RATE_LIMITS[bucket_key]
    while bucket and now - bucket[0] >= RATE_LIMIT_SECONDS:
        bucket.popleft()

    limit = MAX_REQUESTS_PER_WINDOW.get("sensor" if endpoint_name == "post_sensor" else "control")
    if len(bucket) >= limit:
        return True

    bucket.append(now)
    return False


@app.before_request
def enforce_security_policy():
    if not app.debug and request.headers.get("X-Forwarded-Proto") == "http" and request.url.startswith("http://"):
        return redirect(request.url.replace("http://", "https://", 1), code=301)

    if check_rate_limit():
        return jsonify({"error": "rate limit exceeded"}), 429


@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self' http: https:"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains" if not app.debug else "max-age=0"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def init_db():
    try:
        conn = get_db()
    except Exception as e:
        logger.exception("Failed to open database during init_db. DB_PATH=%s", DB_PATH)
        # Re-raise to allow the process to fail and Render to show logs
        raise

    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motion INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    # Ensure readings table has angle/distance/range_max columns (upgrade older DBs)
    cur = conn.execute("PRAGMA table_info(readings)").fetchall()
    reading_cols = [r['name'] for r in cur]
    if 'angle' not in reading_cols:
        conn.execute("ALTER TABLE readings ADD COLUMN angle REAL")
    if 'distance' not in reading_cols:
        conn.execute("ALTER TABLE readings ADD COLUMN distance REAL")
    if 'range_max' not in reading_cols:
        conn.execute("ALTER TABLE readings ADD COLUMN range_max REAL")
    # Create device_state table (without brightness initially) and then ensure the
    # brightness column exists. This order avoids INSERT failures when upgrading old DBs
    # that were created without the brightness column.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT NOT NULL DEFAULT 'OFF'
        )
    """)

    # Ensure older databases missing the brightness column are updated
    cur = conn.execute("PRAGMA table_info(device_state)").fetchall()
    col_names = [r['name'] for r in cur]
    if 'brightness' not in col_names:
        conn.execute("ALTER TABLE device_state ADD COLUMN brightness INTEGER NOT NULL DEFAULT 100")

    # Safe insert now that brightness column exists (either originally or via ALTER)
    conn.execute("INSERT OR IGNORE INTO device_state (id, state, brightness) VALUES (1, 'OFF', 100)")

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    return render_template("index.html")


# ---- Device -> Server: ESP32 / ESP-01 posts a new PIR reading here ----
@app.route("/api/sensor", methods=["POST"])
def post_sensor():
    data = request.get_json(force=True, silent=True) or {}
    motion_value = data.get("motion")
    if motion_value is None:
        return jsonify({"error": "motion is required"}), 400

    try:
        motion = int(motion_value)
    except (TypeError, ValueError):
        return jsonify({"error": "motion must be 0 or 1"}), 400

    if motion not in (0, 1):
        return jsonify({"error": "motion must be 0 or 1"}), 400

    # optional angle (degrees) and distance (meters) and optional range_max
    try:
        angle = float(data.get("angle")) if data.get("angle") is not None else None
    except (TypeError, ValueError):
        angle = None
    try:
        distance = float(data.get("distance")) if data.get("distance") is not None else None
    except (TypeError, ValueError):
        distance = None
    try:
        range_max = float(data.get("range_max")) if data.get("range_max") is not None else None
    except (TypeError, ValueError):
        range_max = None

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        "INSERT INTO readings (motion, timestamp, angle, distance, range_max) VALUES (?, ?, ?, ?, ?)",
        (motion, timestamp, angle, distance, range_max)
    )
    conn.commit()
    state = conn.execute("SELECT state FROM device_state WHERE id = 1").fetchone()["state"]
    conn.close()

    # Return current output device state so the microcontroller can act on it immediately
    return jsonify({"status": "ok", "device_state": state})


# ---- Server -> Device: microcontroller polls this to know whether to turn output ON/OFF ----
@app.route("/api/state")
def get_state():
    conn = get_db()
    row = conn.execute("SELECT state, brightness FROM device_state WHERE id = 1").fetchone()
    conn.close()
    return jsonify({"device_state": row["state"], "brightness": row["brightness"]})


# ---- Dashboard: latest reading + device state (polled by the webpage) ----
@app.route("/api/latest")
def latest():
    conn = get_db()
    row = conn.execute("SELECT motion, timestamp, angle, distance, range_max FROM readings ORDER BY id DESC LIMIT 1").fetchone()
    state_row = conn.execute("SELECT state, brightness FROM device_state WHERE id = 1").fetchone()
    conn.close()

    if row is None:
        return jsonify({
            "motion": None,
            "timestamp": None,
            "device_state": state_row["state"],
            "brightness": state_row["brightness"],
            "angle": None,
            "distance": None,
            "range_max": None,
            "connected": False,
        })

    try:
        last_seen = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
        now = datetime.utcnow()
        connected = (now - last_seen).total_seconds() <= 30
    except (TypeError, ValueError):
        connected = False

    return jsonify({
        "motion": row["motion"] if connected else None,
        "timestamp": format_timestamp(row["timestamp"]) if row["timestamp"] else None,
        "device_state": state_row["state"],
        "brightness": state_row["brightness"],
        "angle": row["angle"],
        "distance": row["distance"],
        "range_max": row["range_max"],
        "connected": connected,
    })


# ---- Dashboard: historical readings table ----
@app.route("/api/history")
def history():
    conn = get_db()
    rows = conn.execute(
        "SELECT motion, timestamp, angle, distance, range_max FROM readings ORDER BY id DESC LIMIT 25"
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "motion": r["motion"],
            "timestamp": format_timestamp(r["timestamp"]),
            "angle": r["angle"],
            "distance": r["distance"],
            "range_max": r["range_max"]
        }
        for r in rows
    ])


# ---- Dashboard button -> updates the output device's target state ----
@app.route("/api/control", methods=["POST"])
def control():
    data = request.get_json(force=True, silent=True) or {}

    # Optional state update
    state = data.get("state")
    if state is not None:
        state = str(state).strip().upper()
        if state not in ("ON", "OFF"):
            return jsonify({"error": "invalid state"}), 400

    # Optional brightness update
    brightness = data.get("brightness")
    if brightness is not None:
        try:
            brightness = int(brightness)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid brightness"}), 400
        if brightness < 0 or brightness > 100:
            return jsonify({"error": "brightness must be 0-100"}), 400

    conn = get_db()
    if state is not None and brightness is not None:
        conn.execute("UPDATE device_state SET state = ?, brightness = ? WHERE id = 1", (state, brightness))
    elif state is not None:
        conn.execute("UPDATE device_state SET state = ? WHERE id = 1", (state,))
    elif brightness is not None:
        conn.execute("UPDATE device_state SET brightness = ? WHERE id = 1", (brightness,))
    else:
        conn.close()
        return jsonify({"error": "no update provided"}), 400

    conn.commit()
    row = conn.execute("SELECT state, brightness FROM device_state WHERE id = 1").fetchone()
    conn.close()
    return jsonify({"status": "ok", "device_state": row["state"], "brightness": row["brightness"]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
