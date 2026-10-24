"""Live mode: real hardware when there is no queue, otherwise a saved hardware run. All with fakes, no IBM calls."""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

import helpers
from core import hardware, pipeline, store

_T = tempfile.mkdtemp(prefix="pf-live-import-")
os.environ.setdefault("PROVAFAIR_LEDGER_DB", os.path.join(_T, "chain.db"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_T}/audit.db")
from fastapi.testclient import TestClient  # noqa: E402
from main import PROVA_API_KEY, app  # noqa: E402
from services import router  # noqa: E402

OK_PROBE = {"ok": True, "spec": "fake:FakeKingston", "backend": "FakeKingston", "pending": 0}


def probe(**kw):
    return mock.patch.object(hardware, "live_probe_safe", return_value={**OK_PROBE, **kw})


class LiveBase(helpers.Isolated):
    def setUp(self):
        super().setUp()
        pipeline._live_used = 0
        for k in ("LIVE_MAX_PENDING", "LIVE_MAX_JOBS", "LIVE_QUEUE_TIMEOUT"):
            os.environ.pop(k, None)

    def record_hardware(self, service="lottery", backend="ibm_test"):
        """Make a saved 'hardware' run (simulator bits relabelled), as scripts/collect.py would leave behind."""
        out = pipeline.draw(service, {}, "sim", shots=512)
        rid = out["receipt"]["run_id"]
        d = store.run_dir(service, rid)
        for name, patch in (("job_meta.json", {"source": "hardware", "backend": backend, "job_id": "hw-job-1"}),
                            ("receipt.json", {"source": "hardware", "backend": backend, "job_id": "hw-job-1"})):
            o = json.loads((d / name).read_text()); o.update(patch); (d / name).write_text(json.dumps(o))
        return rid


class LiveTests(LiveBase, unittest.TestCase):
    def test_live_runs_when_no_queue(self):
        with probe():
            out = pipeline.draw("web3", {}, "live", shots=512)
        rc = out["receipt"]
        self.assertEqual(rc["status"], "CERTIFIED")
        self.assertEqual(rc["badge"]["live"], "live")
        self.assertEqual(rc["badge"]["text"], "SIMULATOR (live, fake backend)")   # fake backend is never called hardware
        self.assertIsNone(rc["badge"]["note"])
        self.assertEqual(rc["live_attempt"]["outcome"], "live")
        self.assertTrue(pipeline.verify_run("web3", rc["run_id"])["all_ok"])
        self.assertEqual(pipeline._live_used, 1)

    def test_queue_means_fallback_to_saved_hardware_run(self):
        src = self.record_hardware()
        with probe(pending=7, backend="ibm_kingston"), mock.patch.object(hardware, "submit_job") as sub:
            out = pipeline.draw("lottery", {}, "live", shots=512)
            sub.assert_not_called()                      # nothing was submitted
        rc = out["receipt"]
        self.assertEqual(rc["status"], "CERTIFIED")
        self.assertEqual(rc["replay_of"], src)
        b = rc["badge"]
        self.assertEqual(b["text"], "HARDWARE (recorded)")
        self.assertEqual(b["live"], "fallback")
        self.assertTrue(b["replayed"])
        self.assertIn("7 jobs queued on ibm_kingston", b["note"])
        self.assertIn(src, b["note"])
        self.assertEqual(rc["job_id"], "hw-job-1")
        self.assertTrue(pipeline.verify_run("lottery", rc["run_id"])["all_ok"])
        self.assertEqual(pipeline._live_used, 0)

    def test_fallback_is_never_labelled_live_hardware(self):
        self.record_hardware()
        with probe(pending=1):
            rc = pipeline.draw("lottery", {}, "live", shots=512)["receipt"]
        self.assertNotIn("(live)", rc["badge"]["text"])

    def test_threshold_is_configurable(self):
        os.environ["LIVE_MAX_PENDING"] = "3"
        with probe(pending=3):
            self.assertEqual(pipeline.draw("ipo", {}, "live", shots=256)["receipt"]["badge"]["live"], "live")
        self.record_hardware("ipo")
        with probe(pending=4):
            self.assertEqual(pipeline.draw("ipo", {}, "live", shots=256)["receipt"]["badge"]["live"], "fallback")

    def test_ibm_unreachable_falls_back_with_reason(self):
        self.record_hardware()
        with probe(ok=False, error="no answer from IBM within 15s"):
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertEqual(rc["badge"]["live"], "fallback")
        self.assertIn("cannot reach IBM", rc["badge"]["note"])

    def test_offline_probe_never_raises_or_hangs(self):
        with mock.patch.object(hardware, "get_service", side_effect=OSError("network down")):
            os.environ.pop("PROVAFAIR_LIVE_BACKEND", None)
            r = hardware.live_probe_safe(2.0)
        self.assertFalse(r["ok"])
        self.assertIn("network down", r["error"])
        with mock.patch.object(hardware, "live_probe", side_effect=lambda a="open": time.sleep(3)):
            t = time.time()
            r = hardware.live_probe_safe(0.3)
        self.assertLess(time.time() - t, 1.5)
        self.assertIn("no answer", r["error"])

    def test_probe_error_message_never_contains_the_token(self):
        os.environ["API_KEY"] = "SECRET-IBM-TOKEN-123"
        try:
            with mock.patch.object(hardware, "get_service", side_effect=RuntimeError("bad token SECRET-IBM-TOKEN-123")):
                r = hardware.live_probe_safe(2.0)
        finally:
            os.environ.pop("API_KEY")
        self.assertNotIn("SECRET-IBM-TOKEN-123", r["error"])

    def test_queued_job_is_cancelled_and_falls_back(self):
        self.record_hardware()
        with probe(), mock.patch.object(hardware, "submit_job", return_value={}), \
                mock.patch.object(hardware, "wait_for_job", return_value="timeout"), \
                mock.patch.object(hardware, "collect_job") as col:
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
            col.assert_not_called()
        self.assertEqual(rc["badge"]["live"], "fallback")
        self.assertIn("still queued", rc["badge"]["note"])
        self.assertIn("cancelled", rc["badge"]["note"])

    def test_failed_hardware_job_falls_back(self):
        self.record_hardware()
        with probe(), mock.patch.object(hardware, "submit_job", return_value={}), \
                mock.patch.object(hardware, "wait_for_job", return_value="error:ERROR"):
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertIn("error:ERROR", rc["badge"]["note"])

    def test_submit_exception_falls_back(self):
        self.record_hardware()
        with probe(), mock.patch.object(hardware, "submit_job", side_effect=RuntimeError("boom")):
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertIn("live submission failed", rc["badge"]["note"])

    def test_no_saved_hardware_run_is_a_clear_503_and_leaves_no_run(self):
        pipeline.draw("keys", {}, "sim", shots=256)            # a simulator recording is NOT an acceptable fallback
        with probe(pending=9):
            with self.assertRaises(pipeline.PipelineError) as cm:
                pipeline.draw("keys", {}, "live", shots=256)
        self.assertEqual(cm.exception.status, 503)
        self.assertIn("no recorded hardware run", str(cm.exception))
        self.assertEqual(len(store.list_runs("keys")), 1)

    def test_live_job_cap_protects_the_allowance(self):
        self.record_hardware()
        os.environ["LIVE_MAX_JOBS"] = "1"
        with probe():
            a = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
            b = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertEqual(a["badge"]["live"], "live")
        self.assertEqual(b["badge"]["live"], "fallback")
        self.assertIn("cap reached", b["badge"]["note"])

    def test_only_one_live_run_at_a_time(self):
        self.record_hardware()
        with probe(), pipeline._live_lock:
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertEqual(rc["badge"]["live"], "fallback")
        self.assertIn("another live run", rc["badge"]["note"])

    def test_blocked_live_result_is_not_hidden_by_fallback(self):
        # if live hardware answers but fails certification we show BLOCKED, we do not swap in a nicer saved run
        self.record_hardware()

        def bad_submit(run_dir, shots, entangle, backend, account="open"):
            bits, info = hardware.run_classical(shots)
            (run_dir / "_local_bits.json").write_text(json.dumps(bits))
            meta = {"job_id": "LHV-1", "backend": "bad", "pair": None, "shots": shots, "circuits": list(bits),
                    "entangled": True, "submitted": hardware.now(), "finished": None, "source": "hardware", "local": True}
            (run_dir / "job_meta.json").write_text(json.dumps(meta))
            return meta
        with probe(), mock.patch.object(hardware, "submit_job", side_effect=bad_submit):
            out = pipeline.draw("lottery", {}, "live", shots=512)
        self.assertEqual(out["receipt"]["status"], "BLOCKED")
        self.assertIsNone(out["result"])
        self.assertEqual(out["receipt"]["badge"]["live"], "live")
        self.assertTrue(pipeline.verify_run("lottery", out["receipt"]["run_id"])["all_ok"])

    def test_params_are_committed_before_any_live_attempt(self):
        self.record_hardware()
        seen = {}

        def spy(*a, **k):
            seen["ledger"] = [e["draw_id"] for e in self.ledger.all_entries()]
            return {"ok": False, "error": "x"}
        with mock.patch.object(hardware, "live_probe_safe", side_effect=spy):
            rc = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        self.assertIn(f"{rc['run_id']}:COMMIT", seen["ledger"])

    def test_fallback_run_becomes_verifiable_and_later_replays_point_at_original(self):
        src = self.record_hardware()
        with probe(pending=5):
            a = pipeline.draw("lottery", {}, "live", shots=256)["receipt"]
        b = pipeline.draw("lottery", {}, "replay", scenario="again")["receipt"]
        self.assertEqual((a["replay_of"], b["replay_of"]), (src, src))

    def test_successful_live_run_becomes_a_future_fallback_source_when_hardware(self):
        # a real live run has source 'hardware' and no replay_of, so it is eligible as the next fallback
        src = self.record_hardware()
        self.assertEqual(pipeline._latest_source("lottery", hardware_only=True), src)


class LiveApiTests(LiveBase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        router._live_cache.update(at=0.0, val=None)
        self.c = TestClient(app, headers={"X-API-Key": PROVA_API_KEY})

    def test_mode_lists_live(self):
        self.assertIn("live", self.c.get("/v3/mode").json()["modes"])

    def test_live_status_usable_and_not(self):
        self.record_hardware("lottery")
        with probe(pending=0):
            s = self.c.get("/v3/live/status").json()
        self.assertTrue(s["live_usable"])
        self.assertFalse(s["can_fall_back"])                 # only lottery has a saved hardware run
        self.assertEqual(s["recorded_hardware_runs"]["lottery"], 1)
        router._live_cache.update(at=0.0, val=None)
        with probe(pending=12, backend="ibm_fez"):
            s = self.c.get("/v3/live/status").json()
        self.assertFalse(s["live_usable"])
        self.assertIn("12 jobs queued on ibm_fez", s["reason"])
        router._live_cache.update(at=0.0, val=None)
        with probe(ok=False, error="offline"):
            s = self.c.get("/v3/live/status").json()
        self.assertFalse(s["reachable"])
        self.assertIn("offline", s["reason"])

    def test_live_status_requires_key(self):
        self.assertEqual(TestClient(app).get("/v3/live/status").status_code, 401)

    def test_live_draw_over_http_falls_back_and_503s(self):
        with probe(pending=3):
            r = self.c.post("/v3/lottery/draw", json={"mode": "live", "shots": 256})
        self.assertEqual(r.status_code, 503)
        self.record_hardware()
        with probe(pending=3):
            j = self.c.post("/v3/lottery/draw", json={"mode": "live", "shots": 256}).json()
        self.assertEqual(j["receipt"]["badge"]["live"], "fallback")
        self.assertEqual(j["receipt"]["badge"]["text"], "HARDWARE (recorded)")

    def test_default_mode_can_be_live(self):
        with mock.patch.object(router, "DEFAULT_MODE", "live"):
            self.assertEqual(self.c.get("/v3/mode").json()["default"], "live")
            self.record_hardware()
            with probe(pending=2):
                j = self.c.post("/v3/lottery/draw", json={"shots": 256}).json()
        self.assertEqual(j["receipt"]["badge"]["live"], "fallback")


if __name__ == "__main__":
    unittest.main()
