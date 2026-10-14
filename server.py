#!/usr/bin/env python3
"""SCLM — Web Server. Start: python server.py"""
import sqlite3, os, json, random, string, re, sys, secrets, urllib.request
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

BASE = Path(__file__).parent
# In Docker: store data.db in /data volume; locally next to script
_data_dir = Path(os.environ.get("DATA_DIR", str(BASE)))
DB = _data_dir / "data.db"
app  = Flask(__name__, static_folder=str(BASE), static_url_path="")
app.static_folder = str(BASE)  # serves /static/ automatically via Flask defaults

# Explicit static subfolder for favicons
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(BASE / "static"), filename)
CORS(app)

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def print_startup_info():
    try:
        port = os.environ.get("PORT", "5000")
        sec = get_admin_secret()
        banner = "="*60
        print(f"\n{banner}")
        print(f"  SCLM — Star Citizen Loot Manager")
        print(f"{banner}")
        print(f"  URL:          http://localhost:{port}")
        print(f"{banner}")
        print(f"  ADMIN SECRET: {sec}")
        print(f"  Admin-URL:    http://localhost:{port}/#admin?secret={sec}")
        print(f"{banner}\n", flush=True)
    except Exception:
        pass

def init_db():
    with get_db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL,
            admin_code TEXT NOT NULL UNIQUE, join_code TEXT NOT NULL UNIQUE,
            max_wishes INTEGER NOT NULL DEFAULT 3,
            locked INTEGER NOT NULL DEFAULT 0,
            raffle_locked INTEGER NOT NULL DEFAULT 0,
            commodities_locked INTEGER NOT NULL DEFAULT 0,
            raffle_done INTEGER NOT NULL DEFAULT 0,
            total_revenue REAL,
            image_url TEXT
        );
        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL,
            added_by TEXT NOT NULL DEFAULT 'admin',
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS wishes (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            participant_id TEXT NOT NULL, loot_id TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
            FOREIGN KEY(loot_id) REFERENCES loot(id) ON DELETE CASCADE,
            UNIQUE(participant_id, loot_id)
        );
        CREATE TABLE IF NOT EXISTS no_interest (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            participant_id TEXT NOT NULL, loot_id TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
            FOREIGN KEY(loot_id) REFERENCES loot(id) ON DELETE CASCADE,
            UNIQUE(participant_id, loot_id)
        );
        CREATE TABLE IF NOT EXISTS loot (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1, type TEXT, grade TEXT, size TEXT,
            loot_key TEXT NOT NULL,
            for_sale INTEGER NOT NULL DEFAULT 0,
            sale_revenue REAL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS commodities (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL,
            scu REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS raffle_results (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            participant_id TEXT NOT NULL, participant_name TEXT NOT NULL,
            won_json TEXT NOT NULL DEFAULT '[]',
            won_by_wish INTEGER NOT NULL DEFAULT 0,
            waived INTEGER NOT NULL DEFAULT 0,
            collected INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS item_db (
            loot_key TEXT PRIMARY KEY, name TEXT NOT NULL,
            type TEXT, grade TEXT, size TEXT
        );
        CREATE TABLE IF NOT EXISTS commodity_db (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS participant_db (name TEXT PRIMARY KEY);
        """)
        # migrations for existing DBs
        for col, dflt in [("total_revenue","REAL"), ("for_sale","INTEGER NOT NULL DEFAULT 0"),
                          ("sale_revenue","REAL")]:
            try:
                if col in ("for_sale","sale_revenue"):
                    con.execute(f"ALTER TABLE loot ADD COLUMN {col} {dflt}")
                else:
                    con.execute(f"ALTER TABLE sessions ADD COLUMN {col} {dflt}")
            except: pass
        try: con.execute("CREATE TABLE IF NOT EXISTS no_interest (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, participant_id TEXT NOT NULL, loot_id TEXT NOT NULL, UNIQUE(participant_id,loot_id))")
        except: pass
        try: con.execute("ALTER TABLE sessions ADD COLUMN image_url TEXT")
        except: pass
        try: con.execute("ALTER TABLE sessions ADD COLUMN raffle_locked INTEGER NOT NULL DEFAULT 0")
        except: pass
        try: con.execute("ALTER TABLE sessions ADD COLUMN commodities_locked INTEGER NOT NULL DEFAULT 0")
        except: pass
        try: con.execute("CREATE TABLE IF NOT EXISTS commodity_db (name TEXT PRIMARY KEY)")
        except: pass
        row = con.execute("SELECT value FROM config WHERE key='admin_secret'").fetchone()
        if not row:
            con.execute("INSERT INTO config(key,value) VALUES('admin_secret',?)", (secrets.token_hex(16),))
        if not con.execute("SELECT 1 FROM config WHERE key='setup_viewed'").fetchone():
            con.execute("INSERT INTO config(key,value) VALUES('setup_viewed','0')")

def get_admin_secret():
    with get_db() as con:
        return con.execute("SELECT value FROM config WHERE key='admin_secret'").fetchone()["value"]

init_db()
print_startup_info()

# ── helpers ───────────────────────────────────────────────────────────────────
def uid(): return ''.join(random.choices(string.ascii_lowercase+string.digits, k=8))
def code6():
    while True:
        c = ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
        with get_db() as con:
            if not con.execute("SELECT 1 FROM sessions WHERE admin_code=? OR join_code=?",(c,c)).fetchone():
                return c
def loot_key(name,typ,grade,size): return "|".join([name.lower().strip(),typ or "",grade or "",size or ""])
def row_to_dict(r): return dict(r) if r else None
def rows_to_list(r): return [dict(x) for x in r]
def is_admin(s,code): return s and s["admin_code"]==code.upper()

def load_session(sid_or_code, by_code=False):
    with get_db() as con:
        if by_code:
            s = row_to_dict(con.execute(
                "SELECT * FROM sessions WHERE admin_code=? OR join_code=?",
                (sid_or_code.upper(), sid_or_code.upper())).fetchone())
        else:
            s = row_to_dict(con.execute("SELECT * FROM sessions WHERE id=?",(sid_or_code,)).fetchone())
        if not s: return None
        s["participants"] = rows_to_list(con.execute(
            "SELECT * FROM participants WHERE session_id=? ORDER BY name COLLATE NOCASE",(s["id"],)).fetchall())
        s["loot"] = rows_to_list(con.execute(
            "SELECT * FROM loot WHERE session_id=? ORDER BY name COLLATE NOCASE",(s["id"],)).fetchall())
        for l in s["loot"]:
            l["wish_count"] = con.execute("SELECT COUNT(*) FROM wishes WHERE loot_id=?",(l["id"],)).fetchone()[0]
        for p in s["participants"]:
            p["wishes"] = [r["loot_id"] for r in con.execute(
                "SELECT loot_id FROM wishes WHERE participant_id=?",(p["id"],)).fetchall()]
            p["no_interest"] = [r["loot_id"] for r in con.execute(
                "SELECT loot_id FROM no_interest WHERE participant_id=?",(p["id"],)).fetchall()]
        s["commodities"] = rows_to_list(con.execute(
            "SELECT * FROM commodities WHERE session_id=? ORDER BY name COLLATE NOCASE",(s["id"],)).fetchall())
        if s["raffle_done"]:
            results = rows_to_list(con.execute(
                "SELECT * FROM raffle_results WHERE session_id=?",(s["id"],)).fetchall())
            for r in results: r["won"]=json.loads(r["won_json"])
            s["results"] = results
        else:
            s["results"] = []
        # totals
        total_scu = sum(c["scu"] for c in s["commodities"])
        sale_rev  = sum((l["sale_revenue"] or 0) for l in s["loot"] if l.get("for_sale") and l.get("sale_revenue"))
        base_rev  = s.get("total_revenue") or 0
        s["commodity_summary"] = {
            "total_scu": total_scu,
            "total_revenue": (base_rev + sale_rev) if (base_rev or sale_rev) else None,
            "sale_revenue": sale_rev,
            "count": len(s["commodities"])
        }
        # raffle mode: 'wish' or 'no_interest'
        total_items = sum(l["qty"] for l in s["loot"] if not l.get("for_sale"))
        s["raffle_mode"] = "no_interest" if total_items < len(s["participants"]) else "wish"
        s["raffle_locked"] = bool(s.get("raffle_locked", 0))
        s["commodities_locked"] = bool(s.get("commodities_locked", 0))
    return s

# ── aggregate stats ───────────────────────────────────────────────────────────
@app.route("/api/stats")
def aggregate_stats():
    with get_db() as con:
        total_loot = con.execute(
            "SELECT COALESCE(SUM(qty),0) FROM loot WHERE for_sale=0").fetchone()[0]
        # Count total individual items won (sum of json array lengths)
        rr_rows = con.execute("SELECT won_json FROM raffle_results").fetchall()
        import json as _json
        total_loot_raffled = sum(len(_json.loads(r[0])) for r in rr_rows)
        total_scu = con.execute(
            "SELECT COALESCE(SUM(scu),0) FROM commodities").fetchone()[0]
        total_revenue_wars = con.execute(
            "SELECT COALESCE(SUM(total_revenue),0) FROM sessions WHERE total_revenue IS NOT NULL").fetchone()[0]
        total_revenue_sale = con.execute(
            "SELECT COALESCE(SUM(sale_revenue),0) FROM loot WHERE for_sale=1 AND sale_revenue IS NOT NULL").fetchone()[0]
        session_count = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        participant_count = con.execute("SELECT COUNT(DISTINCT name) FROM participants").fetchone()[0]
    return jsonify({
        "total_loot": total_loot,
        "total_loot_raffled": total_loot_raffled,
        "total_scu": total_scu,
        "total_revenue": (total_revenue_wars or 0) + (total_revenue_sale or 0),
        "session_count": session_count,
        "participant_count": participant_count,
    })

# ── session ───────────────────────────────────────────────────────────────────
@app.route("/api/sessions")
def list_sessions():
    secret = request.args.get("secret","")
    is_super = (secret == get_admin_secret())
    with get_db() as con:
        rows = rows_to_list(con.execute(
            "SELECT id,name,created,join_code,admin_code,locked,raffle_locked,commodities_locked,raffle_done,total_revenue,image_url FROM sessions ORDER BY created DESC").fetchall())
    result = []
    for s in rows:
        with get_db() as con:
            pc = con.execute("SELECT COUNT(*) FROM participants WHERE session_id=?",(s["id"],)).fetchone()[0]
            lc = con.execute("SELECT COALESCE(SUM(qty),0) FROM loot WHERE session_id=? AND for_sale=0",(s["id"],)).fetchone()[0]
            comm = rows_to_list(con.execute("SELECT scu FROM commodities WHERE session_id=?",(s["id"],)).fetchall())
            sale = con.execute("SELECT COALESCE(SUM(sale_revenue),0) FROM loot WHERE session_id=? AND for_sale=1",(s["id"],)).fetchone()[0]
        total_scu = sum(c["scu"] for c in comm)
        total_rev = (s["total_revenue"] or 0) + (sale or 0)
        result.append({
            "id":s["id"],"name":s["name"],"created":s["created"],
            "join_code":s["join_code"],
            "admin_code":s["admin_code"] if is_super else None,
            "locked":bool(s["locked"]),"raffle_done":bool(s["raffle_done"]),
            "participant_count":pc,"loot_count":lc,
            "commodity_scu":total_scu if comm else None,
            "commodity_revenue":total_rev if total_rev else None,
            "image_url":s.get("image_url"),
        })
    return jsonify(result)

@app.route("/api/session/create", methods=["POST"])
def create_session():
    data=request.json; name=(data.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    sid=uid(); ac=code6(); jc=code6()
    image_url = (data.get("image_url") or "").strip() or None
    with get_db() as con:
        con.execute("INSERT INTO sessions(id,name,created,admin_code,join_code,max_wishes,image_url) VALUES(?,?,?,?,?,?,?)",
            (sid,name,datetime.now().strftime("%d.%m.%Y"),ac,jc,int(data.get("max_wishes",3)),image_url))
    return jsonify({"id":sid,"admin_code":ac,"join_code":jc})

@app.route("/api/session/<code>")
def get_session(code):
    s=load_session(code,by_code=True)
    if not s: return jsonify({"error":"Code ungültig"}),404
    admin=is_admin(s,code)
    s["is_admin"]=admin
    if not admin: s.pop("admin_code",None)
    return jsonify(s)

@app.route("/api/session/<sid>/settings", methods=["PATCH"])
def update_settings(sid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    if not is_admin(s,code) and data.get("secret","")!=get_admin_secret():
        return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con:
        if "max_wishes"     in data: con.execute("UPDATE sessions SET max_wishes=? WHERE id=?",(int(data["max_wishes"]),sid))
        if "locked" in data:
            if data["locked"]:  # anyone authorised can lock
                con.execute("UPDATE sessions SET locked=1 WHERE id=?",(sid,))
            elif data.get("secret","") == get_admin_secret():  # only superadmin can unlock
                con.execute("UPDATE sessions SET locked=0 WHERE id=?",(sid,))
            else:
                return jsonify({"error":"Nur ein Administrator kann entsperren"}),403
        if "name"           in data: con.execute("UPDATE sessions SET name=? WHERE id=?",(data["name"].strip(),sid))
        if "total_revenue"  in data:
            rv=data["total_revenue"]
            con.execute("UPDATE sessions SET total_revenue=? WHERE id=?",(float(rv) if rv not in (None,"") else None,sid))
        if "image_url" in data:
            con.execute("UPDATE sessions SET image_url=? WHERE id=?",((data["image_url"] or None),sid))
        if "raffle_locked" in data:
            con.execute("UPDATE sessions SET raffle_locked=? WHERE id=?",(1 if data["raffle_locked"] else 0,sid))
        if "commodities_locked" in data:
            con.execute("UPDATE sessions SET commodities_locked=? WHERE id=?",(1 if data["commodities_locked"] else 0,sid))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/regenerate_codes", methods=["POST"])
def regenerate_codes(sid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    new_jc=code6(); new_ac=code6()
    with get_db() as con:
        con.execute("UPDATE sessions SET join_code=? WHERE id=?",(new_jc,sid))
        con.execute("UPDATE sessions SET admin_code=? WHERE id=?",(new_ac,sid))
    return jsonify({"admin_code":new_ac,"join_code":new_jc})

@app.route("/api/session/<sid>", methods=["DELETE"])
def delete_session(sid):
    secret=request.args.get("secret",""); code=request.args.get("code","").upper()
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    if not is_admin(s,code) and secret!=get_admin_secret():
        return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con:
        con.execute("DELETE FROM sessions WHERE id=?",(sid,))
    return jsonify({"ok":True})

# ── participants ──────────────────────────────────────────────────────────────
@app.route("/api/session/<sid>/participants", methods=["POST"])
def add_participant(sid):
    data=request.json; code=(data.get("code") or "").upper()
    name=(data.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    admin=is_admin(s,code)
    if not admin and code!=s["join_code"]: return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        ex=con.execute("SELECT id FROM participants WHERE session_id=? AND lower(name)=lower(?)",(sid,name)).fetchone()
        if ex: return jsonify({"error":"Name bereits vorhanden","id":ex["id"]}),409
        pid=uid()
        con.execute("INSERT INTO participants(id,session_id,name,added_by) VALUES(?,?,?,?)",
            (pid,sid,name,"admin" if admin else "self"))
    return jsonify({"id":pid,"name":name})

@app.route("/api/session/<sid>/participants/<pid>", methods=["DELETE"])
def remove_participant(sid,pid):
    code=request.args.get("code","").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        con.execute("DELETE FROM participants WHERE id=? AND session_id=?",(pid,sid))
        con.execute("DELETE FROM wishes WHERE participant_id=?",(pid,))
        con.execute("DELETE FROM no_interest WHERE participant_id=?",(pid,))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/participants/<pid>", methods=["PATCH"])
def update_participant(sid,pid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    name=(data.get("name") or "").strip()
    if name:
        with get_db() as con:
            con.execute("UPDATE participants SET name=? WHERE id=? AND session_id=?",(name,pid,sid))
    return jsonify({"ok":True})

# ── loot ──────────────────────────────────────────────────────────────────────
@app.route("/api/session/<sid>/loot", methods=["POST"])
def add_loot(sid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    name=(data.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    qty=max(1,int(data.get("qty",1))); typ=data.get("type") or None
    grade=data.get("grade") or None; size=data.get("size") or None
    key=loot_key(name,typ,grade,size)
    with get_db() as con:
        ex=con.execute("SELECT id FROM loot WHERE session_id=? AND loot_key=?",(sid,key)).fetchone()
        if ex:
            con.execute("UPDATE loot SET qty=qty+? WHERE id=?",(qty,ex["id"])); lid=ex["id"]
        else:
            lid=uid()
            con.execute("INSERT INTO loot(id,session_id,name,qty,type,grade,size,loot_key) VALUES(?,?,?,?,?,?,?,?)",
                (lid,sid,name,qty,typ,grade,size,key))
        con.execute("INSERT OR IGNORE INTO item_db(loot_key,name,type,grade,size) VALUES(?,?,?,?,?)",(key,name,typ,grade,size))
    return jsonify({"id":lid,"key":key})

@app.route("/api/session/<sid>/loot/<lid>", methods=["DELETE"])
def remove_loot(sid,lid):
    code=request.args.get("code","").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        con.execute("DELETE FROM loot WHERE id=? AND session_id=?",(lid,sid))
        con.execute("DELETE FROM wishes WHERE loot_id=?",(lid,))
        con.execute("DELETE FROM no_interest WHERE loot_id=?",(lid,))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/loot/<lid>/qty", methods=["PATCH"])
def update_loot_qty(sid,lid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    delta=int(data.get("delta",0))
    with get_db() as con:
        con.execute("UPDATE loot SET qty=MAX(1,qty+?) WHERE id=? AND session_id=?",(delta,lid,sid))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/loot/<lid>/sale", methods=["PATCH"])
def update_loot_sale(sid,lid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        if "for_sale" in data:
            fs=1 if data["for_sale"] else 0
            con.execute("UPDATE loot SET for_sale=? WHERE id=? AND session_id=?",(fs,lid,sid))
            if fs:  # clear all wishes for this item
                con.execute("DELETE FROM wishes WHERE loot_id=?",(lid,))
                con.execute("DELETE FROM no_interest WHERE loot_id=?",(lid,))
        if "sale_revenue" in data:
            rv=data["sale_revenue"]
            con.execute("UPDATE loot SET sale_revenue=? WHERE id=? AND session_id=?",
                (float(rv) if rv not in (None,"") else None,lid,sid))
    return jsonify({"ok":True})

# ── wishes & no-interest ──────────────────────────────────────────────────────
@app.route("/api/session/<sid>/wishes", methods=["POST"])
def set_wishes(sid):
    data=request.json; code=(data.get("code") or "").upper()
    pid=data.get("participant_id"); lids=data.get("loot_ids",[])
    mode=data.get("mode","wish")   # 'wish' or 'no_interest'
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    admin=is_admin(s,code)
    if not admin and code!=s["join_code"]: return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    if mode=="wish" and len(lids)>s["max_wishes"] and not admin:
        return jsonify({"error":f"Maximal {s['max_wishes']} Wünsche erlaubt"}),400
    with get_db() as con:
        if mode=="no_interest":
            con.execute("DELETE FROM no_interest WHERE participant_id=? AND session_id=?",(pid,sid))
            for lid in lids:
                con.execute("INSERT OR IGNORE INTO no_interest(id,session_id,participant_id,loot_id) VALUES(?,?,?,?)",
                    (uid(),sid,pid,lid))
        else:
            con.execute("DELETE FROM wishes WHERE participant_id=? AND session_id=?",(pid,sid))
            for lid in lids:
                con.execute("INSERT OR IGNORE INTO wishes(id,session_id,participant_id,loot_id) VALUES(?,?,?,?)",
                    (uid(),sid,pid,lid))
    return jsonify({"ok":True})

# ── commodities ───────────────────────────────────────────────────────────────
@app.route("/api/session/<sid>/commodities", methods=["POST"])
def add_commodity(sid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    name=(data.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    scu=float(data.get("scu",0))
    with get_db() as con:
        ex=con.execute("SELECT id FROM commodities WHERE session_id=? AND lower(name)=lower(?)",(sid,name)).fetchone()
        if ex:
            con.execute("UPDATE commodities SET scu=scu+? WHERE id=?",(scu,ex["id"])); cid=ex["id"]
        else:
            cid=uid()
            con.execute("INSERT INTO commodities(id,session_id,name,scu) VALUES(?,?,?,?)",(cid,sid,name,scu))
        con.execute("INSERT OR IGNORE INTO commodity_db(name) VALUES(?)",(name,))
    return jsonify({"id":cid})

@app.route("/api/session/<sid>/commodities/<cid>", methods=["PATCH"])
def update_commodity(sid,cid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        if "scu"  in data: con.execute("UPDATE commodities SET scu=? WHERE id=? AND session_id=?",(float(data["scu"]),cid,sid))
        if "name" in data: con.execute("UPDATE commodities SET name=? WHERE id=? AND session_id=?",((data["name"] or "").strip(),cid,sid))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/commodities/<cid>/qty", methods=["PATCH"])
def update_commodity_qty(sid,cid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    delta=float(data.get("delta",0))
    with get_db() as con:
        con.execute("UPDATE commodities SET scu=MAX(0,scu+?) WHERE id=? AND session_id=?",(delta,cid,sid))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/commodities/<cid>", methods=["DELETE"])
def delete_commodity(sid,cid):
    code=request.args.get("code","").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    if s["locked"]: return jsonify({"error":"Session gesperrt"}),403
    with get_db() as con:
        con.execute("DELETE FROM commodities WHERE id=? AND session_id=?",(cid,sid))
    return jsonify({"ok":True})

# ── raffle ────────────────────────────────────────────────────────────────────
@app.route("/api/session/<sid>/raffle", methods=["POST"])
def run_raffle(sid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s or not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    participants=s["participants"]
    loot_items=[l for l in s["loot"] if not l.get("for_sale")]
    if not participants or not loot_items: return jsonify({"error":"Braucht Teilnehmer und Loot"}),400

    n_parts=len(participants)
    total_items=sum(l["qty"] for l in loot_items)
    mode = "no_interest" if total_items < n_parts else "wish"

    parts=[{**p,"won":[],"won_by_wish":False} for p in participants]

    # Expand instances
    instances=[]
    for l in loot_items:
        for i in range(l["qty"]): instances.append({**l,"inst":i})

    assigned=set()

    def add_win(p, inst, by_wish=False):
        p["won"].append({"name":inst["name"],"type":inst.get("type"),
                          "grade":inst.get("grade"),"size":inst.get("size")})
        if by_wish: p["won_by_wish"]=True
        assigned.add(f"{inst['id']}:{inst['inst']}")

    def fairest_recipient(pool):
        """Pick participant from pool with fewest wins; random tiebreak."""
        min_won=min(len(p["won"]) for p in pool)
        candidates=[p for p in pool if len(p["won"])==min_won]
        random.shuffle(candidates)
        return candidates[0]

    if mode=="no_interest":
        # No-interest mode: participants mark what they DON'T want.
        # Distribute each item to eligible participants (those who didn't exclude it),
        # always picking the one with fewest wins for fairness.
        by_id={}
        for inst in instances: by_id.setdefault(inst["id"],[]).append(inst)
        random.shuffle(instances)
        for inst in instances:
            eligible=[p for p in parts if inst["id"] not in p.get("no_interest",[])]
            if not eligible: eligible=list(parts)
            add_win(fairest_recipient(eligible), inst)
    else:
        # WISH MODE
        # Phase 1: Distribute all wished items first.
        # For each loot type with interested parties, give one copy to each interested
        # person before giving anyone a second copy (round-robin by wish count).
        by_id={}
        for inst in instances: by_id.setdefault(inst["id"],[]).append(inst)

        for loot_id,insts in by_id.items():
            interested=[p for p in parts if loot_id in p.get("wishes",[])]
            if not interested: continue
            shuffled=list(interested)
            random.shuffle(shuffled)
            for idx,inst in enumerate(insts):
                # Round-robin: cycle through interested, fewest-wins first within each cycle
                cycle_pos=idx%len(shuffled)
                if cycle_pos==0:
                    # Start new cycle: re-sort by wins ascending, shuffle ties
                    shuffled.sort(key=lambda p: len(p["won"]))
                    # Stable-shuffle within same win count
                    groups={}
                    for p in shuffled:
                        groups.setdefault(len(p["won"]),[]).append(p)
                    for g in groups.values(): random.shuffle(g)
                    shuffled=[p for grp in sorted(groups) for p in groups[grp]]
                add_win(shuffled[cycle_pos], inst, by_wish=True)

        # Phase 2: Distribute remaining items with equalizing logic.
        # Always give next item to participant with fewest total wins.
        # This ensures the gap between most and least is minimised.
        remaining=[inst for inst in instances if f"{inst['id']}:{inst['inst']}" not in assigned]
        random.shuffle(remaining)
        for inst in remaining:
            add_win(fairest_recipient(parts), inst)

    with get_db() as con:
        con.execute("DELETE FROM raffle_results WHERE session_id=?",(sid,))
        for p in parts:
            con.execute("INSERT INTO raffle_results(id,session_id,participant_id,participant_name,won_json,won_by_wish) VALUES(?,?,?,?,?,?)",
                (uid(),sid,p["id"],p["name"],json.dumps(p["won"]),1 if p["won_by_wish"] else 0))
        con.execute("UPDATE sessions SET raffle_done=1 WHERE id=?",(sid,))
    return jsonify({"ok":True,"mode":mode})

@app.route("/api/session/<sid>/raffle/<rid>", methods=["PATCH"])
def update_result(sid,rid):
    data=request.json; code=(data.get("code") or "").upper()
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    admin=is_admin(s,code)
    is_super=data.get("secret","")== get_admin_secret()
    join_code=(code==s["join_code"])
    if not admin and not is_super and not join_code:
        return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con:
        if join_code and not admin and not is_super:
            # Participants: one-way only (can set but not unset)
            r=row_to_dict(con.execute("SELECT * FROM raffle_results WHERE id=? AND session_id=?",(rid,sid)).fetchone())
            if not r: return jsonify({"error":"Nicht gefunden"}),404
            if "waived"    in data and data["waived"]    and not r["waived"]:
                con.execute("UPDATE raffle_results SET waived=1 WHERE id=?",(rid,))
            if "collected" in data and data["collected"] and not r["collected"]:
                con.execute("UPDATE raffle_results SET collected=1 WHERE id=?",(rid,))
        else:
            if s["locked"] and not is_super:
                return jsonify({"error":"Session gesperrt"}),403
            if "waived"    in data: con.execute("UPDATE raffle_results SET waived=?    WHERE id=? AND session_id=?",(1 if data["waived"] else 0,rid,sid))
            if "collected" in data: con.execute("UPDATE raffle_results SET collected=? WHERE id=? AND session_id=?",(1 if data["collected"] else 0,rid,sid))
    return jsonify({"ok":True})

@app.route("/api/session/<sid>/raffle/result_for/<pid>")
def result_for_participant(sid,pid):
    code=request.args.get("code","").upper()
    s=load_session(sid)
    if not s: return jsonify({"error":"Nicht gefunden"}),404
    if code!=s["join_code"] and not is_admin(s,code): return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con:
        r=row_to_dict(con.execute("SELECT * FROM raffle_results WHERE session_id=? AND participant_id=?",(sid,pid)).fetchone())
    if not r: return jsonify({"result":None})
    r["won"]=json.loads(r["won_json"]); return jsonify({"result":r})

# ── search endpoints ──────────────────────────────────────────────────────────
@app.route("/api/items/search")
def search_items():
    q=(request.args.get("q") or "").lower().strip()
    with get_db() as con:
        rows=rows_to_list(con.execute("SELECT * FROM item_db WHERE lower(name) LIKE ? LIMIT 12",(f"%{q}%",)).fetchall())
    return jsonify(rows)

@app.route("/api/commodities/search")
def search_commodities():
    q=(request.args.get("q") or "").lower().strip()
    with get_db() as con:
        rows=[r["name"] for r in con.execute("SELECT name FROM commodity_db WHERE lower(name) LIKE ? LIMIT 10",(f"%{q}%",)).fetchall()]
    return jsonify(rows)

@app.route("/api/participants/search")
def search_participants():
    q=(request.args.get("q") or "").lower().strip()
    with get_db() as con:
        rows=[r["name"] for r in con.execute("SELECT name FROM participant_db WHERE lower(name) LIKE ? LIMIT 12",(f"%{q}%",)).fetchall()]
    return jsonify(rows)

# ── admin endpoints ───────────────────────────────────────────────────────────
@app.route("/api/admin/data")
def admin_data():
    if request.args.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con:
        items=rows_to_list(con.execute("SELECT * FROM item_db ORDER BY name COLLATE NOCASE").fetchall())
        names=[r["name"] for r in con.execute("SELECT name FROM participant_db ORDER BY name COLLATE NOCASE").fetchall()]
        comms=[r["name"] for r in con.execute("SELECT name FROM commodity_db ORDER BY name COLLATE NOCASE").fetchall()]
    return jsonify({"items":items,"participant_names":names,"commodity_names":comms})

@app.route("/api/admin/items/<path:key>", methods=["DELETE"])
def admin_delete_item(key):
    if request.args.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con: con.execute("DELETE FROM item_db WHERE loot_key=?",(key,))
    return jsonify({"ok":True})

@app.route("/api/admin/items", methods=["POST"])
def admin_add_item():
    d=request.json
    if d.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    name=(d.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    typ=d.get("type") or None; grade=d.get("grade") or None; size=d.get("size") or None
    key=loot_key(name,typ,grade,size)
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO item_db(loot_key,name,type,grade,size) VALUES(?,?,?,?,?)",(key,name,typ,grade,size))
    return jsonify({"ok":True,"key":key})

@app.route("/api/admin/participants/<path:name>", methods=["DELETE"])
def admin_delete_participant(name):
    if request.args.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con: con.execute("DELETE FROM participant_db WHERE name=?",(name,))
    return jsonify({"ok":True})

@app.route("/api/admin/participants", methods=["POST"])
def admin_add_participant_db():
    d=request.json
    if d.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    name=(d.get("name") or "").strip()
    if not name: return jsonify({"error":"Name erforderlich"}),400
    with get_db() as con: con.execute("INSERT OR IGNORE INTO participant_db(name) VALUES(?)",(name,))
    return jsonify({"ok":True})

@app.route("/api/admin/commodities/<path:name>", methods=["DELETE"])
def admin_delete_commodity_db(name):
    if request.args.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    with get_db() as con: con.execute("DELETE FROM commodity_db WHERE name=?",(name,))
    return jsonify({"ok":True})

# ── UEX import (items sent from browser, processed server-side) ──────────────
@app.route("/api/admin/uex_import", methods=["POST"])
def uex_import():
    d=request.json
    if d.get("secret","")!=get_admin_secret(): return jsonify({"error":"Nicht autorisiert"}),403
    items=d.get("items",[])
    if not items: return jsonify({"error":"Keine Daten empfangen"}),400
    # Browser already sends pre-mapped values: type="CIV"/"MIL" etc., grade="A"/"B" etc.
    valid_types={"MIL","STE","COM","CIV","IND"}
    valid_grades={"A","B","C","D"}
    added=0; skipped=0
    with get_db() as con:
        for item in items:
            name=str(item.get("name") or "").strip()
            if not name: continue
            raw_type=str(item.get("type") or "").strip().upper()
            raw_grade=str(item.get("grade") or "").strip().upper()
            raw_size=str(item.get("size") or "").strip()
            typ=raw_type if raw_type in valid_types else None
            grade=raw_grade if raw_grade in valid_grades else None
            size=raw_size if raw_size.isdigit() else None  # "0" is valid SC size
            key=loot_key(name,typ,grade,size)
            ex=con.execute("SELECT loot_key,type,grade,size FROM item_db WHERE loot_key=?",(key,)).fetchone()

            # Also look for same name with different/missing properties (old imports)
            if not ex:
                ex=con.execute(
                    "SELECT loot_key,type,grade,size FROM item_db WHERE lower(name)=lower(?) LIMIT 1",
                    (name,)).fetchone()

            if not ex:
                con.execute("INSERT INTO item_db(loot_key,name,type,grade,size) VALUES(?,?,?,?,?)",(key,name,typ,grade,size))
                added+=1
            else:
                stored=dict(ex)
                # Merge: prefer incoming non-None values over stored values
                new_type  = typ   if typ   is not None else stored["type"]
                new_grade = grade if grade is not None else stored["grade"]
                new_size  = size  if size  is not None else stored["size"]
                new_key   = loot_key(name, new_type, new_grade, new_size)
                needs_update = (
                    new_key != stored["loot_key"] or
                    new_type  != stored["type"]  or
                    new_grade != stored["grade"] or
                    new_size  != stored["size"]
                )
                if needs_update:
                    con.execute("DELETE FROM item_db WHERE loot_key=?",(stored["loot_key"],))
                    con.execute("INSERT OR REPLACE INTO item_db(loot_key,name,type,grade,size) VALUES(?,?,?,?,?)",
                        (new_key,name,new_type,new_grade,new_size))
                    added+=1
                else:
                    skipped+=1
    return jsonify({"ok":True,"added":added,"skipped":skipped,"total":len(items)})

# ── raidhelper ────────────────────────────────────────────────────────────────
@app.route("/api/raidhelper/parse", methods=["POST"])
def parse_raidhelper():
    try:
        data=request.json.get("json_data",{})
        title=data.get("title") or data.get("displayTitle") or "Unbekanntes Event"
        title=re.sub(r"^\[E\]\s*","",title).strip()
        date=data.get("date") or datetime.now().strftime("%d.%m.%Y")
        excluded={"Absence","Bench","Late"}
        signups=[s for s in data.get("signUps",[]) if (s.get("cClassName") or s.get("className") or "") not in excluded]
        names=[s["name"] for s in signups if s.get("name")]
        image_url = None
        adv = data.get("advancedSettings") or {}
        if isinstance(adv, dict):
            image_url = (adv.get("image") or "").strip() or None
        with get_db() as con:
            for n in names: con.execute("INSERT OR IGNORE INTO participant_db(name) VALUES(?)",(n,))
        return jsonify({"name":f"{date} — {title}","participants":names,"image_url":image_url})
    except Exception as e: return jsonify({"error":str(e)}),400

@app.route("/api/admin/change_secret", methods=["POST"])
def change_secret():
    d=request.json
    if d.get("secret","")!=get_admin_secret(): return jsonify({"error":"Aktuelles Kennwort falsch"}),403
    new_secret=(d.get("new_secret") or "").strip()
    if len(new_secret)<6: return jsonify({"error":"Kennwort muss mindestens 6 Zeichen haben"}),400
    with get_db() as con:
        con.execute("UPDATE config SET value=? WHERE key='admin_secret'",(new_secret,))
    # Reset setup_viewed so the new secret can be looked up if needed
    with get_db() as con:
        con.execute("UPDATE config SET value='0' WHERE key='setup_viewed'")
    print(f"\n◈ Admin-Secret geändert.\n", flush=True)
    return jsonify({"ok":True})

@app.route("/api/admin/verify", methods=["POST"])
def verify_admin():
    d = request.json or {}
    if d.get("secret","") == get_admin_secret():
        return jsonify({"ok": True})
    return jsonify({"error": "Ungültiges Kennwort"}), 403

@app.route("/api/admin/secret-hint")
def secret_hint():
    """Returns the admin secret — only accessible from localhost/container-internal."""
    remote = request.remote_addr or ""
    allowed = ("127.0.0.1", "::1", "localhost")
    if not (remote in allowed or remote.startswith("::ffff:127.") or remote == "172.17.0.1"):
        return jsonify({"error": "Nur lokal erreichbar"}), 403
    sec = get_admin_secret()
    return jsonify({
        "secret": sec,
        "admin_url": f"/#admin?secret={sec}",
        "hint": "Dieser Endpunkt ist nur von localhost erreichbar."
    })

@app.route("/setup")
def setup_page():
    """First-run setup page — only shown once, disappears after being viewed."""
    with get_db() as con:
        viewed = con.execute("SELECT value FROM config WHERE key='setup_viewed'").fetchone()
        already_viewed = viewed and viewed["value"] == "1"
    if already_viewed:
        return """<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"><title>SCLM</title>
<style>body{font-family:monospace;background:#080c10;color:#e8eef4;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#0d1318;border:1px solid rgba(60,140,200,.4);border-radius:8px;
padding:40px;max-width:400px;width:90%;text-align:center}
h1{color:#4d6a80;font-size:18px;letter-spacing:2px}
p{color:#4d6a80;font-size:12px;margin-top:16px;line-height:1.6}
a{color:#1e8bc3;text-decoration:none}</style></head>
<body><div class="box">
<h1>◈ SETUP ABGESCHLOSSEN</h1>
<p>Diese Seite wurde bereits aufgerufen und ist nicht mehr verfügbar.<br><br>
Das Admin-Secret ist in den <strong>Container-Logs</strong> einsehbar.<br><br>
<a href="/">← Zur App</a></p>
</div></body></html>""", 410
    # Mark as viewed immediately
    with get_db() as con:
        con.execute("UPDATE config SET value='1' WHERE key='setup_viewed'")
    sec = get_admin_secret()
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><title>SCLM — Ersteinrichtung</title>
<style>
body{{font-family:monospace;background:#080c10;color:#e8eef4;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.box{{background:#0d1318;border:1px solid rgba(60,140,200,.4);border-radius:8px;padding:40px;max-width:500px;width:90%;text-align:center}}
h1{{color:#1e8bc3;letter-spacing:2px;margin-bottom:8px;font-size:20px}}
.sub{{color:#4d6a80;font-size:11px;letter-spacing:1px;margin-bottom:30px}}
.secret-box{{background:#1a2430;border:1px solid rgba(200,155,60,.4);border-radius:6px;padding:20px;margin:20px 0}}
.secret-label{{color:#4d6a80;font-size:10px;letter-spacing:2px;margin-bottom:8px}}
.secret-val{{color:#c89b3c;font-size:24px;letter-spacing:4px;font-weight:700;word-break:break-all}}
.warn{{background:rgba(231,76,60,.1);border:1px solid rgba(231,76,60,.3);border-radius:4px;padding:12px;color:#e74c3c;font-size:11px;margin:16px 0;line-height:1.8}}
.info{{background:rgba(30,139,195,.1);border:1px solid rgba(30,139,195,.3);border-radius:4px;padding:12px;color:#7cc4e4;font-size:11px;margin:16px 0;line-height:1.8}}
.btn{{display:inline-block;margin-top:20px;padding:12px 24px;background:#0d2a3d;border:1px solid #1e8bc3;color:#1e8bc3;border-radius:4px;text-decoration:none;font-size:13px;font-weight:600;letter-spacing:1px}}
.btn:hover{{background:#1e8bc3;color:#fff}}
</style></head>
<body><div class="box">
<h1>◈ SCLM — Star Citizen Loot Manager</h1>
<div class="sub">ERSTEINRICHTUNG // EINMALIGE ANZEIGE</div>
<div class="secret-box">
  <div class="secret-label">ADMIN SECRET</div>
  <div class="secret-val">{sec}</div>
</div>
<div class="warn">
  ⚠ Diese Seite wird nur <strong>einmalig</strong> angezeigt und ist danach gesperrt.<br>
  Notiere das Secret jetzt — du kannst es später in den Container-Logs oder über die<br>
  Administrationsseite unter Einstellungen ändern.
</div>
<div class="info">
  Nach dem ersten Login empfehlen wir das Secret unter<br>
  <strong>Administration → Einstellungen → Kennwort ändern</strong> anzupassen.
</div>
<a class="btn" href="/#admin?secret={sec}">→ Zur Administrationsseite</a>
</div></body></html>"""

@app.route("/")
def index(): return send_from_directory(str(BASE),"index.html")

if __name__=="__main__":
    port=int(sys.argv[1]) if len(sys.argv)>1 else 5000
    sec=get_admin_secret()
    banner="="*60
    print(f"\n{banner}")
    print(f"  SCLM — Star Citizen Loot Manager")
    print(f"{banner}")
    print(f"  URL:          http://localhost:{port}")
    print(f"  Netzwerk:     http://<deine-IP>:{port}")
    print(f"{banner}")
    print(f"  ADMIN SECRET: {sec}")
    print(f"  Admin-URL:    http://localhost:{port}/#admin?secret={sec}")
    print(f"{banner}\n")
    app.run(host="0.0.0.0",port=port,debug=False)
