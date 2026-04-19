import psycopg2
import sqlite3

PG_URL = "postgresql://postgres:ZNzqtjqqkXLLRMoabtGHQXEXBwbdbCxn@mainline.proxy.rlwy.net:54061/railway"

print("Conectando a Railway...")
pg = psycopg2.connect(PG_URL)
pg_cur = pg.cursor()

print("Conectando a SQLite local...")
sq = sqlite3.connect("labflow.db")
sq_cur = sq.cursor()

# Reagents
pg_cur.execute("SELECT name, vol_ml, use_per_patient_ul, alert_threshold_days FROM reagents ORDER BY id")
rows = pg_cur.fetchall()
print(f"Reactivos encontrados: {len(rows)}")
for row in rows:
    sq_cur.execute("INSERT OR IGNORE INTO reagents (name,vol_ml,use_per_patient_ul,alert_threshold_days) VALUES (?,?,?,?)", row)

# Antibodies
pg_cur.execute("SELECT name, fluorochrome, vol_ul, use_per_test_ul, panel, staining_type, alert_threshold_days FROM antibodies ORDER BY id")
rows = pg_cur.fetchall()
print(f"Anticuerpos encontrados: {len(rows)}")
for row in rows:
    sq_cur.execute("INSERT OR IGNORE INTO antibodies (name,fluorochrome,vol_ul,use_per_test_ul,panel,staining_type,alert_threshold_days) VALUES (?,?,?,?,?,?,?)", row)

# Calendar
pg_cur.execute("SELECT entry_date, patient_count FROM calendar_entries")
rows = pg_cur.fetchall()
print(f"Entradas de calendario: {len(rows)}")
for row in rows:
    sq_cur.execute("INSERT OR IGNORE INTO calendar_entries (entry_date,patient_count) VALUES (?,?)", (str(row[0]), row[1]))

# Alert contacts
pg_cur.execute("SELECT email FROM alert_contacts")
rows = pg_cur.fetchall()
print(f"Contactos: {len(rows)}")
for row in rows:
    sq_cur.execute("INSERT OR IGNORE INTO alert_contacts (email) VALUES (?)", (row[0],))

sq.commit()
pg.close()
sq.close()
print("✓ Migración completada exitosamente")