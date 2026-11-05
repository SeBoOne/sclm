"""tests/test_hardening_3c.py — Nacharbeit 3C (Review-Befunde aus 3A + 3B-Zusatz + Port-Notiz).

Deckt ab: Ganzzahl-Felder lehnen 1.5 ab (3.0/"3" ok), leere Saiten type/grade/size -> null,
loot_count/participant_count null bei vergifteter Altbestands-qty, QTY_MAX 10000,
RAFFLE_MAX_TOTAL 50000 (400 vor Expansion), Altbestand-Kappung auf QTY_MAX bleibt,
no_interest_count als Anzahl, GET/DELETE Secret header-only (POST/PATCH-Fallback bleibt),
einheitliche Port-Quelle (argv vor PORT).
"""
import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="sclm_test_3c_")
os.environ["DATA_DIR"] = _TMP
server = importlib.import_module("server")


class ApiBase(unittest.TestCase):
    def setUp(self):
        self.c = server.app.test_client()

    def new_session(self, **kw):
        r = self.c.post("/api/session/create", json={"name": "T-" + self.id().split(".")[-1], **kw})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def admin(self, sess):
        return {"X-SCLM-Code": sess["admin_code"]}

    def add_loot(self, sess, **body):
        r = self.c.post(f"/api/session/{sess['id']}/loot", json=body, headers=self.admin(sess))
        return r

    def detail(self, sess):
        return self.c.get(f"/api/session/{sess['admin_code']}").get_json()

    def error_json(self, r):
        self.assertTrue(r.is_json, f"keine JSON-Antwort: {r.get_data(as_text=True)[:200]}")
        return r.get_json()["error"]

    def poison_qty(self, lid, value):
        """Altbestand simulieren: qty direkt in der DB vergiften."""
        with sqlite3.connect(str(server.DB)) as con:
            con.execute("UPDATE loot SET qty=? WHERE id=?", (value, lid))


# ── 1. Ganzzahl-Felder lehnen nicht-ganzzahlige Zahlen ab ────────────────────
class TestIntegerStrictness(ApiBase):
    def test_qty_half_400(self):
        s = self.new_session()
        for bad in (1.5, "1.5", -0.5, 2.7):
            r = self.add_loot(s, name="I", qty=bad)
            self.assertEqual(r.status_code, 400, f"qty={bad!r}")
            self.assertEqual(self.error_json(r), "qty muss eine Ganzzahl sein")

    def test_qty_whole_float_and_strings_ok(self):
        s = self.new_session()
        r = self.add_loot(s, name="W1", qty=3.0)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.add_loot(s, name="W2", qty="3.0")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.add_loot(s, name="W3", qty="3")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(sorted(l["qty"] for l in self.detail(s)["loot"]), [3, 3, 3])

    def test_loot_delta_half_400(self):
        s = self.new_session()
        lid = self.add_loot(s, name="D", qty=5).get_json()["id"]
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/qty", json={"delta": 1.5},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "delta muss eine Ganzzahl sein")
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/qty", json={"delta": 2.0},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200)  # ganzzahliger Float ok
        self.assertEqual(self.detail(s)["loot"][0]["qty"], 7)

    def test_max_wishes_half_400(self):
        r = self.c.post("/api/session/create", json={"name": "MW25", "max_wishes": 2.5})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "max_wishes muss eine Ganzzahl sein")
        r = self.c.post("/api/session/create", json={"name": "MW4", "max_wishes": 4.0})
        self.assertEqual(r.status_code, 200)  # ganzzahliger Float ok
        s = self.new_session()
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"max_wishes": 2.5},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "max_wishes muss eine Ganzzahl sein")

    def test_decimal_fields_stay_decimal(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/commodities", json={"name": "M", "scu": 150.5},
                        headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        cid = r.get_json()["id"]
        r = self.c.patch(f"/api/session/{s['id']}/commodities/{cid}/qty", json={"delta": -50.25},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))  # commodities-delta: Float ok
        lid = self.add_loot(s, name="V", qty=1).get_json()["id"]
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/sale", json={"sale_revenue": 250.75},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200)
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"total_revenue": 10.25},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200)


