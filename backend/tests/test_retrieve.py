"""Submit-ahead / retrieve-at-demo. IBM is faked: fetch_job_bits_safe is patched, nothing is sent anywhere."""
import json
import unittest
from unittest import mock

import helpers
from core import hardware, pipeline, store
from test_live import LiveBase, TestClient, router, PROVA_API_KEY, app


def ibm_returns(bits):
    return mock.patch.object(hardware, "fetch_job_bits_safe", return_value={"ok": True, "bits": bits})


def ibm_down(err="no answer from IBM within 30s"):
    return mock.patch.object(hardware, "fetch_job_bits_safe", return_value={"ok": False, "error": err})


class RetrieveTests(LiveBase, unittest.TestCase):
    def saved(self, service="lottery"):
        rid = self.record_hardware(service)
        return rid, json.loads((store.run_dir(service, rid) / "bitstrings.json").read_text())

    def test_retrieve_matching_bits_runs_the_full_pipeline_live(self):
        rid, bits = self.saved()
        with ibm_returns(bits) as f:
            out = pipeline.draw("lottery", {"pool": 30, "picks": 4}, "retrieve", scenario="demo")
            f.assert_called_once()
            self.assertEqual(f.call_args[0][0], "hw-job-1")           # asked IBM for the saved job id
        rc = out["receipt"]
        self.assertEqual(rc["status"], "CERTIFIED")
        self.assertEqual(rc["badge"]["text"], "HARDWARE (recorded, retrieved from IBM)")
        self.assertIsNone(rc["badge"]["note"])
        self.assertEqual(rc["retrieve_attempt"]["outcome"], "ibm")
        self.assertTrue(rc["retrieve_attempt"]["matches_local"])
        self.assertEqual(rc["replay_of"], rid)
        self.assertEqual(rc["job_id"], "hw-job-1")
        self.assertEqual(len(out["result"]["numbers"]), 4)             # new params really ran
        v = pipeline.verify_run("lottery", rc["run_id"])
        self.assertTrue(v["all_ok"], v)
        ids = [e["draw_id"] for e in self.ledger.all_entries()]        # written to the ledger now, commit first
        self.assertEqual(ids[-2:], [f"{rc['run_id']}:COMMIT", rc["run_id"]])

    def test_new_run_each_time_with_distinct_seed_per_scenario(self):
        rid, bits = self.saved()
        with ibm_returns(bits):
            a = pipeline.draw("lottery", {}, "retrieve", scenario="A")["receipt"]
            b = pipeline.draw("lottery", {}, "retrieve", scenario="B")["receipt"]
        self.assertNotEqual(a["seed_hash"], b["seed_hash"])
        self.assertNotEqual(a["run_id"], b["run_id"])

    def test_ibm_unreachable_uses_local_copy_and_says_so(self):
        rid, bits = self.saved()
        with ibm_down("no answer from IBM within 30s"):
            rc = pipeline.draw("lottery", {}, "retrieve")["receipt"]
        self.assertEqual(rc["status"], "CERTIFIED")
        self.assertEqual(rc["retrieve_attempt"]["outcome"], "local")
        self.assertEqual(rc["badge"]["text"], "HARDWARE (recorded)")           # not claimed as retrieved
        self.assertIn("Could not retrieve from IBM", rc["badge"]["note"])
        self.assertIn("no answer from IBM", rc["badge"]["note"])
        self.assertTrue(pipeline.verify_run("lottery", rc["run_id"])["all_ok"])

    def test_mismatch_between_ibm_and_local_copy_is_refused(self):
        rid, bits = self.saved()
        forged = json.loads(json.dumps(bits))
        forged["A0B0"][0] = "01" if forged["A0B0"][0] in ("00", "11") else "00"
        with ibm_returns(forged):
            with self.assertRaises(pipeline.PipelineError) as cm:
                pipeline.draw("lottery", {}, "retrieve")
        self.assertEqual(cm.exception.status, 409)
        self.assertIn("do not match", str(cm.exception))
        self.assertEqual(len(store.list_runs("lottery")), 1)                   # no run created

    def test_local_copy_tampered_is_caught_too(self):
        rid, bits = self.saved()
        d = store.run_dir("lottery", rid)
        local = json.loads((d / "bitstrings.json").read_text())
        local["A1B1"][5] = "01" if local["A1B1"][5] in ("00", "11") else "00"
        (d / "bitstrings.json").write_text(json.dumps(local))
        with ibm_returns(bits):                                                # IBM has the original
            with self.assertRaises(pipeline.PipelineError) as cm:
                pipeline.draw("lottery", {}, "retrieve")
        self.assertEqual(cm.exception.status, 409)

    def test_no_local_copy_but_ibm_ok_still_works(self):
        rid, bits = self.saved()
        (store.run_dir("lottery", rid) / "bitstrings.json").unlink()
        with ibm_returns(bits):
            rc = pipeline.draw("lottery", {}, "retrieve")["receipt"]
        self.assertIsNone(rc["retrieve_attempt"]["matches_local"])
        self.assertEqual(rc["badge"]["text"], "HARDWARE (recorded, retrieved from IBM)")

    def test_no_local_copy_and_ibm_down_is_a_clear_503(self):
        rid, bits = self.saved()
        (store.run_dir("lottery", rid) / "bitstrings.json").unlink()
        with ibm_down():
            with self.assertRaises(pipeline.PipelineError) as cm:
                pipeline.draw("lottery", {}, "retrieve")
        self.assertEqual(cm.exception.status, 503)

    def test_only_real_hardware_runs_can_be_retrieved(self):
        sim = pipeline.draw("web3", {}, "sim", shots=256)["receipt"]["run_id"]
        with self.assertRaises(pipeline.PipelineError) as cm:
            pipeline.draw("web3", {}, "retrieve", source_run=sim)
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(pipeline.PipelineError) as cm:                  # nothing recorded at all
            pipeline.draw("keys", {}, "retrieve")
        self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(pipeline.PipelineError) as cm:
            pipeline.draw("lottery", {}, "retrieve", source_run="LOTTERY-nope")
        self.assertEqual(cm.exception.status, 404)

    def test_blocked_source_cannot_be_retrieved(self):
        rid = self.record_hardware()
        d = store.run_dir("lottery", rid)
        c = json.loads((d / "certificate.json").read_text()); c["certified"] = False
        (d / "certificate.json").write_text(json.dumps(c))
        with self.assertRaises(pipeline.PipelineError):
            pipeline.draw("lottery", {}, "retrieve", source_run=rid)

    def test_fabricated_bits_from_ibm_that_fail_the_bell_test_would_be_blocked(self):
        # no local copy, so nothing to mismatch against; classical bits must still be BLOCKED by certification
        rid, bits = self.saved()
        (store.run_dir("lottery", rid) / "bitstrings.json").unlink()
        lhv, _ = hardware.run_classical(512)
        with ibm_returns(lhv):
            out = pipeline.draw("lottery", {}, "retrieve")
        self.assertEqual(out["receipt"]["status"], "BLOCKED")
        self.assertIsNone(out["result"])

    def test_retrieve_never_submits_a_job(self):
        rid, bits = self.saved()
        with ibm_returns(bits), mock.patch.object(hardware, "submit_job") as sub:
            pipeline.draw("lottery", {}, "retrieve")
            sub.assert_not_called()
        self.assertEqual(pipeline._live_used, 0)


