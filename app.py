from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
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

def row_to_dict(c):
    if USE_PG:
        cols = [d[0] for d in c.description]
        row = c.fetchone()
        return dict(zip(cols, row)) if row else None
    row = c.fetchone()
    return dict(row) if row else None

def Q(n=1):
    ph = "%s" if USE_PG else "?"
    return ",".join([ph]*n)

def init_db():
    conn = get_db()
    c = conn.cursor()
    if USE_PG:
        c.execute("""CREATE TABLE IF NOT EXISTS reagents (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            vol_ml REAL NOT NULL, use_per_patient_ul REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS antibodies (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            vol_ul REAL NOT NULL, use_per_tube_ul REAL NOT NULL,
            staining_type TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS panels (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, staining_type TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS calendar_entries (
            id SERIAL PRIMARY KEY, entry_date TEXT NOT NULL UNIQUE,
            patient_count INTEGER NOT NULL DEFAULT 0)""")
    else:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS reagents (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                vol_ml REAL NOT NULL, use_per_patient_ul REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                vol_ul REAL NOT NULL, use_per_tube_ul REAL NOT NULL, staining_type TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS panels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, staining_type TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calendar_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL UNIQUE, patient_count INTEGER NOT NULL DEFAULT 0);
        """)

    ph = "%s" if USE_PG else "?"
    c.execute("SELECT COUNT(*) FROM reagents")
    if c.fetchone()[0] == 0:
        for r in [("FACS Lysing Solution 10X",100,500),("FIX & PERM (Fixation)",60,100),
                  ("FIX & PERM (Permeabilization)",60,100),("PBS 1X",500,2000)]:
            c.execute(f"INSERT INTO reagents (name,vol_ml,use_per_patient_ul) VALUES ({ph},{ph},{ph})",r)

    c.execute("SELECT COUNT(*) FROM antibodies")
    if c.fetchone()[0] == 0:
        for a in [("CD3 PE",500,7,"ext"),("CD4 FITC",500,7,"ext"),("CD8 APC",500,10,"ext"),
                  ("CD19 PerCP-Cy5.5",500,7,"ext"),("CD56 PE-Cy7",300,7,"ext"),
                  ("IFN-γ BV421",300,10,"int"),("IL-2 PE",300,7,"int"),("TNF-α APC",300,7,"int"),
                  ("Ki-67 FITC",200,7,"nuc"),("FoxP3 PE",200,10,"nuc")]:
            c.execute(f"INSERT INTO antibodies (name,vol_ul,use_per_tube_ul,staining_type) VALUES ({ph},{ph},{ph},{ph})",a)

    c.execute("SELECT COUNT(*) FROM panels")
    if c.fetchone()[0] == 0:
        for p in [("Panel Linfocitos T/B/NK","ext"),("Panel Citocinas Intracelulares","int"),
                  ("Panel Proliferación/Activación Nuclear","nuc")]:
            c.execute(f"INSERT INTO panels (name,staining_type) VALUES ({ph},{ph})",p)

    conn.commit()
    conn.close()

# ── Reagents ──────────────────────────────────────────────────────────────────
@app.route("/api/reagents", methods=["GET"])
def get_reagents():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM reagents ORDER BY name")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/reagents", methods=["POST"])
def add_reagent():
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"INSERT INTO reagents (name,vol_ml,use_per_patient_ul) VALUES ({ph},{ph},{ph})",
              (d["name"],d["vol_ml"],d["use_per_patient_ul"]))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/reagents/<int:rid>", methods=["PUT"])
def update_reagent(rid):
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"UPDATE reagents SET name={ph},vol_ml={ph},use_per_patient_ul={ph} WHERE id={ph}",
              (d["name"],d["vol_ml"],d["use_per_patient_ul"],rid))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/reagents/<int:rid>", methods=["DELETE"])
def delete_reagent(rid):
    ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"DELETE FROM reagents WHERE id={ph}",(rid,))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── Antibodies ────────────────────────────────────────────────────────────────
@app.route("/api/antibodies", methods=["GET"])
def get_antibodies():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM antibodies ORDER BY staining_type,name")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/antibodies", methods=["POST"])
def add_antibody():
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"INSERT INTO antibodies (name,vol_ul,use_per_tube_ul,staining_type) VALUES ({ph},{ph},{ph},{ph})",
              (d["name"],d["vol_ul"],d["use_per_tube_ul"],d["staining_type"]))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/antibodies/<int:aid>", methods=["PUT"])
def update_antibody(aid):
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"UPDATE antibodies SET name={ph},vol_ul={ph},use_per_tube_ul={ph},staining_type={ph} WHERE id={ph}",
              (d["name"],d["vol_ul"],d["use_per_tube_ul"],d["staining_type"],aid))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/antibodies/<int:aid>", methods=["DELETE"])
def delete_antibody(aid):
    ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"DELETE FROM antibodies WHERE id={ph}",(aid,))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── Panels ────────────────────────────────────────────────────────────────────
@app.route("/api/panels", methods=["GET"])
def get_panels():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM panels ORDER BY staining_type")
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/panels", methods=["POST"])
def add_panel():
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"INSERT INTO panels (name,staining_type) VALUES ({ph},{ph})",(d["name"],d["staining_type"]))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route("/api/panels/<int:pid>", methods=["DELETE"])
def delete_panel(pid):
    ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"DELETE FROM panels WHERE id={ph}",(pid,))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── Calendar ──────────────────────────────────────────────────────────────────
@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    year = request.args.get("year", date.today().year)
    month = request.args.get("month", date.today().month)
    ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute(f"SELECT entry_date,patient_count FROM calendar_entries WHERE entry_date LIKE {ph}",
              (f"{year}-{int(month):02d}-%",))
    result = rows_to_list(c); conn.close()
    return jsonify(result)

@app.route("/api/calendar", methods=["POST"])
def set_calendar():
    d = request.json; ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    if d["patient_count"] == 0:
        c.execute(f"DELETE FROM calendar_entries WHERE entry_date={ph}",(d["date"],))
    else:
        if USE_PG:
            c.execute("INSERT INTO calendar_entries (entry_date,patient_count) VALUES (%s,%s) ON CONFLICT(entry_date) DO UPDATE SET patient_count=EXCLUDED.patient_count",
                      (d["date"],d["patient_count"]))
        else:
            c.execute("INSERT INTO calendar_entries (entry_date,patient_count) VALUES (?,?) ON CONFLICT(entry_date) DO UPDATE SET patient_count=excluded.patient_count",
                      (d["date"],d["patient_count"]))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── Prediction ────────────────────────────────────────────────────────────────
@app.route("/api/prediction", methods=["GET"])
def get_prediction():
    days_ahead = int(request.args.get("days", 30))
    ph = "%s" if USE_PG else "?"
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM reagents"); reagents = rows_to_list(c)
    c.execute("SELECT * FROM antibodies"); antibodies = rows_to_list(c)
    c.execute("SELECT * FROM panels"); panels = rows_to_list(c)
    today = date.today()
    c.execute(f"SELECT entry_date,patient_count FROM calendar_entries WHERE entry_date >= {ph} AND entry_date <= {ph}",
              (str(today), str(today + timedelta(days=days_ahead))))
    cal_rows = rows_to_list(c); conn.close()

    calendar = {r["entry_date"]: r["patient_count"] for r in cal_rows}
    panels_by_type = {}
    for p in panels:
        panels_by_type.setdefault(p["staining_type"],[]).append(p)

    result = []
    for d in range(days_ahead):
        day = today + timedelta(days=d)
        key = str(day)
        pts = calendar.get(key, 0)
        if pts == 0: continue
        row = {"date":key,"weekday":day.strftime("%A"),"patients":pts,
               "total_tubes":pts*len(panels),"reagent_consumption":{},"antibody_consumption":{}}
        for r in reagents:
            row["reagent_consumption"][r["name"]] = round(pts*r["use_per_patient_ul"]/1000, 3)
        for ab in antibodies:
            ab_panels = panels_by_type.get(ab["staining_type"],[])
            row["antibody_consumption"][ab["name"]] = round(pts*len(ab_panels)*ab["use_per_tube_ul"], 1)
        result.append(row)

    reagent_empty = {}
    for r in reagents:
        cum = 0
        for row in result:
            cum += row["reagent_consumption"].get(r["name"],0)
            if cum >= r["vol_ml"] and r["name"] not in reagent_empty:
                reagent_empty[r["name"]] = (datetime.strptime(row["date"],"%Y-%m-%d").date()-today).days

    ab_empty = {}
    for ab in antibodies:
        cum = 0
        for row in result:
            cum += row["antibody_consumption"].get(ab["name"],0)/1000
            if cum >= ab["vol_ul"]/1000 and ab["name"] not in ab_empty:
                ab_empty[ab["name"]] = (datetime.strptime(row["date"],"%Y-%m-%d").date()-today).days

    reagent_cum = {r["name"]: round(sum(row["reagent_consumption"].get(r["name"],0) for row in result),3) for r in reagents}
    ab_cum = {ab["name"]: round(sum(row["antibody_consumption"].get(ab["name"],0) for row in result),1) for ab in antibodies}

    return jsonify({
        "daily": result,
        "reagent_summary": [{**r,"consumed_30d_ml":reagent_cum.get(r["name"],0),"days_until_empty":reagent_empty.get(r["name"])} for r in reagents],
        "antibody_summary": [{**ab,"consumed_30d_ul":ab_cum.get(ab["name"],0),"days_until_empty":ab_empty.get(ab["name"])} for ab in antibodies]
    })

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
