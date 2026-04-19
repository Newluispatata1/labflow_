from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import smtplib
import json
from dotenv import load_dotenv
load_dotenv()
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date, timedelta

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

def get_db():
    if USE_PG:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect("labflow.db")
    conn.row_factory = sqlite3.Row
    return conn

def rows_to_list(c):
    if USE_PG:
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    return [dict(r) for r in c.fetchall()]

def Q():
    return "%s" if USE_PG else "?"

def init_db():
    conn = get_db()
    c = conn.cursor()
    ph = Q()
    if USE_PG:
        c.execute("""CREATE TABLE IF NOT EXISTS reagents (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            vol_ml REAL NOT NULL, use_per_patient_ul REAL NOT NULL,
            alert_threshold_days INTEGER DEFAULT 7)""")
        c.execute("""CREATE TABLE IF NOT EXISTS antibodies (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, fluorochrome TEXT,
            vol_ul REAL NOT NULL, use_per_test_ul REAL NOT NULL,
            panel TEXT NOT NULL, staining_type TEXT NOT NULL,
            alert_threshold_days INTEGER DEFAULT 7)""")
        c.execute("""CREATE TABLE IF NOT EXISTS calendar_entries (
            id SERIAL PRIMARY KEY, entry_date TEXT NOT NULL UNIQUE,
            patient_count INTEGER NOT NULL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS alert_contacts (
            id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE)""")
        c.execute("""CREATE TABLE IF NOT EXISTS alert_log (
            id SERIAL PRIMARY KEY,
            alert_key TEXT NOT NULL UNIQUE,
            sent_at TIMESTAMP DEFAULT NOW())""")
    else:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS reagents (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                vol_ml REAL NOT NULL, use_per_patient_ul REAL NOT NULL,
                alert_threshold_days INTEGER DEFAULT 7);
            CREATE TABLE IF NOT EXISTS antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                fluorochrome TEXT, vol_ul REAL NOT NULL,
                use_per_test_ul REAL NOT NULL, panel TEXT NOT NULL,
                staining_type TEXT NOT NULL,
                alert_threshold_days INTEGER DEFAULT 7);
            CREATE TABLE IF NOT EXISTS calendar_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL UNIQUE,
                patient_count INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS alert_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_key TEXT NOT NULL UNIQUE,
                sent_at TEXT DEFAULT (datetime('now')));
        """)

    # ── Seed reagents ──────────────────────────────────────────────────────
    # Volumes per patient derived from SOPs:
    # FACS Lysing: 1200 µL per 100 µL blood = 1200 µL/patient (each of 6 tubes gets lysis)
    # FIX 1X: 180 µL × 6 tubes = 1080 µL/patient
    # PERM 1X: 700 µL × 3 uses × 6 tubes = 12600 µL — but only tubes with intracelular/nuclear get PERM
    #   MM1 BFA, MM1 PMA, MM2, MM3 = 4 tubes × 700 × 3 = 8400 µL; + AF = 700×3 = 2100 → 10500 total
    # PBS 1X: 1000 µL wash per tube × 6 tubes = 6000 µL
    # Staining Buffer: 1000 µL × 2 washes × 6 tubes = 12000 µL
    c.execute("SELECT COUNT(*) FROM reagents")
    if c.fetchone()[0] == 0:
        reagents_seed = [
            ("FACS Lysing Solution 10X", 100.0, 7200,  7),   # 1200 µL × 6 tubes
            ("FIX 1X (True Nuclear Fix)", 60.0,  1080,  7),  # 180 µL × 6 tubes
            ("PERM 1X (True Nuclear Perm)", 100.0, 10500, 7),# 700×3×5 tubes (4 perm + AF)
            ("PBS 1X", 500.0, 6000, 7),                       # 1000 µL × 6 tubes
            ("Tampón de Tinción Celular", 500.0, 12000, 7),   # 1000 µL × 2 × 6
            ("Human TruStain FcX™", 1.0, 12, 14),             # 2 µL × 6 tubes
            ("BD Golgi Plug™ (Brefeldina A)", 1.0, 1, 14),    # 1 µL for MM1 PMA tube
            ("Cóctel Activación PMA/Ionomicina", 1.0, 1, 14), # 1 µL for MM1 PMA tube
        ]
        for r in reagents_seed:
            c.execute(f"INSERT INTO reagents (name,vol_ml,use_per_patient_ul,alert_threshold_days) VALUES ({ph},{ph},{ph},{ph})", r)

    # ── Seed antibodies from Master Mix ───────────────────────────────────
    c.execute("SELECT COUNT(*) FROM antibodies")
    if c.fetchone()[0] == 0:
        abs_seed = [
            # MM1 Extracelular (10 µL cocktail total per test, individual volumes)
            ("CD38",   "FITC",         500, 0.5, "MM1", "ext"),
            ("CD56",   "PE-Dazzle594", 500, 0.5, "MM1", "ext"),
            ("DNAM-1", "PerCP-Cy5.5",  500, 2.0, "MM1", "ext"),
            ("CD16",   "PECy7",        500, 0.5, "MM1", "ext"),
            ("CD4",    "APC",          500, 1.5, "MM1", "ext"),
            ("CD8",    "APC-A700",     500, 1.0, "MM1", "ext"),
            ("CD3",    "APC-A750",     500, 0.5, "MM1", "ext"),
            ("CD161",  "PB",           500, 0.5, "MM1", "ext"),
            ("HLA-DR", "KOr",          500, 1.0, "MM1", "ext"),
            ("CD25",   "BV605",        500, 1.0, "MM1", "ext"),
            ("CD137",  "BV650",        500, 1.0, "MM1", "ext"),
            # MM1 Intracelular (14 µL cocktail, applied to MM1 BFA y MM1 PMA)
            ("T-bet",  "PE",           500, 7.0, "MM1", "int"),
            ("IFN-γ",  "BV785",        500, 7.0, "MM1", "int"),
            # MM2 Extracelular (15.5 µL/test)
            ("CD45RA", "FITC",         500, 0.5, "MM2", "ext"),
            ("CD197",  "PE",           500, 0.5, "MM2", "ext"),
            ("CD28",   "PE-Dazzle594", 500, 5.0, "MM2", "ext"),
            ("CD279",  "PerCP-Cy5.5",  500, 1.0, "MM2", "ext"),
            ("CD27",   "PECy7",        500, 1.0, "MM2", "ext"),
            ("CD4",    "APC",          500, 1.5, "MM2", "ext"),
            ("CD8",    "APC-A700",     500, 1.0, "MM2", "ext"),
            ("CD3",    "APC-A750",     500, 0.5, "MM2", "ext"),
            ("CD294",  "PB",           500, 0.5, "MM2", "ext"),
            ("CD45",   "KOr",          500, 2.0, "MM2", "ext"),
            ("CD62L",  "BV605",        500, 1.0, "MM2", "ext"),
            ("CD196",  "BV650",        500, 1.5, "MM2", "ext"),
            # MM2 Intracelular (7 µL/test)
            ("CTLA-4", "BV785",        500, 7.0, "MM2", "int"),
            # MM3 Extracelular (11 µL/test)
            ("CD45RA", "FITC",         500, 0.5, "MM3", "ext"),
            ("CD197",  "PE",           500, 0.5, "MM3", "ext"),
            ("CD39",   "PE-Dazzle594", 500, 1.0, "MM3", "ext"),
            ("CD279",  "PerCP-Cy5.5",  500, 1.0, "MM3", "ext"),
            ("CD366",  "PECy7",        500, 1.0, "MM3", "ext"),
            ("CD4",    "APC",          500, 1.5, "MM3", "ext"),
            ("CD8",    "APC-A700",     500, 1.0, "MM3", "ext"),
            ("CD3",    "APC-A750",     500, 0.5, "MM3", "ext"),
            ("CD127",  "PB",           500, 1.0, "MM3", "ext"),
            ("CD45",   "KOr",          500, 2.0, "MM3", "ext"),
            ("CD25",   "BV605",        500, 1.0, "MM3", "ext"),
            # MM3 Intracelular (14 µL/test)
            ("FOXP3",  "BV650",        500, 7.0, "MM3", "int"),
            ("CTLA-4", "BV785",        500, 7.0, "MM3", "int"),
            # MMDC Extracelular (12 µL/test) — panel Células Dendríticas
            ("Lin neg","FITC",         500, 1.5, "MMDC","ext"),
            ("CD86",   "PE-Dazzle594", 500, 1.0, "MMDC","ext"),
            ("CD1c",   "PerCP-Cy5.5",  500, 2.0, "MMDC","ext"),
            ("CD11c",  "PECy7",        500, 1.5, "MMDC","ext"),
            ("CD370",  "APC",          500, 1.0, "MMDC","ext"),
            ("CD16",   "APC-A700",     500, 0.5, "MMDC","ext"),
            ("HLA-DR", "PB",           500, 2.0, "MMDC","ext"),
            ("CD45",   "KOr",          500, 2.0, "MMDC","ext"),
            ("CD83",   "BV605",        500, 1.0, "MMDC","ext"),
            ("CD80",   "BV650",        500, 1.0, "MMDC","ext"),
            ("Viab.",  "APC-A750",     500, 0.5, "MMDC","ext"),
            # MMDC Intracelular
            ("IL-12",  "PE",           500, 3.0, "MMDC","int"),
            ("CTLA-4", "BV785",        500, 5.0, "MMDC","int"),
        ]
        for a in abs_seed:
            c.execute(f"INSERT INTO antibodies (name,fluorochrome,vol_ul,use_per_test_ul,panel,staining_type) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})", a)

    conn.commit()
    conn.close()

# ── Helpers ───────────────────────────────────────────────────────────────────
def tubes_per_patient():
    """
    Per patient per day:
    MM1 S/E (SOP-001):  AF + MM1          = 2 tubes (extrac + intrac)
    MM1 Estimulado (SOP-004): AF + MM1 BFA + MM1 PMA = 3 tubes (but AF is shared)
    MM2 (SOP-002):      AF + MM2          = 2 tubes
    MM3 (SOP-003):      AF + MM3          = 2 tubes
    MMDC:               AF + MMDC         = 2 tubes
    AF is shared across all 4 SOPs → 1 AF tube total
    Total unique tubes: AF(1) + MM1(1) + MM1_BFA(1) + MM1_PMA(1) + MM2(1) + MM3(1) + MMDC(1) = 7
    """
    return 7

def calc_reagent_use(pts, reagent_name):
    """Calculate µL used per patient for a given reagent, based on SOP logic."""
    # All values in µL
    name = reagent_name.lower()
    if "lysing" in name or "facs" in name:
        # 1200 µL per tube. Tubes that get lysis: AF, MM1, MM1_BFA, MM1_PMA, MM2, MM3, MMDC = 7
        return pts * 1200 * 7
    elif "fix" in name:
        # 180 µL × 7 tubes
        return pts * 180 * 7
    elif "perm" in name:
        # 700 µL × 3 uses × tubes that get PERM
        # AF, MM1, MM1_BFA, MM1_PMA, MM2, MM3 = 6 tubes (MMDC no intracelular yet)
        return pts * 700 * 3 * 6
    elif "pbs" in name:
        # 1000 µL × 1 final wash × 7 tubes
        return pts * 1000 * 7
    elif "tampón" in name or "tampon" in name or "staining" in name or "buffer" in name:
        # 1000 µL × 2 wash steps × 7 tubes
        return pts * 1000 * 2 * 7
    elif "trustain" in name or "fcx" in name or "bloqueo" in name:
        # 2 µL × 7 tubes
        return pts * 2 * 7
    elif "golgi" in name or "brefeldina" in name:
        # 1 µL for MM1 BFA and MM1 PMA only = 2 tubes
        return pts * 1 * 2
    elif "pma" in name or "activaci" in name or "ionomicina" in name:
        # 1 µL for MM1 PMA tube only
        return pts * 1 * 1
    else:
        return pts * 500  # generic fallback

def calc_ab_use_per_patient(ab):
    """
    Calculate µL of antibody used per patient.
    MM1 ext: applied to MM1_SE + MM1_BFA + MM1_PMA = 3 tubes
    MM1 int: applied to MM1_SE + MM1_BFA + MM1_PMA = 3 tubes
    MM2 ext/int: applied to MM2 = 1 tube
    MM3 ext/int: applied to MM3 = 1 tube
    MMDC ext/int: applied to MMDC = 1 tube
    """
    panel = ab["panel"]
    tubes = {"MM1": 3, "MM2": 1, "MM3": 1, "MMDC": 1}.get(panel, 1)
    return ab["use_per_test_ul"] * tubes

# ── Reagents API ──────────────────────────────────────────────────────────────
@app.route("/api/reagents", methods=["GET"])
def get_reagents():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM reagents ORDER BY name")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/reagents", methods=["POST"])
def add_reagent():
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute(f"INSERT INTO reagents (name,vol_ml,use_per_patient_ul,alert_threshold_days) VALUES ({ph},{ph},{ph},{ph})",
              (d["name"], d["vol_ml"], d.get("use_per_patient_ul",0), d.get("alert_threshold_days",7)))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/reagents/<int:rid>", methods=["PUT"])
def update_reagent(rid):
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute(f"UPDATE reagents SET name={ph},vol_ml={ph},use_per_patient_ul={ph},alert_threshold_days={ph} WHERE id={ph}",
              (d["name"], d["vol_ml"], d.get("use_per_patient_ul",0), d.get("alert_threshold_days",7), rid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/reagents/<int:rid>", methods=["DELETE"])
def delete_reagent(rid):
    conn = get_db(); c = conn.cursor(); ph = Q()
    c.execute(f"DELETE FROM reagents WHERE id={ph}", (rid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── Antibodies API ────────────────────────────────────────────────────────────
@app.route("/api/antibodies", methods=["GET"])
def get_antibodies():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM antibodies ORDER BY panel, staining_type, name")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/antibodies", methods=["POST"])
def add_antibody():
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute(f"INSERT INTO antibodies (name,fluorochrome,vol_ul,use_per_test_ul,panel,staining_type,alert_threshold_days) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
              (d["name"], d.get("fluorochrome",""), d["vol_ul"], d["use_per_test_ul"],
               d["panel"], d["staining_type"], d.get("alert_threshold_days",7)))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/antibodies/<int:aid>", methods=["PUT"])
def update_antibody(aid):
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute(f"UPDATE antibodies SET name={ph},fluorochrome={ph},vol_ul={ph},use_per_test_ul={ph},panel={ph},staining_type={ph},alert_threshold_days={ph} WHERE id={ph}",
              (d["name"], d.get("fluorochrome",""), d["vol_ul"], d["use_per_test_ul"],
               d["panel"], d["staining_type"], d.get("alert_threshold_days",7), aid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/antibodies/<int:aid>", methods=["DELETE"])
def delete_antibody(aid):
    conn = get_db(); c = conn.cursor(); ph = Q()
    c.execute(f"DELETE FROM antibodies WHERE id={ph}", (aid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── Calendar API ──────────────────────────────────────────────────────────────
@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    year = request.args.get("year", date.today().year)
    month = request.args.get("month", date.today().month)
    ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute(f"SELECT entry_date,patient_count FROM calendar_entries WHERE entry_date LIKE {ph}",
              (f"{year}-{int(month):02d}-%",))
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/calendar", methods=["POST"])
def set_calendar():
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    if d["patient_count"] == 0:
        c.execute(f"DELETE FROM calendar_entries WHERE entry_date={ph}", (d["date"],))
    else:
        if USE_PG:
            c.execute("INSERT INTO calendar_entries (entry_date,patient_count) VALUES (%s,%s) ON CONFLICT(entry_date) DO UPDATE SET patient_count=EXCLUDED.patient_count",
                      (d["date"], d["patient_count"]))
        else:
            c.execute("INSERT INTO calendar_entries (entry_date,patient_count) VALUES (?,?) ON CONFLICT(entry_date) DO UPDATE SET patient_count=excluded.patient_count",
                      (d["date"], d["patient_count"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── Alerts API ────────────────────────────────────────────────────────────────
@app.route("/api/alerts/contacts", methods=["GET"])
def get_contacts():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM alert_contacts ORDER BY email")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/alerts/contacts", methods=["POST"])
def add_contact():
    d = request.json; ph = Q()
    conn = get_db(); c = conn.cursor()
    try:
        c.execute(f"INSERT INTO alert_contacts (email) VALUES ({ph})", (d["email"],))
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/alerts/contacts/<int:cid>", methods=["DELETE"])
def delete_contact(cid):
    conn = get_db(); c = conn.cursor(); ph = Q()
    c.execute(f"DELETE FROM alert_contacts WHERE id={ph}", (cid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── Prediction API ────────────────────────────────────────────────────────────
@app.route("/api/prediction", methods=["GET"])
def get_prediction():
    days_ahead = int(request.args.get("days", 30))
    ph = Q()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM reagents"); reagents = rows_to_list(c)
    c.execute("SELECT * FROM antibodies"); antibodies = rows_to_list(c)
    today = date.today()
    c.execute(f"SELECT entry_date,patient_count FROM calendar_entries WHERE entry_date >= {ph} AND entry_date <= {ph}",
              (str(today), str(today + timedelta(days=days_ahead))))
    cal_rows = rows_to_list(c); conn.close()

    calendar = {r["entry_date"]: r["patient_count"] for r in cal_rows}

    daily = []
    for d in range(days_ahead):
        day = today + timedelta(days=d)
        key = str(day)
        pts = calendar.get(key, 0)
        if pts == 0:
            continue
        row = {
            "date": key,
            "weekday": day.strftime("%A"),
            "patients": pts,
            "total_tubes": pts * tubes_per_patient(),
            "reagent_consumption": {},
            "antibody_consumption": {}
        }
        for r in reagents:
            used_ul = calc_reagent_use(pts, r["name"])
            row["reagent_consumption"][r["name"]] = round(used_ul / 1000, 3)
        for ab in antibodies:
            used_ul = calc_ab_use_per_patient(ab) * pts
            row["antibody_consumption"][ab["name"] + " " + ab["panel"]] = round(used_ul, 1)
        daily.append(row)

    # Cumulative sums
    reagent_cum = {r["name"]: 0.0 for r in reagents}
    ab_cum = {ab["name"] + " " + ab["panel"]: 0.0 for ab in antibodies}
    for row in daily:
        for k, v in row["reagent_consumption"].items():
            reagent_cum[k] = round(reagent_cum.get(k, 0) + v, 3)
        for k, v in row["antibody_consumption"].items():
            ab_cum[k] = round(ab_cum.get(k, 0) + v, 1)

    # Days until empty — uses calendar projection first, falls back to rate-based estimate
    def days_until_empty_reagent(r):
        avail_ml = r["vol_ml"]
        cum = 0.0
        for row in daily:
            cum += row["reagent_consumption"].get(r["name"], 0)
            if cum >= avail_ml:
                return (datetime.strptime(row["date"], "%Y-%m-%d").date() - today).days
        # Fallback: use average daily consumption rate from calendar
        total_days = len(daily)
        if total_days > 0:
            total_consumed = sum(row["reagent_consumption"].get(r["name"], 0) for row in daily)
            if total_consumed > 0:
                rate_per_day = total_consumed / (days_ahead)
                return int(avail_ml / rate_per_day)
        # Last resort: use use_per_patient_ul directly (assume 1 patient/day avg)
        if r["use_per_patient_ul"] > 0:
            avail_ul = r["vol_ml"] * 1000
            return int(avail_ul / r["use_per_patient_ul"])
        return None

    def days_until_empty_ab(ab):
        key = ab["name"] + " " + ab["panel"]
        avail_ul = ab["vol_ul"]
        cum = 0.0
        for row in daily:
            cum += row["antibody_consumption"].get(key, 0)
            if cum >= avail_ul:
                return (datetime.strptime(row["date"], "%Y-%m-%d").date() - today).days
        # Fallback: rate-based estimate
        total_days = len(daily)
        if total_days > 0:
            total_consumed = sum(row["antibody_consumption"].get(key, 0) for row in daily)
            if total_consumed > 0:
                rate_per_day = total_consumed / (days_ahead)
                return int(avail_ul / rate_per_day)
        # Last resort: use use_per_test_ul × tubes per patient
        if ab["use_per_test_ul"] > 0:
            tubes = {"MM1": 3, "MM2": 1, "MM3": 1, "MMDC": 1}.get(ab["panel"], 1)
            return int(avail_ul / (ab["use_per_test_ul"] * tubes))
        return None

    reagent_summary = []
    for r in reagents:
        d_empty = days_until_empty_reagent(r)
        reagent_summary.append({
            **r,
            "consumed_30d_ml": reagent_cum.get(r["name"], 0),
            "days_until_empty": d_empty,
            "alert": d_empty is not None and d_empty <= 21
        })

    ab_summary = []
    for ab in antibodies:
        key = ab["name"] + " " + ab["panel"]
        d_empty = days_until_empty_ab(ab)
        ab_summary.append({
            **ab,
            "consumed_30d_ul": ab_cum.get(key, 0),
            "days_until_empty": d_empty,
            "alert": d_empty is not None and d_empty <= 21
        })

    alerts = [
        {"type": "reagent", "name": r["name"], "days": r["days_until_empty"],
         "threshold": r["alert_threshold_days"]}
        for r in reagent_summary if r["alert"]
    ] + [
        {"type": "antibody", "name": ab["name"], "panel": ab["panel"],
         "days": ab["days_until_empty"], "threshold": ab["alert_threshold_days"]}
        for ab in ab_summary if ab["alert"]
    ]

    return jsonify({
        "daily": daily,
        "reagent_summary": reagent_summary,
        "antibody_summary": ab_summary,
        "alerts": sorted(alerts, key=lambda x: x["days"] or 999),
        "tubes_per_patient": tubes_per_patient()
    })

@app.route("/")
def index():
    return render_template("index.html")


# ── Email notifications ───────────────────────────────────────────────────────
def send_alert_email(alerts, contacts):
    gmail_user = os.environ.get('GMAIL_USER', '')
    gmail_pass = os.environ.get('GMAIL_APP_PASSWORD', '')
    if not gmail_user or not gmail_pass or not contacts:
        return False, 'Email not configured'

    alert_key = '|'.join(sorted([
        f"{a['type']}:{a['name']}:{a.get('panel','')}"
        for a in alerts
    ]))

    ph = '%s' if USE_PG else '?'
    conn = get_db(); c = conn.cursor()
    c.execute(f'SELECT id FROM alert_log WHERE alert_key={ph}', (alert_key,))
    already_sent = c.fetchone()
    if already_sent:
        conn.close()
        return False, 'Already notified for this alert set'

    rows_html = ''
    for a in alerts:
        color = '#f87171' if (a['days'] or 99) <= 7 else '#fbbf24'
        item = a['name'] + (f' ({a["panel"]})' if a.get('panel') else '')
        tipo = 'Reactivo' if a['type'] == 'reagent' else 'Anticuerpo'
        rows_html += (
            f'<tr>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #2a2a3e">{item}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #2a2a3e;color:#9ca3af">{tipo}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #2a2a3e">'
            f'<span style="background:{color}22;color:{color};padding:3px 10px;border-radius:20px;font-size:12px;font-family:monospace">'
            f'~{a["days"]}d restantes</span></td></tr>'
        )

    html_body = (
        '<div style="font-family:Arial,sans-serif;background:#0e0f14;color:#e8eaf0;padding:32px;max-width:600px;margin:0 auto;border-radius:12px">'
        '<div style="margin-bottom:24px"><span style="font-size:24px">🧪</span>'
        '<span style="font-size:20px;font-weight:600;margin-left:10px">LabFlow — Immunocine</span>'
        '<div style="font-size:13px;color:#6b7280;margin-top:4px">Alerta de reabastecimiento</div></div>'
        f'<p style="color:#9ca3af;font-size:14px;margin-bottom:20px">'
        f'{len(alerts)} item(s) próximos a agotarse según el calendario de pacientes:</p>'
        '<table style="width:100%;border-collapse:collapse;background:#16181f;border-radius:8px;overflow:hidden">'
        '<thead><tr style="background:#1e2029">'
        '<th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280">ITEM</th>'
        '<th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280">TIPO</th>'
        '<th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280">ESTADO</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>'
        '<p style="color:#6b7280;font-size:12px;margin-top:20px">'
        'Mensaje automático de LabFlow. Ingresa a la app para más detalles.</p></div>'
    )

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'⚠ LabFlow — {len(alerts)} alerta(s) de reabastecimiento'
        msg['From'] = gmail_user
        msg['To'] = ', '.join(contacts)
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, contacts, msg.as_string())
        c.execute(f'INSERT INTO alert_log (alert_key) VALUES ({ph})', (alert_key,))
        conn.commit()
        conn.close()
        return True, 'Email enviado correctamente'
    except Exception as e:
        conn.close()
        return False, str(e)


@app.route('/api/notify', methods=['POST'])
def trigger_notify():
    data = request.json or {}
    alerts = data.get('alerts', [])
    if not alerts:
        return jsonify({'sent': False, 'reason': 'Sin alertas activas'})
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT email FROM alert_contacts ORDER BY email')
    rows = c.fetchall()
    contacts = [r['email'] if isinstance(r, dict) else r[0] for r in rows]
    conn.close()
    if not contacts:
        return jsonify({'sent': False, 'reason': 'Sin contactos configurados'})
    sent, reason = send_alert_email(alerts, contacts)
    return jsonify({'sent': sent, 'reason': reason})


@app.route('/api/alerts/test', methods=['POST'])
def test_email():
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT email FROM alert_contacts ORDER BY email')
    rows = c.fetchall()
    contacts = [r['email'] if isinstance(r, dict) else r[0] for r in rows]
    conn.close()
    if not contacts:
        return jsonify({'sent': False, 'reason': 'No hay contactos configurados'})
    gmail_user = os.environ.get('GMAIL_USER', '')
    gmail_pass = os.environ.get('GMAIL_APP_PASSWORD', '')
    if not gmail_user or not gmail_pass:
        return jsonify({'sent': False, 'reason': 'Variables GMAIL_USER y GMAIL_APP_PASSWORD no configuradas en Railway'})
    test_alerts = [{'type': 'reagent', 'name': 'Email de prueba — LabFlow', 'days': 5, 'panel': ''}]
    # Clear log for test key so it always sends
    ph = '%s' if USE_PG else '?'
    test_key = 'reagent:Email de prueba — LabFlow:'
    conn2 = get_db(); c2 = conn2.cursor()
    c2.execute(f'DELETE FROM alert_log WHERE alert_key={ph}', (test_key,))
    conn2.commit(); conn2.close()
    sent, reason = send_alert_email(test_alerts, contacts)
    return jsonify({'sent': sent, 'reason': reason})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