class RetrieveApiTests(LiveBase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.c = TestClient(app, headers={"X-API-Key": PROVA_API_KEY})

    def test_mode_and_draw_over_http(self):
        self.assertIn("retrieve", self.c.get("/v3/mode").json()["modes"])
        rid = self.record_hardware()
        bits = json.loads((store.run_dir("lottery", rid) / "bitstrings.json").read_text())
        with ibm_returns(bits):
            j = self.c.post("/v3/lottery/draw", json={"mode": "retrieve", "scenario": "x"}).json()
        self.assertEqual(j["receipt"]["badge"]["text"], "HARDWARE (recorded, retrieved from IBM)")
        forged = {k: list(v) for k, v in bits.items()}
        forged["A0B0"][0] = "01" if forged["A0B0"][0] in ("00", "11") else "00"
        with ibm_returns(forged):
            r = self.c.post("/v3/lottery/draw", json={"mode": "retrieve"})
        self.assertEqual(r.status_code, 409)

    def test_fetch_job_bits_safe_never_raises_or_hangs(self):
        import time
        with mock.patch.object(hardware, "get_service", side_effect=OSError("offline")):
            r = hardware.fetch_job_bits_safe("j", None, 2.0)
        self.assertFalse(r["ok"]); self.assertIn("offline", r["error"])
        with mock.patch.object(hardware, "fetch_job_bits", side_effect=lambda *a: time.sleep(3)):
            t = time.time(); r = hardware.fetch_job_bits_safe("j", None, 0.3)
        self.assertLess(time.time() - t, 1.5); self.assertIn("no answer", r["error"])

    def test_fetch_requires_a_done_job(self):
        job = mock.Mock(); job.status.return_value = "QUEUED"
        svc = mock.Mock(); svc.job.return_value = job
        with mock.patch.object(hardware, "get_service", return_value=svc):
            with self.assertRaisesRegex(RuntimeError, "QUEUED"):
                hardware.fetch_job_bits("j")


if __name__ == "__main__":
    unittest.main()