# ── 2. Leere Saiten -> null (Vertrag: null oder Wert, nie "") ────────────────
class TestEmptyStringToNull(ApiBase):
    def test_loot_empty_type_grade_size_null(self):
        s = self.new_session()
        r = self.add_loot(s, name="EmptyType", qty=1, type="", grade="", size="")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        loot = self.detail(s)["loot"][0]
        self.assertIsNone(loot["type"])
        self.assertIsNone(loot["grade"])
        self.assertIsNone(loot["size"])
        self.assertEqual(loot["loot_key"], "emptytype|||")

    def test_loot_whitespace_only_null(self):
        s = self.new_session()
        r = self.add_loot(s, name="WsType", qty=1, type="   ", grade=" ", size="  ")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        loot = self.detail(s)["loot"][0]
        self.assertIsNone(loot["type"])
        self.assertIsNone(loot["grade"])
        self.assertIsNone(loot["size"])

    def test_name_empty_still_required(self):
        s = self.new_session()
        r = self.add_loot(s, name="", qty=1)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "Name erforderlich")
        r = self.add_loot(s, name="   ", qty=1)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "Name erforderlich")

    def test_nonempty_values_unchanged(self):
        s = self.new_session()
        r = self.add_loot(s, name="Fr86", qty=1, type="MIL", grade="A", size="3")
        self.assertEqual(r.status_code, 200)
        loot = self.detail(s)["loot"][0]
        self.assertEqual((loot["type"], loot["grade"], loot["size"]), ("MIL", "A", "3"))

    def test_admin_item_empty_type_null(self):
        secret = server.get_admin_secret()
        r = self.c.post("/api/admin/items", json={"name": "AdmEmpty", "type": "", "grade": " ", "size": ""},
                        headers={"X-SCLM-Secret": secret})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        items = self.c.get("/api/admin/data", headers={"X-SCLM-Secret": secret}).get_json()["items"]
        adm = [i for i in items if i["name"] == "AdmEmpty"]
        self.assertEqual(len(adm), 1)
        self.assertIsNone(adm[0]["type"])
        self.assertIsNone(adm[0]["grade"])
        self.assertIsNone(adm[0]["size"])


# ── 3. loot_count/participant_count in der Sessions-Liste abgeschirmt ────────
class TestListGuards(ApiBase):
    def test_poisoned_qty_gives_null_loot_count(self):
        s = self.new_session()
        lid = self.add_loot(s, name="POISON", qty=1).get_json()["id"]
        self.poison_qty(lid, 1e20)
        entry = [e for e in self.c.get("/api/sessions").get_json() if e["id"] == s["id"]][0]
        self.assertIsNone(entry["loot_count"])
        self.assertIsInstance(entry["participant_count"], int)  # COUNT(*) ist sauber
        # Detail: qty war durch 3A schon abgeschirmt — Regressionsschutz
        self.assertIsNone(self.detail(s)["loot"][0]["qty"])

    def test_infinite_qty_gives_null_loot_count(self):
        s = self.new_session()
        lid = self.add_loot(s, name="INF", qty=1).get_json()["id"]
        self.poison_qty(lid, float("inf"))
        entry = [e for e in self.c.get("/api/sessions").get_json() if e["id"] == s["id"]][0]
        self.assertIsNone(entry["loot_count"])

    def test_clean_counts_unchanged(self):
        s = self.new_session()
        self.add_loot(s, name="A", qty=4)
        self.add_loot(s, name="B", qty=6)
        entry = [e for e in self.c.get("/api/sessions").get_json() if e["id"] == s["id"]][0]
        self.assertEqual(entry["loot_count"], 10)


# ── 4. QTY_MAX 10000 + RAFFLE_MAX_TOTAL 50000 ────────────────────────────────
class TestRaffleLimits(ApiBase):
    def test_qty_max_is_10000(self):
        s = self.new_session()
        r = self.add_loot(s, name="Edge", qty=10000)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.add_loot(s, name="Over", qty=10001)
        self.assertEqual(r.status_code, 400)
        self.assertIn("zwischen 1 und 10000", self.error_json(r))
        self.assertEqual(server.QTY_MAX, 10_000)
        self.assertEqual(server.RAFFLE_MAX_TOTAL, 50_000)

    def _participant(self, s):
        r = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "P-" + self.id().split(".")[-1]},
                        headers={"X-SCLM-Code": s["join_code"]})
        return r.get_json()

    def test_raffle_rejects_too_many_instances(self):
        s = self.new_session()
        self._participant(s)
        for i in range(6):
            r = self.add_loot(s, name=f"Bulk{i}", qty=10000)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True)[:300])
        body = r.get_json()
        self.assertEqual(body["error"], "Zu viele Loot-Instanzen für eine Ziehung (max 50000)")
        self.assertEqual(body["loot_instanzen"], 60000)
        d = self.detail(s)
        self.assertFalse(d["raffle_done"])  # Ziehung fand nicht statt

    def test_raffle_at_limit_allowed(self):
        s = self.new_session()
        self._participant(s)
        for i in range(5):
            self.assertEqual(self.add_loot(s, name=f"Max{i}", qty=10000).status_code, 200)
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.detail(s)["results"][0]["won_count"], 50000)

    def test_altbestand_cap_survives(self):
        # vergiftete Altbestands-qty (1e14, endlich und unter SAFE_ABS_MAX) wird
        # in der Ziehung auf QTY_MAX gekappt, nicht abgelehnt.
        s = self.new_session()
        self._participant(s)
        lid = self.add_loot(s, name="OLD", qty=1).get_json()["id"]
        self.poison_qty(lid, 1e14)
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.detail(s)["results"][0]["won_count"], 10000)
        # 1e20 -> |wert| > SAFE_ABS_MAX -> qty wird als null serialisiert und
        # bei der Ziehung übersprungen (Altbestand ohne Instanzen, kein Crash)
        self.poison_qty(lid, 1e20)
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])

    def test_small_raffle_unchanged(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Klein", qty=100).get_json()["id"]
        self._participant(s)
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.detail(s)["results"][0]["won_count"], 100)
        self.assertIsNotNone(lid)


