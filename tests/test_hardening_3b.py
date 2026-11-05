"""tests/test_hardening_3b.py — API-Härtungsrunde 3B (stdlib unittest + Flask test_client).

Deckt ab: GET /api/sessions liefert join_code nur mit gültigem Site-Secret
(Header und Query), öffentlich join_code:null bei erhaltenem Feld, übrige
Listenfelder unverändert, Session-Detail per join_code weiterhin funktional.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="sclm_test_3b_")
os.environ["DATA_DIR"] = _TMP
server = importlib.import_module("server")


class ApiBase(unittest.TestCase):
    def setUp(self):
        self.c = server.app.test_client()
        self.secret = server.get_admin_secret()

    def new_session(self, **kw):
        r = self.c.post("/api/session/create", json={"name": "T-" + self.id().split(".")[-1], **kw})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def entry_for(self, sessions, sid):
        for e in sessions:
            if e["id"] == sid:
                return e
        self.fail(f"Session {sid} fehlt in der Liste")


# ── 1. Öffentliche Liste: join_code null, Feld vorhanden ─────────────────────
class TestPublicList(ApiBase):
    def test_join_code_null_without_secret(self):
        s = self.new_session()
        r = self.c.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        sessions = r.get_json()
        e = self.entry_for(sessions, s["id"])
        self.assertIn("join_code", e, "Feld join_code muss vorhanden bleiben")
        self.assertIsNone(e["join_code"])
        self.assertIsNone(e["admin_code"])

    def test_all_entries_have_null_join_code(self):
        self.new_session()
        r = self.c.get("/api/sessions")
        for e in r.get_json():
            self.assertIn("join_code", e)
            self.assertIsNone(e["join_code"])

    def test_other_fields_unchanged(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/participants",
                        json={"name": "Tester"}, headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        e = self.entry_for(self.c.get("/api/sessions").get_json(), s["id"])
        for key in ("id", "name", "created", "participant_count", "loot_count",
                    "locked", "raffle_done", "image_url"):
            self.assertIn(key, e)
        self.assertEqual(e["name"], f"T-{self.id().split('.')[-1]}")
        self.assertEqual(e["participant_count"], 1)
        self.assertIsInstance(e["locked"], bool)
        self.assertIsInstance(e["raffle_done"], bool)

    def test_wrong_secret_still_null(self):
        s = self.new_session()
        r = self.c.get("/api/sessions", headers={"X-SCLM-Secret": "falsch123"})
        self.assertEqual(r.status_code, 200)
        e = self.entry_for(r.get_json(), s["id"])
        self.assertIsNone(e["join_code"])
        self.assertIsNone(e["admin_code"])


# ── 2. Liste mit Site-Secret: join_code + admin_code gesetzt ─────────────────
class TestSecretList(ApiBase):
    def test_join_code_with_header_secret(self):
        s = self.new_session()
        r = self.c.get("/api/sessions", headers={"X-SCLM-Secret": self.secret})
        self.assertEqual(r.status_code, 200)
        e = self.entry_for(r.get_json(), s["id"])
        self.assertEqual(e["join_code"], s["join_code"])
        self.assertEqual(e["admin_code"], s["admin_code"])

    def test_join_code_with_query_secret(self):
        s = self.new_session()
        r = self.c.get(f"/api/sessions?secret={self.secret}")
        self.assertEqual(r.status_code, 200)
        e = self.entry_for(r.get_json(), s["id"])
        self.assertEqual(e["join_code"], s["join_code"])
        self.assertEqual(e["admin_code"], s["admin_code"])


# ── 3. Session-Detail per join_code bleibt unverändert ───────────────────────
class TestSessionDetail(ApiBase):
    def test_detail_via_join_code_200(self):
        s = self.new_session()
        r = self.c.get(f"/api/session/{s['join_code']}")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["id"], s["id"])
        self.assertFalse(d.get("is_admin"))

    def test_detail_via_admin_code_shows_join_code(self):
        s = self.new_session()
        r = self.c.get(f"/api/session/{s['admin_code']}")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("is_admin"))
        self.assertEqual(d["admin_code"], s["admin_code"])
        self.assertEqual(d["join_code"], s["join_code"])

    def test_bad_join_code_still_404(self):
        self.new_session()
        r = self.c.get("/api/session/ZZZZZZ")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.is_json)


# ── 4. Core-Fluss über Listen-Sichtbarkeit hinaus unverändert ────────────────
class TestNoRegression(ApiBase):
    def test_join_participant_and_stats_work(self):
        s = self.new_session()
        r = self.c.post(f"/api/session/{s['id']}/participants",
                        json={"name": "Spieler1"}, headers={"X-SCLM-Code": s["join_code"]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        pid = r.get_json()["id"]
        r = self.c.get(f"/api/session/{s['join_code']}")
        self.assertEqual(r.status_code, 200)
        names = [p["name"] for p in r.get_json()["participants"]]
        self.assertIn("Spieler1", names)
        r = self.c.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.get_json()["session_count"], 1)
        self.assertIsNotNone(pid)


if __name__ == "__main__":
    unittest.main()
