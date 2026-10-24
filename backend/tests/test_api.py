import os
import tempfile
import unittest

import helpers
from core import store

_T = tempfile.mkdtemp(prefix="pf-api-import-")
os.environ["PROVAFAIR_LEDGER_DB"] = os.path.join(_T, "chain.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_T}/audit.db"          # keep API usage logs out of the tracked ledger.db
from fastapi.testclient import TestClient  # noqa: E402
from main import PROVA_API_KEY, app  # noqa: E402

KEY = {"X-API-Key": PROVA_API_KEY}

SERVICES = ("ipo", "web3", "lottery", "keys")


class ApiTests(helpers.Isolated, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.c = TestClient(app, headers=KEY)
        self.anon = TestClient(app)

    def draw(self, service, **body):
        body.setdefault("shots", 256)
        return self.c.post(f"/v3/{service}/draw", json=body)

    def test_mode_and_services_endpoints(self):
        m = self.c.get("/v3/mode").json()
        self.assertEqual(m["default"], "sim")
        self.assertEqual(set(m["modes"]), {"sim", "control", "classical", "replay", "live"})
        s = self.c.get("/v3/services").json()
        self.assertEqual(set(s), set(SERVICES))
        self.assertTrue(all(v["limits"] and v["defaults"] for v in s.values()))

    def test_each_service_draw_runs_and_verifies_over_http(self):
        for s in SERVICES:
            r = self.draw(s)
            self.assertEqual(r.status_code, 200, r.text)
            j = r.json()
            self.assertEqual(j["receipt"]["status"], "CERTIFIED")
            self.assertEqual(j["receipt"]["badge"]["text"], "SIMULATOR")
            rid = j["receipt"]["run_id"]
            v = self.c.post(f"/v3/verify/{s}/{rid}").json()
            self.assertTrue(v["all_ok"], v)
            self.assertEqual(self.c.get(f"/v3/{s}/runs/{rid}").json()["receipt"]["run_id"], rid)
            self.assertEqual(self.c.get(f"/v3/{s}/runs").json()["runs"][0]["run_id"], rid)

    def test_keys_returned_once_not_by_get(self):
        j = self.draw("keys", params={"count": 2}).json()
        self.assertEqual(len(j["demo_keys"]), 2)
        got = self.c.get(f"/v3/keys/runs/{j['receipt']['run_id']}").text
        self.assertTrue(all(k not in got for k in j["demo_keys"]))

    def test_blocked_modes_over_http(self):
        for mode in ("control", "classical"):
            j = self.draw("lottery", mode=mode).json()
            self.assertEqual(j["receipt"]["status"], "BLOCKED")
            self.assertIsNone(j["result"])

    def test_replay_over_http(self):
        self.assertEqual(self.draw("ipo", mode="replay").status_code, 404)
        self.draw("ipo")
        r = self.draw("ipo", mode="replay", scenario="demo-b").json()
        self.assertTrue(r["receipt"]["badge"]["replayed"])

    def test_error_codes(self):
        self.assertEqual(self.draw("ipo", params={"lot_size": 0}).status_code, 422)
        self.assertEqual(self.draw("ipo", shots=10).status_code, 422)
        self.assertEqual(self.draw("ipo", mode="bogus").status_code, 422)
        self.assertEqual(self.draw("bogus").status_code, 404)
        self.assertEqual(self.c.get("/v3/bogus/runs").status_code, 404)
        self.assertEqual(self.c.get("/v3/ipo/runs/IPO-nope").status_code, 404)
        self.assertEqual(self.c.post("/v3/verify/ipo/IPO-nope").status_code, 404)
        self.assertEqual(self.c.get("/v3/ipo/runs/..%2F..%2Fetc").status_code, 404)

    def test_backend_param_cannot_reach_ibm(self):
        # anything but aer / fake:* is coerced to aer, so the API can never submit a real job
        j = self.draw("ipo", backend="open").json()
        self.assertEqual(j["receipt"]["backend"], "aer")

    def test_existing_routes_still_work(self):
        self.assertEqual(self.c.get("/v2/usecases").status_code, 200)
        self.assertEqual(self.c.post("/v2/draw", json={"mode": "quantum", "record": False}).status_code, 200)


class AuthAndLegacyTests(helpers.Isolated, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from ledger.audit_db import ApiUsageLog, SessionLocal, init_db
        init_db()
        with SessionLocal() as s:
            s.query(ApiUsageLog).delete()
            s.commit()
        self.c = TestClient(app, headers=KEY)
        self.anon = TestClient(app)

    def test_v3_requires_api_key_everywhere(self):
        bad = TestClient(app, headers={"X-API-Key": "wrong"})
        for cl in (self.anon, bad):
            self.assertEqual(cl.get("/v3/mode").status_code, 401)
            self.assertEqual(cl.get("/v3/services").status_code, 401)
            self.assertEqual(cl.post("/v3/ipo/draw", json={}).status_code, 401)
            self.assertEqual(cl.get("/v3/ipo/runs").status_code, 401)
            self.assertEqual(cl.post("/v3/verify/ipo/x").status_code, 401)
        self.assertEqual(store.list_runs("ipo"), [])          # nothing ran
        self.assertEqual(self.c.get("/v3/mode").status_code, 200)

    def test_v3_rate_limit_and_separate_quota_from_legacy(self):
        os.environ["V3_RATE_LIMIT"] = "4"
        try:
            codes = [self.c.get("/v3/mode").status_code for _ in range(6)]
        finally:
            os.environ.pop("V3_RATE_LIMIT")
        self.assertEqual(codes, [200, 200, 200, 200, 429, 429])
        r = self.c.post("/draw/quantum", json={"service_type": "lottery", "service_params": {}})
        self.assertEqual(r.status_code, 200)                  # legacy quota unaffected by v3 traffic

    def test_v3_idempotency_runs_once_and_never_caches_keys(self):
        h = {"Idempotency-Key": "k-1"}
        a = self.c.post("/v3/keys/draw", json={"shots": 256}, headers=h).json()
        b = self.c.post("/v3/keys/draw", json={"shots": 256}, headers=h).json()
        self.assertEqual(a["receipt"]["run_id"], b["receipt"]["run_id"])
        self.assertTrue(b["idempotent_replay"])
        self.assertTrue(a["demo_keys"])
        self.assertNotIn("demo_keys", b)
        self.assertEqual(len(store.list_runs("keys")), 1)
        c = self.c.post("/v3/keys/draw", json={"shots": 256}, headers={"Idempotency-Key": "k-2"}).json()
        self.assertNotEqual(a["receipt"]["run_id"], c["receipt"]["run_id"])

    def test_legacy_quantum_draw_is_real_not_placeholder(self):
        r = self.c.post("/draw/quantum", json={"service_type": "lottery", "service_params": {"num_winners": 3}})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["status"], "CERTIFIED")
        self.assertNotEqual(j["chsh_score"], 2.8284)
        self.assertTrue(2.0 < j["chsh_score"] <= 3.0)
        self.assertTrue(j["ibm_job_id"].startswith("SIM-"))
        self.assertEqual(len(j["payload"]["prizes"][0]["tickets"]), 3)
        v = self.c.post(f"/v3/verify/lottery/{j['draw_id']}").json()
        self.assertTrue(v["all_ok"])
        self.assertEqual(self.c.get(f"/verify/{j['draw_id']}").json()["status"], "CERTIFIED")   # audit ledger too

    def test_legacy_rigged_draw_is_blocked_by_the_physics(self):
        j = self.c.post("/draw/rigged", json={"service_type": "ipo", "service_params": {}}).json()
        self.assertEqual(j["status"], "BLOCKED")
        self.assertIsNone(j["payload"])
        self.assertLessEqual(j["chsh_score"], 2.0 + 0.3)
        self.assertTrue(self.c.post(f"/v3/verify/ipo/{j['draw_id']}").json()["all_ok"])

    def test_legacy_all_services_and_aliases(self):
        for st_, svc in (("ipo", "ipo"), ("web3", "web3"), ("validator", "web3"), ("quantum_lottery", "lottery"),
                         ("keys", "keys")):
            j = self.c.post("/draw/quantum", json={"service_type": st_, "service_params": {}}).json()
            self.assertEqual(j["service_type"], svc)
            self.assertEqual(j["status"], "CERTIFIED")
            # stay under the 5/min legacy limit
            from ledger.audit_db import ApiUsageLog, SessionLocal
            with SessionLocal() as s:
                s.query(ApiUsageLog).delete(); s.commit()

    def test_legacy_keys_not_returned_or_stored(self):
        j = self.c.post("/draw/quantum", json={"service_type": "keys", "service_params": {}}).json()
        self.assertNotIn("demo_keys", j)
        self.assertNotIn("keys", j["payload"])
        self.assertEqual(len(j["payload"]["fingerprints"]), 4)

    def test_legacy_errors_and_auth(self):
        self.assertEqual(self.anon.post("/draw/quantum", json={}).status_code, 401)
        self.assertEqual(self.c.post("/draw/quantum", json={"service_type": "nope"}).status_code, 422)
        self.assertEqual(self.c.post("/draw/quantum", json={"service_type": "ipo", "service_params": {"lot_size": 0}}).status_code, 422)

    def test_legacy_idempotent_and_rate_limited(self):
        h = {"Idempotency-Key": "legacy-1"}
        a = self.c.post("/draw/quantum", json={"service_type": "ipo"}, headers=h).json()
        b = self.c.post("/draw/quantum", json={"service_type": "ipo"}, headers=h).json()
        self.assertEqual(a["draw_id"], b["draw_id"])
        self.assertEqual(len(store.list_runs("ipo")), 1)
        codes = [self.c.post("/draw/quantum", json={"service_type": "ipo"}).status_code for _ in range(5)]
        self.assertEqual(codes.count(429), 2)                 # 5/min: 2 used above (both count), 3 more allowed

    def test_legacy_webhook_returns_202_then_completes(self):
        r = self.c.post("/draw/quantum", json={"service_type": "ipo", "webhook_url": "http://127.0.0.1:9/none"})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["status"], "QUEUED")
        rid = r.json()["draw_id"]
        self.assertTrue(self.c.post(f"/v3/verify/ipo/{rid}").json()["all_ok"])      # background task finished


if __name__ == "__main__":
    unittest.main()