# ── 5. no_interest_count ist die Anzahl ──────────────────────────────────────
class TestNoInterestCountSemantics(ApiBase):
    def test_counts_entries_not_flag(self):
        s = self.new_session()
        l1 = self.add_loot(s, name="N1", qty=1).get_json()["id"]
        l2 = self.add_loot(s, name="N2", qty=1).get_json()["id"]
        l3 = self.add_loot(s, name="N3", qty=1).get_json()["id"]
        p = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]}).get_json()
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [l1, l2, l3],
                              "pcode": p["pcode"], "mode": "no_interest"},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        part = self.detail(s)["participants"][0]
        self.assertEqual(part["no_interest_count"], 3)  # Anzahl, nicht 1/0
        self.assertEqual(len(part["no_interest"]), 3)   # Liste unverändert
        self.assertEqual(part["wish_count"], 0)

    def test_no_interest_empty_is_zero(self):
        s = self.new_session()
        self.add_loot(s, name="X", qty=1)
        p = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]}).get_json()
        part = self.detail(s)["participants"][0]
        self.assertEqual(part["no_interest_count"], 0)


# ── 6. 3B-Zusatz: Secret für GET/DELETE nur noch per Header ─────────────────
class TestSecretHeaderOnlyGet(ApiBase):
    def setUp(self):
        super().setUp()
        self.secret = server.get_admin_secret()

    def test_get_admin_data_query_secret_now_403(self):
        r = self.c.get(f"/api/admin/data?secret={self.secret}")
        self.assertEqual(r.status_code, 403)  # 3C: Query-Fallback nur noch POST/PATCH
        r = self.c.get("/api/admin/data", headers={"X-SCLM-Secret": self.secret})
        self.assertEqual(r.status_code, 200)

    def test_sessions_list_admin_code_paths(self):
        s = self.new_session()
        entry = [e for e in self.c.get(f"/api/sessions?secret={self.secret}").get_json()
                 if e["id"] == s["id"]][0]
        self.assertIsNone(entry["admin_code"])  # Query-Secret wirkt nicht mehr
        entry = [e for e in self.c.get("/api/sessions", headers={"X-SCLM-Secret": self.secret}).get_json()
                 if e["id"] == s["id"]][0]
        self.assertEqual(entry["admin_code"], s["admin_code"])  # Header unverändert

    def test_post_and_patch_keep_query_and_body_fallback(self):
        r = self.c.post(f"/api/admin/items?secret={self.secret}",
                        json={"name": "LegacyQuery"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.c.post("/api/admin/items", json={"name": "LegacyBody", "secret": self.secret})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        s = self.new_session()
        r = self.c.patch(f"/api/session/{s['id']}/settings?secret={self.secret}",
                         json={"name": "Nope"})
        # settings PATCH mit Secret-Fallback ist autorisiert; Name "Nope" ok
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_delete_requires_header(self):
        r = self.c.post("/api/admin/items", json={"name": "DelMe"},
                        headers={"X-SCLM-Secret": self.secret})
        key = r.get_json()["key"]
        r = self.c.delete(f"/api/admin/items/{key}?secret={self.secret}")
        self.assertEqual(r.status_code, 403)  # DELETE header-only
        r = self.c.delete(f"/api/admin/items/{key}", headers={"X-SCLM-Secret": self.secret})
        self.assertEqual(r.status_code, 200)

    def test_code_fallback_unchanged(self):
        # Codes (?code= / Body) bleiben überall erhalten — nur Secret wurde umgestellt
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/loot?code={s['admin_code']}", json={"name": "QCode"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))


# ── 7. Port-Quelle vereinheitlicht (Operator-Zusatzpunkt) ────────────────────
class TestPortResolution(unittest.TestCase):
    def test_argv_before_port_before_default(self):
        old_argv = sys.argv
        old_port = os.environ.get("PORT")
        try:
            sys.argv = ["server.py", "5100"]
            os.environ["PORT"] = "6000"
            self.assertEqual(server._resolved_port(), 5100)   # argv gewinnt
            sys.argv = ["server.py"]
            self.assertEqual(server._resolved_port(), 6000)   # PORT wird gelesen
            del os.environ["PORT"]
            self.assertEqual(server._resolved_port(), 5000)   # Default
            sys.argv = ["gunicorn", "server:app"]
            os.environ["PORT"] = "quatsch"
            self.assertEqual(server._resolved_port(), 5000)   # robust bei Müll
        finally:
            sys.argv = old_argv
            if old_port is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = old_port

    def test_banner_printed_once_on_import(self):
        # print_startup_info() läuft genau einmal beim Import; der __main__-Block
        # druckt keinen zweiten Banner mehr (Text des Banners darf nur einmal im
        # Quelltext stehen, Port-Quelle in __main__ ist _resolved_port).
        src = (Path(__file__).resolve().parent.parent / "server.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("SCLM — Star Citizen Loot Manager"), 1)
        main_block = src.split('if __name__=="__main__":')[-1]
        self.assertIn("_resolved_port()", main_block)
        self.assertNotIn("print(", main_block)


if __name__ == "__main__":
    unittest.main()
