"""tests/test_hardening_3a.py — API-Härtungsrunde 3A (stdlib unittest + Flask test_client).

Deckt ab: numeric-in-text 400, Grenzen qty/scu/revenue, NaN/Inf, for_sale-Wunsch 400,
JSON-Fehler bei 404/405/415, sid-im-GET-Pfad-Meldung, neue Zählerfelder, size:"3" ok.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="sclm_test_3a_")
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

    def error_json(self, r):
        self.assertTrue(r.is_json, f"keine JSON-Antwort: {r.get_data(as_text=True)[:200]}")
        return r.get_json()["error"]


# ── 1. Zahlen in Textfeldern ──────────────────────────────────────────────────
class TestTypeValidation(ApiBase):
    def test_loot_size_numeric_400(self):
        s = self.new_session()
        r = self.add_loot(s, name="FR-86", type="MIL", grade="A", size=3)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "size muss eine Zeichenkette sein")

    def test_loot_type_numeric_400(self):
        s = self.new_session()
        r = self.add_loot(s, name="FR-86", type=300)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "type muss eine Zeichenkette sein")

    def test_participant_name_numeric_400(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/participants",
                        json={"name": 5678}, headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "name muss eine Zeichenkette sein")

    def test_text_field_bool_list_obj_rejected(self):
        s = self.new_session()
        for bad in (True, ["a"], {"a": 1}):
            r = self.add_loot(s, name="X", grade=bad)
            self.assertEqual(r.status_code, 400)
            self.assertEqual(self.error_json(r), "grade muss eine Zeichenkette sein")

    def test_numeric_field_bool_rejected(self):
        s = self.new_session()
        r = self.add_loot(s, name="X", qty=True)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "qty muss eine Zahl sein")

    def test_numeric_field_string_ok(self):
        s = self.new_session()
        r = self.add_loot(s, name="X", qty="3")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_numeric_field_nonnumeric_string_400(self):
        s = self.new_session()
        r = self.add_loot(s, name="X", qty="abc")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "qty muss eine Zahl sein")

    def test_text_field_null_ok(self):
        s = self.new_session()
        r = self.add_loot(s, name="X", type=None, grade=None, size=None)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_size_string_3_still_ok(self):
        s = self.new_session()
        r = self.add_loot(s, name="FR-86", type="MIL", grade="A", size="3")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIn("3", r.get_json()["key"].split("|"))
        d = self.c.get(f"/api/session/{s['join_code']}").get_json()
        self.assertEqual(d["loot"][0]["size"], "3")

    def test_settings_name_numeric_400(self):
        s = self.new_session()
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"name": 42}, headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "name muss eine Zeichenkette sein")

    def test_admin_items_numeric_type_400(self):
        s = self.new_session()  # nur um DB-Aktivität zu haben; Admin-Endpoint braucht Secret
        secret = server.get_admin_secret()
        r = self.c.post("/api/admin/items", json={"name": "A", "type": 5},
                        headers={"X-SCLM-Secret": secret})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "type muss eine Zeichenkette sein")

    def test_uex_import_numeric_name_400(self):
        secret = server.get_admin_secret()
        r = self.c.post("/api/admin/uex_import", json={"items": [{"name": 7, "type": "CIV"}]},
                        headers={"X-SCLM-Secret": secret})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "name muss eine Zeichenkette sein")
        r = self.c.post("/api/admin/uex_import", json={"items": {"name": "A"}},
                        headers={"X-SCLM-Secret": secret})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "items muss eine Liste sein")


# ── NaN / Infinity ────────────────────────────────────────────────────────────
class TestNaNInf(ApiBase):
    def _post_raw(self, path, raw, headers=None):
        return self.c.post(path, data=raw, content_type="application/json", headers=headers)

    def test_qty_nan_literal_400(self):
        s = self.new_session()
        r = self._post_raw(f"/api/session/{s['id']}/loot",
                           '{"name":"N1","qty":NaN}', self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "qty darf nicht NaN oder unendlich sein")

    def test_scu_inf_string_400(self):
        s = self.new_session()
        r = self._post_raw(f"/api/session/{s['id']}/commodities",
                           '{"name":"Messium","scu":Infinity}', self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "scu darf nicht NaN oder unendlich sein")
        r = self._post_raw(f"/api/session/{s['id']}/commodities",
                           '{"name":"Messium","scu":"NotAFlightTime"}', self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "scu muss eine Zahl sein")

    def test_revenue_neg_inf_400(self):
        s = self.new_session()
        r = self.c.patch(f"/api/session/{s['id']}/settings", data='{"total_revenue": -Infinity}',
                         content_type="application/json", headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "total_revenue darf nicht NaN oder unendlich sein")


# ── 2. Zahlengrenzen ──────────────────────────────────────────────────────────
class TestBounds(ApiBase):
    def test_qty_bounds(self):
        # 3C: QTY_MAX wurde von 100000 auf 10000 gesenkt
        s = self.new_session()
        for bad in (0, -5, 10001, 10**9):
            r = self.add_loot(s, name="Q", qty=bad)
            self.assertEqual(r.status_code, 400, f"qty={bad}")
            self.assertIn("muss zwischen", self.error_json(r))
        self.assertEqual(self.add_loot(s, name="Q", qty=10000).status_code, 200)

    def test_delta_bounds(self):
        s = self.new_session()
        lid = self.add_loot(s, name="D", qty=5).get_json()["id"]
        for bad in (100001, -100001):
            r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/qty", json={"delta": bad},
                             headers=self.admin(s))
            self.assertEqual(r.status_code, 400, f"delta={bad}")
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/qty", json={"delta": -100000},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200)

    def test_scu_bounds(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/commodities", json={"name": "M", "scu": -1},
                        headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "scu muss zwischen 0 und 1000000000 sein")
        r = self.c.post(f"/api/session/{s['id']}/commodities", json={"name": "M", "scu": 10**10},
                        headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertIn("1000000000", self.error_json(r))

    def test_revenue_bounds(self):
        s = self.new_session()
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"total_revenue": -1},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"total_revenue": 10**13},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        lid = self.add_loot(s, name="S", qty=1).get_json()["id"]
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/sale", json={"sale_revenue": 10**13},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertIn("sale_revenue", self.error_json(r))

    def test_max_wishes_bounds_and_strings(self):
        s = self.new_session(max_wishes="5")   # numerische Saite ok
        self.assertEqual(s["id"] and 200, 200)
        r = self.c.post("/api/session/create", json={"name": "MW", "max_wishes": 0})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "max_wishes muss zwischen 1 und 10 liegen")
        r = self.c.patch(f"/api/session/{s['id']}/settings", json={"max_wishes": True},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.error_json(r), "max_wishes muss eine Zahl sein")


# ── 3. sid vs. Code ───────────────────────────────────────────────────────────
class TestSidInPath(ApiBase):
    def test_sid_in_get_path_message(self):
        s = self.new_session()
        r = self.c.get(f"/api/session/{s['id']}")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.error_json(r),
                         "sid im Pfad nicht erlaubt: GET /api/session/<admin_code oder join_code> verwenden")

    def test_codes_still_work(self):
        s = self.new_session()
        self.assertEqual(self.c.get(f"/api/session/{s['join_code']}").status_code, 200)
        d = self.c.get(f"/api/session/{s['admin_code']}").get_json()
        self.assertTrue(d["is_admin"])
        r = self.c.get("/api/session/ZZZZZZ")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.error_json(r), "Code ungültig")


# ── 4. JSON-Fehlerantworten ───────────────────────────────────────────────────
class TestJsonErrors(ApiBase):
    def test_404_api_is_json(self):
        r = self.c.get("/api/api-hartung-3a-gibts-nicht")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.error_json(r), "Nicht gefunden")

    def test_405_api_is_json(self):
        r = self.c.post("/api/stats")   # Route existiert, aber nur für GET
        self.assertEqual(r.status_code, 405)
        self.assertEqual(self.error_json(r), "Methode nicht erlaubt")

    def test_415_api_is_json(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/loot", data="name=x",
                        content_type="text/plain", headers=self.admin(s))
        self.assertEqual(r.status_code, 415)
        self.assertEqual(self.error_json(r), "Content-Type muss application/json sein")

    def test_page_404_stays_html(self):
        r = self.c.get("/gibts-auch-nicht")
        self.assertEqual(r.status_code, 404)
        self.assertIn("text/html", r.content_type)

    def test_500_generic_no_traceback(self):
        s = self.new_session()
        orig = server.loot_key  # noqa: F811
        try:
            def boom(*a, **k):
                raise RuntimeError("interner Fehler")
            server.loot_key = boom  # type: ignore[attr-defined]
            r = self.add_loot(s, name="BOOM", size="1")
            self.assertEqual(r.status_code, 500)
            body = self.error_json(r)
            self.assertEqual(body, "Interner Serverfehler")
            self.assertNotIn("Traceback", r.get_data(as_text=True))
        finally:
            server.loot_key = orig


# ── 5. Wish-Guard for_sale ────────────────────────────────────────────────────
class TestWishGuard(ApiBase):
    def _participant(self, s):
        r = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]})
        return r.get_json()  # id + pcode

    def test_wish_on_for_sale_400(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Verkauft", qty=2).get_json()["id"]
        other = self.add_loot(s, name="Raffle", qty=1).get_json()["id"]
        self.c.patch(f"/api/session/{s['id']}/loot/{lid}/sale", json={"for_sale": True},
                     headers=self.admin(s))
        p = self._participant(s)
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [lid, other],
                              "pcode": p["pcode"]},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "Gegenstand ist für Verkauf markiert")
        self.assertEqual(r.get_json()["loot_ids"], [lid])

    def test_no_interest_unaffected(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Verkauft", qty=2).get_json()["id"]
        self.c.patch(f"/api/session/{s['id']}/loot/{lid}/sale", json={"for_sale": True},
                     headers=self.admin(s))
        p = self._participant(s)
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [lid],
                              "pcode": p["pcode"], "mode": "no_interest"},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_sale_marking_autoclear_unchanged(self):
        s = self.new_session()
        lid = self.add_loot(s, name="Beides", qty=1).get_json()["id"]
        p = self._participant(s)
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [lid], "pcode": p["pcode"]},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        r = self.c.patch(f"/api/session/{s['id']}/loot/{lid}/sale", json={"for_sale": True},
                         headers=self.admin(s))
        self.assertEqual(r.status_code, 200)  # Auto-Bereinigung bleibt wie sie ist
        d = self.c.get(f"/api/session/{s['admin_code']}").get_json()
        self.assertEqual(d["participants"][0]["wish_count"], 0)


# ── 6. Additive Zählerfelder ──────────────────────────────────────────────────
class TestCounterFields(ApiBase):
    def test_participant_and_result_counters(self):
        s = self.new_session()
        l1 = self.add_loot(s, name="L1", qty=2).get_json()["id"]
        l2 = self.add_loot(s, name="L2", qty=1).get_json()["id"]
        r = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]})
        p = r.get_json()
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [l1, l2], "pcode": p["pcode"]},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        d = self.c.get(f"/api/session/{s['join_code']}").get_json()
        part = d["participants"][0]
        self.assertEqual(part["wish_count"], 2)
        self.assertEqual(part["no_interest_count"], 0)
        self.assertEqual(sorted(part["wishes"]), sorted([l1, l2]))  # bestehende Felder unverändert

        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = self.c.get(f"/api/session/{s['admin_code']}").get_json()
        res = d["results"][0]
        self.assertEqual(res["won_count"], len(res["won"]))
        self.assertEqual(res["won_count"], 3)

    def test_no_interest_count_flag(self):
        s = self.new_session()
        l1 = self.add_loot(s, name="L1", qty=1).get_json()["id"]
        r = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]})
        p = r.get_json()
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [l1],
                              "pcode": p["pcode"], "mode": "no_interest"},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        d = self.c.get(f"/api/session/{s['join_code']}").get_json()
        self.assertEqual(d["participants"][0]["no_interest_count"], 1)
        self.assertEqual(d["participants"][0]["wish_count"], 0)


# ── 7. Kernfunktionen unverändert (Rauchtests) ────────────────────────────────
class TestCoreUnchanged(ApiBase):
    def test_normal_flow(self):
        s = self.new_session()
        lid = self.add_loot(s, name="FR-86", type="MIL", grade="A", size="3", qty=4).get_json()["id"]
        # Dedupe: gleicher Key erhöht qty
        r = self.add_loot(s, name="fr-86", type="MIL", grade="A", size="3", qty="2")
        self.assertEqual(r.get_json()["id"], lid)
        r = self.c.post(f"/api/session/{s['id']}/participants", json={"name": "Self"},
                        headers={"X-SCLM-Code": s["join_code"]})
        p = r.get_json()
        r = self.c.post(f"/api/session/{s['id']}/wishes",
                        json={"participant_id": p["id"], "loot_ids": [lid], "pcode": p["pcode"]},
                        headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        r = self.c.post(f"/api/session/{s['id']}/raffle", json={}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200)
        d = self.c.get(f"/api/session/{s['join_code']}").get_json()
        self.assertTrue(d["raffle_done"])
        self.assertEqual(len(d["results"][0]["won"]), 6)
        # Ergebnis-Markierung Teilnehmer (waived) funktioniert weiter
        rid = d["results"][0]["id"]
        r = self.c.patch(f"/api/session/{s['id']}/raffle/{rid}",
                         json={"waived": True, "pcode": p["pcode"]},
                         headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200)
        r = self.c.get(f"/api/session/{s['join_code']}")  # Listenabfrage weiterhin OK
        self.assertEqual(r.status_code, 200)

    def test_commodity_flow(self):
        s = self.new_session()
        cid = self.c.post(f"/api/session/{s['id']}/commodities",
                          json={"name": "Messium", "scu": "150.5"}, headers=self.admin(s)).get_json()["id"]
        r = self.c.patch(f"/api/session/{s['id']}/commodities/{cid}/qty",
                         json={"delta": "-50"}, headers=self.admin(s))
        self.assertEqual(r.status_code, 200)
        d = self.c.get(f"/api/session/{s['join_code']}").get_json()
        self.assertAlmostEqual(d["commodities"][0]["scu"], 100.5)
        self.assertAlmostEqual(d["commodity_summary"]["total_scu"], 100.5)


if __name__ == "__main__":
    unittest.main()
