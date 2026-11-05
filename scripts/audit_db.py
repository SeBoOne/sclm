#!/usr/bin/env python3
"""audit_db.py — liest die SCLM-DB (Pfadlogik wie server.py) und meldet Zeilen,
deren qty / scu / sale_revenue / total_revenue außerhalb der Härtungsgrenzen
aus server.py liegen. Schreibt nichts (read-only).

Start:  python scripts/audit_db.py            (DATA_DIR wie beim Server setzen)
Exit:   0 = alles innerhalb der Grenzen, 1 = Ausreißer gefunden, 2 = DB nicht gefunden.
"""
import os, sqlite3, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # Repo-Root (Scripts/Ordner)
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE / "instance")))
DB = DATA_DIR / "data.db"

# Grenzen — bewusst dupliziert zu server.py, damit das Audit auch bei deren
# Anpassung unabhängig prüfbar bleibt (gleiche Standardwerte).
QTY_MIN, QTY_MAX = 1, 100_000
SCU_MIN, SCU_MAX = 0, 1_000_000_000
REVENUE_MIN, REVENUE_MAX = 0, 1_000_000_000_000

def _violates(v, lo, hi):
    if v is None:
        return False  # null ist erlaubt (leerer Wert)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return True  # nicht-numerisch gespeichert
    if v != v or v in (float("inf"), float("-inf")):
        return True  # NaN/Inf
    return v < lo or v > hi

def main():
    if not DB.exists():
        print(f"DB nicht gefunden: {DB}")
        return 2
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    bad = 0

    checks = [
        ("loot.qty", "SELECT id, name, qty FROM loot", "qty", QTY_MIN, QTY_MAX),
        ("loot.sale_revenue", "SELECT id, name, sale_revenue FROM loot", "sale_revenue", REVENUE_MIN, REVENUE_MAX),
        ("commodities.scu", "SELECT id, name, scu FROM commodities", "scu", SCU_MIN, SCU_MAX),
        ("sessions.total_revenue", "SELECT id, name, total_revenue FROM sessions", "total_revenue", REVENUE_MIN, REVENUE_MAX),
    ]
    for label, sql, col, lo, hi in checks:
        for row in con.execute(sql):
            v = row[col]
            if _violates(v, lo, hi):
                bad += 1
                print(f"AUSREISSER {label}: id={row['id']} name={row['name']!r} wert={v!r} (Grenze {lo}..{hi})")
    con.close()
    if bad:
        print(f"\n{bad} fehlerhafte Zeile(n) gefunden — geschrieben wurde nichts.")
        return 1
    print("OK — alle qty/scu/sale_revenue/total_revenue-Werte innerhalb der Grenzen.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
