"""tests/test_public_view.py — Runde 4A: öffentliche Session-Detail-Ansicht ohne Codes.

Deckt ab: GET /api/public/session/<sid> ist ohne Header/Code/Secret lesbar (200),
liefert nirgends join_code/admin_code/pcode (rekursiv), dieselben Zahlenwerte wie
der Join-Code-Leser für dieselbe Session, 404-JSON bei unbekannter sid, sid im
/alten/ Pfad /api/session/<sid> bleibt abgelehnt, vergifteter Altbestand (qty=1e20)
crasht nicht und wird zu null, gesperrte und abgeschlossene Sessions sind lesbar,
Schreibzugriff ohne Codes bleibt abgelehnt.
"""
import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="sclm_test_4a_")
os.environ["DATA_DIR"] = _TMP
server = importlib.import_module("server")

FORBIDDEN_KEYS = ("join_code", "admin_code", "pcode")


def iter_keys(obj, path="$"):
    """Rekursiver Walk über dict/list — liefert alle Schlüssel mit ihrem Pfad."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from iter_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_keys(v, f"{path}[{i}]")


class ApiBase(unittest.TestCase):
    def setUp(self):
        self.c = server.app.test_client()

    def new_session(self, **kw):
        r = self.c.post("/api/session/create", json={"name": "P4A-" + self.id().split(".")[-1], **kw})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def admin(self, sess):
        return {"X-SCLM-Code": sess["admin_code"]}

    def add_participant(self, sess, name):
        r = self.c.post(f"/api/session/{sess['id']}/participants",
                        json={"name": name}, headers=self.admin(sess))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()["id"]

    def add_loot(self, sess, **body):
        r = self.c.post(f"/api/session/{sess['id']}/loot", json=body, headers=self.admin(sess))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()["id"]

    def wishes(self, sess, pid, loot_ids, mode="wish"):
        r = self.c.post(f"/api/session/{sess['id']}/wishes",
                        json={"participant_id": pid, "loot_ids": loot_ids, "mode": mode},
                        headers=self.admin(sess))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def public(self, sid):
        # bewusst KEINER Header, KEIN Code, KEIN Secret
        return self.c.get(f"/api/public/session/{sid}")

    def populated_session(self, with_raffle=True):
        """Session mit Teilnehmern, Loot, Wünschen, No-Interest, Ware und Ziehung."""
        s = self.new_session(max_wishes=2)
        p1 = self.add_participant(s, "Alice")
        p2 = self.add_participant(s, "Bob")
        l1 = self.add_loot(s, name="Aputarma Body", qty=2, type="MIL", grade="A", size="1")
        l2 = self.add_loot(s, name="Medkit L", qty=3, type="MED", grade="B", size="2")
        l3 = self.add_loot(s, name="Champagner", qty=1, type="CIV", grade="A", size="1", for_sale=True)
        self.c.post(f"/api/session/{s['id']}/commodities",
                    json={"name": "Bakery", "scu": 120.5}, headers=self.admin(s))
        self.wishes(s, p1, [l1])
        self.wishes(s, p2, [l2])
        self.wishes(s, p2, [l3], mode="no_interest")
        if with_raffle:
            r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return s


# ── 1. Öffentlicher Lese-Endpunkt: 200 ohne alles ────────────────────────────
class TestPublicReadEndpoint(ApiBase):
    def test_200_without_any_header(self):
        s = self.populated_session()
        r = self.public(s["id"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d["id"], s["id"])
        self.assertEqual(d["name"], f"P4A-{self.id().split('.')[-1]}")
        self.assertIs(d["is_admin"], False)
        self.assertEqual(len(d["participants"]), 2)
        self.assertTrue(d["loot"])
        self.assertTrue(d["commodities"])
        self.assertTrue(d["results"])

    def test_session_metadata_fields(self):
        s = self.populated_session(with_raffle=False)
        d = self.public(s["id"]).get_json()
        for key in ("id", "name", "created", "max_wishes", "locked", "raffle_locked",
                    "commodities_locked", "raffle_done", "total_revenue", "image_url",
                    "participants", "loot", "commodities", "results", "commodity_summary"):
            self.assertIn(key, d, f"Feld {key} fehlt")

    def test_participant_and_loot_fields(self):
        d = self.public(self.populated_session()["id"]).get_json()
        for p in d["participants"]:
            for key in ("id", "name", "added_by", "wishes", "no_interest",
                        "wish_count", "no_interest_count"):
                self.assertIn(key, p, f"Teilnehmer-Feld {key} fehlt")
        for l in d["loot"]:
            for key in ("id", "name", "qty", "type", "grade", "size", "sale_revenue", "for_sale", "wish_count"):
                self.assertIn(key, l, f"Loot-Feld {key} fehlt")
        for c in d["commodities"]:
            for key in ("id", "name", "scu"):
                self.assertIn(key, c, f"Waren-Feld {key} fehlt")
        for res in d["results"]:
            for key in ("won", "won_count", "won_by_wish", "waived", "collected"):
                self.assertIn(key, res, f"Ergebnis-Feld {key} fehlt")
            self.assertNotIn("won_json", res, "won_json darf nicht ausgeliefert werden")

    def test_empty_session_is_readable(self):
        sid = self.new_session()["id"]
        r = self.public(sid)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["participants"], [])
        self.assertEqual(d["loot"], [])
        self.assertEqual(d["results"], [])


# ── 2. Keine Codes anywhere (rekursiv) ───────────────────────────────────────
class TestNoCodesLeak(ApiBase):
    def test_no_code_keys_anywhere(self):
        s = self.populated_session()
        r = self.public(s["id"])
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        hits = [(path, key) for path, key in iter_keys(d) if key in FORBIDDEN_KEYS]
        self.assertEqual(hits, [], f"Code-Schlüssel im Payload: {hits}")

    def test_code_values_not_anywhere_in_payload(self):
        s = self.populated_session(with_raffle=False)
        raw = self.public(s["id"]).get_data(as_text=True)
        for label in ("join_code", "admin_code"):
            self.assertNotIn(s[label], raw, f"{label}-Wert ist im Payload enthalten")
        # pcode-Werte der Teilnehmer (nur im Admin-Detail sichtbar) dürfen nicht vorkommen
        with sqlite3.connect(str(server.DB)) as con:
            rows = con.execute("SELECT pcode FROM participants WHERE session_id=?", (s["id"],)).fetchall()
        for (pc,) in rows:
            if pc:
                self.assertNotIn(pc, raw, "pcode-Wert ist im Payload enthalten")

    def test_admin_detail_still_has_pcodes_for_comparison(self):
        """Gegenprobe: der Admin-Leser liefert pcode — der öffentliche Endpunkt nicht."""
        s = self.populated_session(with_raffle=False)
        admin_view = self.c.get(f"/api/session/{s['admin_code']}").get_json()
        self.assertTrue(any("pcode" in p for p in admin_view["participants"]),
                        "Admin-Detail muss pcode liefern (Vergleichsbasis)")
        pub = self.public(s["id"]).get_json()
        self.assertFalse(any("pcode" in p for p in pub["participants"]))

    def test_locked_session_leaks_nothing(self):
        s = self.new_session()
        self.c.patch(f"/api/session/{s['id']}/settings", json={"locked": True}, headers=self.admin(s))
        raw = self.public(s["id"]).get_data(as_text=True)
        d = json.loads(raw)
        self.assertTrue(d["locked"])
        hits = [k for _, k in iter_keys(d) if k in FORBIDDEN_KEYS]
        self.assertEqual(hits, [])
        for label in ("join_code", "admin_code"):
            self.assertNotIn(s[label], raw)


# ── 3. Gleiche Zahlenwerte wie der Join-Code-Leser ───────────────────────────
class TestSameNumbersAsCodeReader(ApiBase):
    def test_counts_and_values_match_join_code_reader(self):
        s = self.populated_session()
        pub_resp = self.public(s["id"])
        self.assertEqual(pub_resp.status_code, 200)
        pub = pub_resp.get_json()
        code = self.c.get(f"/api/session/{s['join_code']}").get_json()

        # Session-Metadaten
        for key in ("id", "name", "created", "max_wishes", "locked", "raffle_done",
                    "raffle_mode", "total_revenue", "image_url"):
            self.assertEqual(pub[key], code[key], f"Metadatum {key} weicht ab")

        # Teilnehmer: Anzahl + Zähler
        self.assertEqual(len(pub["participants"]), len(code["participants"]))
        self.assertEqual(len(pub["participants"]), 2)
        for a, b in zip(sorted(pub["participants"], key=lambda p: p["name"]),
                        sorted(code["participants"], key=lambda p: p["name"])):
            self.assertEqual(a["name"], b["name"])
            self.assertEqual(sorted(a["wishes"]), sorted(b["wishes"]))
            self.assertEqual(sorted(a["no_interest"]), sorted(b["no_interest"]))
            self.assertEqual(a["wish_count"], b["wish_count"])
            self.assertEqual(a["no_interest_count"], b["no_interest_count"])
        self.assertEqual([p["no_interest_count"] for p in pub["participants"]], [0, 1])
        self.assertEqual([p["wish_count"] for p in pub["participants"]], [1, 1])

        # Loot: Mengen + wish_count
        self.assertEqual(len(pub["loot"]), len(code["loot"]))
        self.assertEqual({l["name"]: l["qty"] for l in pub["loot"]},
                         {l["name"]: l["qty"] for l in code["loot"]})
        self.assertEqual({l["name"]: l["wish_count"] for l in pub["loot"]},
                         {l["name"]: l["wish_count"] for l in code["loot"]})

        # Waren
        self.assertEqual({c["name"]: c["scu"] for c in pub["commodities"]},
                         {c["name"]: c["scu"] for c in code["commodities"]})

        # Ziehungsergebnisse
        self.assertEqual(len(pub["results"]), len(code["results"]))
        self.assertEqual([r["won_count"] for r in sorted(pub["results"], key=lambda r: r["participant_name"])],
                         [r["won_count"] for r in sorted(code["results"], key=lambda r: r["participant_name"])])
        self.assertEqual([r["won"] for r in sorted(pub["results"], key=lambda r: r["participant_name"])],
                         [r["won"] for r in sorted(code["results"], key=lambda r: r["participant_name"])])
        self.assertEqual(pub["commodity_summary"], code["commodity_summary"])


# ── 4. 404 als JSON, nie HTML/500 ────────────────────────────────────────────
class TestUnknownSid(ApiBase):
    def test_unknown_sid_json_404(self):
        r = self.public("zzzzzzzz")
        self.assertEqual(r.status_code, 404)
        self.assertIn("application/json", r.content_type)
        self.assertEqual(r.get_json(), {"error": "Session nicht gefunden"})

    def test_empty_sid_does_not_match_public_route(self):
        # "/api/public/session/" (ohne sid) ist kein Route-Treffer -> JSON-Fehler, keine Seite
        r = self.c.get("/api/public/session/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("application/json", r.content_type)
        self.assertNotIn("<html", r.get_data(as_text=True).lower())


# ── 5. Der alte Code-Pfad bleibt unverändert (3A-Regel) ──────────────────────
class TestCodeOnlyPathUnchanged(ApiBase):
    def test_sid_in_old_path_still_rejected(self):
        s = self.new_session()
        r = self.c.get(f"/api/session/{s['id']}")
        self.assertEqual(r.status_code, 404)
        self.assertIn("sid im Pfad nicht erlaubt", r.get_json()["error"])

    def test_code_reader_still_rejects_sid_and_accepts_codes(self):
        s = self.new_session()
        self.assertEqual(self.c.get("/api/session/nnnnnnnn").get_json()["error"], "Code ungültig")
        self.assertEqual(self.c.get(f"/api/session/{s['join_code']}").get_json()["id"], s["id"])
        self.assertEqual(self.c.get(f"/api/session/{s['admin_code']}").get_json()["id"], s["id"])

    def test_public_route_is_not_a_write_path(self):
        s = self.new_session()
        r = self.c.post(f"/api/public/session/{s['id']}", json={"name": "Angriff"})
        self.assertIn(r.status_code, (404, 405))
        self.assertIn("application/json", r.content_type)


# ── 6. Vergifteter Altbestand ────────────────────────────────────────────────
class TestPoisonedLegacyValues(ApiBase):
    def _poison(self, sid):
        with sqlite3.connect(str(server.DB)) as con:
            con.execute("UPDATE loot SET qty=1e20 WHERE session_id=?", (sid,))
            con.execute("UPDATE loot SET sale_revenue=1e30 WHERE session_id=?", (sid,))
            con.execute("UPDATE commodities SET scu=1e30 WHERE session_id=?", (sid,))
            con.execute("UPDATE sessions SET total_revenue=1e30 WHERE id=?", (sid,))
            con.commit()

    def test_poisoned_qty_becomes_null_and_no_crash(self):
        s = self.new_session()
        self.add_loot(s, name="Altbestand loot", qty=5, type="item")
        self.c.post(f"/api/session/{s['id']}/commodities", json={"name": "Altbestand Ware", "scu": 10},
                    headers=self.admin(s))
        self._poison(s["id"])
        r = self.public(s["id"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        loot = [l for l in d["loot"] if l["name"] == "Altbestand loot"][0]
        self.assertIsNone(loot["qty"], "vergiftete qty muss null sein")
        for c in d["commodities"]:
            if c["name"] == "Altbestand Ware":
                self.assertIsNone(c["scu"], "vergiftete scu muss null sein")
        self.assertIsNone(d["total_revenue"], "vergiftete total_revenue muss null sein")
        cs = d["commodity_summary"]
        for key in ("total_scu", "total_revenue", "sale_revenue"):
            v = cs[key]
            self.assertTrue(v is None or abs(v) <= server.SAFE_ABS_MAX,
                            f"commodity_summary.{key} = {v} ist nicht abgeschirmt")
        raw = r.get_data(as_text=True)
        for bad in ("1e+20", "1e20", "1e+30", "1e30", "Infinity", "NaN"):
            self.assertNotIn(bad, raw, f"{bad} ist im Payload aufgetaucht")

    def test_poisoned_loot_still_readable_by_code_reader(self):
        """Der Code-Leser shielded ebenfalls — öffentliche Ansicht darf nicht schlechter sein."""
        s = self.new_session()
        self.add_loot(s, name="Gift loot", qty=7, type="item")
        self._poison(s["id"])
        pub = self.public(s["id"])
        self.assertEqual(pub.status_code, 200)
        code = self.c.get(f"/api/session/{s['join_code']}")
        self.assertEqual(code.status_code, 200)
        self.assertEqual([l["qty"] for l in pub.get_json()["loot"]],
                         [l["qty"] for l in code.get_json()["loot"]])


# ── 7. Gesperrte und abgeschlossene Sessions sind lesbar ─────────────────────
class TestLockedAndFinishedReadable(ApiBase):
    def test_locked_session_readable_but_write_still_denied(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Locked loot", qty=1, type="item")
        pid = self.add_participant(s, "Carl")
        self.c.patch(f"/api/session/{s['id']}/settings", json={"locked": True}, headers=self.admin(s))
        r = self.public(s["id"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["locked"], "locked muss als wahr (1/true) erscheinen")
        # Sperre betrifft nur Schreibzugriff — auch mit gültigem Join-Code
        w = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": pid, "loot_ids": [lid], "mode": "wish",
                              "pcode": "irgendein-key"},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(w.status_code, 403, w.get_data(as_text=True))
        self.assertEqual(w.get_json()["error"], "Session gesperrt")
        # ohne jeden Code bleibt der Schreibversuch ebenfalls abgelehnt
        n = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": pid, "loot_ids": [lid], "mode": "wish"})
        self.assertEqual(n.status_code, 403)
        self.assertEqual(n.get_json()["error"], "Nicht autorisiert")

    def test_raffle_done_session_readable(self):
        s = self.populated_session(with_raffle=True)
        r = self.public(s["id"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertTrue(d["raffle_done"], "raffle_done muss als wahr (1/true) erscheinen")
        self.assertTrue(d["results"])
        self.assertTrue(sum(res["won_count"] for res in d["results"]) > 0)

    def test_writes_without_codes_are_denied_everywhere(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Write probe", qty=1, type="item")
        pid = self.add_participant(s, "Dana")
        cases = [
            ("POST", f"/api/session/{s['id']}/wishes", {"participant_id": pid, "loot_ids": [lid]}),
            ("POST", f"/api/session/{s['id']}/loot", {"name": "Ohne Code", "qty": 1}),
            ("POST", f"/api/session/{s['id']}/participants", {"name": "Ohne Code"}),
            ("PATCH", f"/api/session/{s['id']}/settings", {"locked": True}),
            ("POST", f"/api/session/{s['id']}/raffle", {}),
        ]
        for method, path, body in cases:
            r = getattr(self.c, method.lower())(path, json=body)
            self.assertEqual(r.status_code, 403, f"{path}: {r.get_data(as_text=True)}")
        self.assertEqual(self.c.delete(f"/api/session/{s['id']}").status_code, 403)


# ── 8. ui/Vertrags-Wächter: Liste bleibt code-frei, sid nur in diesem Pfad ───
class TestContractGuard(ApiBase):
    def test_list_still_has_no_codes(self):
        s = self.new_session()
        raw = self.c.get("/api/sessions").get_data(as_text=True)
        for label in ("join_code", "admin_code"):
            self.assertNotIn(s[label], raw, "Sessions-Liste darf keine Codes enthalten")

    def test_public_view_has_no_secrets_required(self):
        # explizit: Secret-Header ändert am öffentlichen Endpunkt nichts
        s = self.new_session()
        a = self.public(s["id"]).get_json()
        b = self.c.get(f"/api/public/session/{s['id']}",
                       headers={"X-SCLM-Secret": server.get_admin_secret()}).get_json()
        self.assertEqual({k: v for k, v in a.items() if k != "commodity_summary"},
                         {k: v for k, v in b.items() if k != "commodity_summary"})
        self.assertNotIn("admin_code", b)
        self.assertNotIn("join_code", b)


if __name__ == "__main__":
    unittest.main()
