from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, date
import json

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get("DATABASE_URL", "labflow.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS reagents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vol_ml REAL NOT NULL,
            use_per_patient_ul REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS antibodies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vol_ul REAL NOT NULL,
            use_per_tube_ul REAL NOT NULL,
            staining_type TEXT NOT NULL CHECK(staining_type IN ('ext','int','nuc')),
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            staining_type TEXT NOT NULL CHECK(staining_type IN ('ext','int','nuc'))
        );
        CREATE TABLE IF NOT EXISTS calendar_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL UNIQUE,
            patient_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            amount_used REAL NOT NULL,
            logged_at TEXT DEFAULT (datetime('now')),
            notes TEXT
        );
    """)
    # Seed default data if empty
    if c.execute("SELECT COUNT(*) FROM reagents").fetchone()[0] == 0:
        c.executemany("INSERT INTO reagents (name, vol_ml, use_per_patient_ul) VALUES (?,?,?)", [
            ("FACS Lysing Solution 10X", 100, 500),
            ("FIX & PERM (Fixation)", 60, 100),
            ("FIX & PERM (Permeabilization)", 60, 100),
            ("PBS 1X", 500, 2000),
        ])
    if c.execute("SELECT COUNT(*) FROM antibodies").fetchone()[0] == 0:
        c.executemany("INSERT INTO antibodies (name, vol_ul, use_per_tube_ul, staining_type) VALUES (?,?,?,?)", [
            ("CD3 PE", 500, 7, "ext"),
            ("CD4 FITC", 500, 7, "ext"),
            ("CD8 APC", 500, 10, "ext"),
            ("CD19 PerCP-Cy5.5", 500, 7, "ext"),
            ("CD56 PE-Cy7", 300, 7, "ext"),
            ("IFN-γ BV421", 300, 10, "int"),
            ("IL-2 PE", 300, 7, "int"),
            ("TNF-α APC", 300, 7, "int"),
            ("Ki-67 FITC", 200, 7, "nuc"),
            ("FoxP3 PE", 200, 10, "nuc"),
        ])
    if c.execute("SELECT COUNT(*) FROM panels").fetchone()[0] == 0:
        c.executemany("INSERT INTO panels (name, staining_type) VALUES (?,?)", [
            ("Panel Linfocitos T/B/NK", "ext"),
            ("Panel Citocinas Intracelulares", "int"),
            ("Panel Proliferación/Activación Nuclear", "nuc"),
        ])
    conn.commit()
    conn.close()

# ── Reagents ──────────────────────────────────────────────────────────────────
@app.route("/api/reagents", methods=["GET"])
def get_reagents():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reagents ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reagents", methods=["POST"])
def add_reagent():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO reagents (name, vol_ml, use_per_patient_ul) VALUES (?,?,?)",
                 (data["name"], data["vol_ml"], data["use_per_patient_ul"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/reagents/<int:rid>", methods=["PUT"])
def update_reagent(rid):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE reagents SET name=?, vol_ml=?, use_per_patient_ul=? WHERE id=?",
                 (data["name"], data["vol_ml"], data["use_per_patient_ul"], rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/reagents/<int:rid>", methods=["DELETE"])
def delete_reagent(rid):
    conn = get_db()
    conn.execute("DELETE FROM reagents WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Antibodies ────────────────────────────────────────────────────────────────
@app.route("/api/antibodies", methods=["GET"])
def get_antibodies():
    conn = get_db()
    rows = conn.execute("SELECT * FROM antibodies ORDER BY staining_type, name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/antibodies", methods=["POST"])
def add_antibody():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO antibodies (name, vol_ul, use_per_tube_ul, staining_type) VALUES (?,?,?,?)",
                 (data["name"], data["vol_ul"], data["use_per_tube_ul"], data["staining_type"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/antibodies/<int:aid>", methods=["PUT"])
def update_antibody(aid):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE antibodies SET name=?, vol_ul=?, use_per_tube_ul=?, staining_type=? WHERE id=?",
                 (data["name"], data["vol_ul"], data["use_per_tube_ul"], data["staining_type"], aid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/antibodies/<int:aid>", methods=["DELETE"])
def delete_antibody(aid):
    conn = get_db()
    conn.execute("DELETE FROM antibodies WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Panels ────────────────────────────────────────────────────────────────────
@app.route("/api/panels", methods=["GET"])
def get_panels():
    conn = get_db()
    rows = conn.execute("SELECT * FROM panels ORDER BY staining_type").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/panels", methods=["POST"])
def add_panel():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO panels (name, staining_type) VALUES (?,?)",
                 (data["name"], data["staining_type"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/panels/<int:pid>", methods=["DELETE"])
def delete_panel(pid):
    conn = get_db()
    conn.execute("DELETE FROM panels WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Calendar ──────────────────────────────────────────────────────────────────
@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    year = request.args.get("year", date.today().year)
    month = request.args.get("month", date.today().month)
    conn = get_db()
    rows = conn.execute(
        "SELECT entry_date, patient_count FROM calendar_entries WHERE strftime('%Y-%m', entry_date) = ?",
        (f"{year}-{int(month):02d}",)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/calendar", methods=["POST"])
def set_calendar():
    data = request.json
    conn = get_db()
    if data["patient_count"] == 0:
        conn.execute("DELETE FROM calendar_entries WHERE entry_date=?", (data["date"],))
    else:
        conn.execute("""INSERT INTO calendar_entries (entry_date, patient_count) VALUES (?,?)
                        ON CONFLICT(entry_date) DO UPDATE SET patient_count=excluded.patient_count""",
                     (data["date"], data["patient_count"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Prediction ────────────────────────────────────────────────────────────────
@app.route("/api/prediction", methods=["GET"])
def get_prediction():
    days_ahead = int(request.args.get("days", 30))
    conn = get_db()
    reagents = [dict(r) for r in conn.execute("SELECT * FROM reagents").fetchall()]
    antibodies = [dict(r) for r in conn.execute("SELECT * FROM antibodies").fetchall()]
    panels = [dict(r) for r in conn.execute("SELECT * FROM panels").fetchall()]

    from datetime import timedelta
    today = date.today()
    entries = conn.execute(
        "SELECT entry_date, patient_count FROM calendar_entries WHERE entry_date >= ? AND entry_date <= ?",
        (str(today), str(today + timedelta(days=days_ahead)))
    ).fetchall()
    conn.close()

    calendar = {r["entry_date"]: r["patient_count"] for r in entries}
    panels_by_type = {}
    for p in panels:
        panels_by_type.setdefault(p["staining_type"], []).append(p)

    result = []
    for d in range(days_ahead):
        day = today + timedelta(days=d)
        key = str(day)
        pts = calendar.get(key, 0)
        if pts == 0:
            continue
        total_tubes = pts * len(panels)
        row = {
            "date": key,
            "weekday": day.strftime("%A"),
            "patients": pts,
            "total_tubes": total_tubes,
            "reagent_consumption": {},
            "antibody_consumption": {}
        }
        for r in reagents:
            row["reagent_consumption"][r["name"]] = round(pts * r["use_per_patient_ul"] / 1000, 3)
        for ab in antibodies:
            ab_panels = panels_by_type.get(ab["staining_type"], [])
            tubes_for_ab = pts * len(ab_panels)
            row["antibody_consumption"][ab["name"]] = round(tubes_for_ab * ab["use_per_tube_ul"], 1)
        result.append(row)

    # Cumulative consumption and days-until-empty per item
    reagent_cumulative = {r["name"]: 0 for r in reagents}
    ab_cumulative = {ab["name"]: 0 for ab in antibodies}
    reagent_empty = {r["name"]: None for r in reagents}
    ab_empty = {ab["name"]: None for ab in antibodies}

    for row in result:
        for rname, used in row["reagent_consumption"].items():
            reagent_cumulative[rname] = round(reagent_cumulative[rname] + used, 3)
        for aname, used in row["antibody_consumption"].items():
            ab_cumulative[aname] = round(ab_cumulative[aname] + used, 1)

    for r in reagents:
        avail = r["vol_ml"]
        cum = 0
        for row in result:
            cum += row["reagent_consumption"].get(r["name"], 0)
            if cum >= avail and reagent_empty[r["name"]] is None:
                reagent_empty[r["name"]] = (datetime.strptime(row["date"], "%Y-%m-%d").date() - today).days

    for ab in antibodies:
        avail = ab["vol_ul"] / 1000
        cum = 0
        for row in result:
            cum += row["antibody_consumption"].get(ab["name"], 0) / 1000
            if cum >= avail and ab_empty[ab["name"]] is None:
                ab_empty[ab["name"]] = (datetime.strptime(row["date"], "%Y-%m-%d").date() - today).days

    return jsonify({
        "daily": result,
        "reagent_summary": [
            {**r, "consumed_30d_ml": reagent_cumulative.get(r["name"], 0),
             "days_until_empty": reagent_empty.get(r["name"])}
            for r in reagents
        ],
        "antibody_summary": [
            {**ab, "consumed_30d_ul": ab_cumulative.get(ab["name"], 0),
             "days_until_empty": ab_empty.get(ab["name"])}
            for ab in antibodies
        ]
    })

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
