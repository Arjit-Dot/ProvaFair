import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

import helpers
from core import pipeline, store

SERVICES = ("ipo", "web3", "lottery", "keys")
PY = sys.executable


def failed(v):
    return [c["id"] for c in v["checks"] if not c["ok"]]


class PipelineTests(helpers.Isolated, unittest.TestCase):
    def test_every_service_certifies_and_all_five_checks_tick(self):
        for s in SERVICES:
            out = pipeline.draw(s, {}, "sim", shots=512)
            rc = out["receipt"]
            self.assertEqual(rc["status"], "CERTIFIED", s)
            self.assertEqual(rc["badge"]["text"], "SIMULATOR")
            self.assertTrue(rc["params_hash"] and rc["seed_hash"] and rc["ledger_hash"])
            v = pipeline.verify_run(s, rc["run_id"])
            self.assertTrue(v["all_ok"], (s, v))
            self.assertEqual(len(v["checks"]), 5)

    def test_run_folder_contents(self):
        out = pipeline.draw("lottery", {}, "sim", shots=256)
        d = store.run_dir("lottery", out["receipt"]["run_id"])
        for f in ("params.json", "params_hash.txt", "job_meta.json", "bitstrings.json", "certificate.json",
                  "result.json", "receipt.json"):
            self.assertTrue((d / f).exists(), f)
        bits = json.loads((d / "bitstrings.json").read_text())
        self.assertEqual({k: len(v) for k, v in bits.items()}, {k: 256 for k in ("A0B0", "A0B1", "A1B0", "A1B1")})

    def test_commit_entry_precedes_result_in_ledger(self):
        out = pipeline.draw("ipo", {}, "sim", shots=256)
        rid = out["receipt"]["run_id"]
        e = self.ledger.all_entries()
        ids = [x["draw_id"] for x in e]
        self.assertEqual(ids, [f"{rid}:COMMIT", rid])
        self.assertEqual(e[0]["winners"], [out["receipt"]["params_hash"]])
        self.assertTrue(self.ledger.verify_chain()["intact"])

    def test_control_and_classical_blocked_fail_closed(self):
        for mode, badge in (("control", "SIMULATOR (control, no entanglement)"), ("classical", "CLASSICAL")):
            for s in SERVICES:
                out = pipeline.draw(s, {}, mode, shots=512)
                rc = out["receipt"]
                self.assertEqual(rc["status"], "BLOCKED", (mode, s))
                self.assertIsNone(out["result"])
                self.assertIsNone(rc["seed_hash"])
                self.assertNotIn("demo_keys", out)
                self.assertEqual(rc["badge"]["text"], badge)
                self.assertTrue(pipeline.verify_run(s, rc["run_id"])["all_ok"])   # a blocked run still verifies

    def test_replay_uses_recorded_bits_and_is_never_live(self):
        src = pipeline.draw("lottery", {}, "sim", shots=512)["receipt"]
        a = pipeline.draw("lottery", {}, "replay", scenario="A")["receipt"]
        b = pipeline.draw("lottery", {}, "replay", scenario="B")["receipt"]
        for r in (a, b):
            self.assertTrue(r["badge"]["replayed"])
            self.assertEqual(r["badge"]["text"], "SIMULATOR (replayed)")
            self.assertEqual(r["replay_of"], src["run_id"])
            self.assertEqual(r["job_id"], src["job_id"])
            self.assertTrue(pipeline.verify_run("lottery", r["run_id"])["all_ok"])
        self.assertNotEqual(a["seed_hash"], b["seed_hash"])           # distinct scenario -> distinct seed
        self.assertNotEqual(a["seed_hash"], src["seed_hash"])
        # replay of a replay still points at the original run
        c = pipeline.draw("lottery", {}, "replay", scenario="C", source_run=a["run_id"])["receipt"]
        self.assertEqual(c["replay_of"], src["run_id"])

    def test_replay_changed_params_reruns_algorithm_only(self):
        pipeline.draw("lottery", {}, "sim", shots=256)
        r = pipeline.draw("lottery", {"pool": 10, "picks": 3}, "replay", scenario="small")
        self.assertEqual(len(r["result"]["numbers"]), 3)
        self.assertTrue(all(1 <= n <= 10 for n in r["result"]["numbers"]))

    def test_replay_without_recording_is_a_clear_404_and_leaves_no_run(self):
        with self.assertRaises(pipeline.PipelineError) as cm:
            pipeline.draw("ipo", {}, "replay")
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(store.list_runs("ipo"), [])
        self.assertFalse(any((store.root() / "ipo").iterdir()) if (store.root() / "ipo").exists() else False)

    def test_cannot_replay_a_blocked_run(self):
        blocked = pipeline.draw("ipo", {}, "classical", shots=256)["receipt"]["run_id"]
        with self.assertRaises(pipeline.PipelineError):
            pipeline.draw("ipo", {}, "replay", source_run=blocked)

    def test_invalid_inputs(self):
        for kw, status in (({"params": {"lot_size": 0}}, 422), ({"shots": 10}, 422), ({"mode": "bogus"}, 422)):
            with self.assertRaises(pipeline.PipelineError) as cm:
                pipeline.draw("ipo", kw.get("params", {}), kw.get("mode", "sim"), shots=kw.get("shots", 256))
            self.assertEqual(cm.exception.status, status)
        with self.assertRaises(pipeline.PipelineError) as cm:
            pipeline.draw("nope", {})
        self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(ValueError):
            store.run_dir("ipo", "../../etc")

    def test_noisy_fake_backend_run_certifies_with_lower_S(self):
        out = pipeline.draw("web3", {}, "sim", shots=1024, backend="fake:FakeKingston")
        self.assertEqual(out["receipt"]["status"], "CERTIFIED")
        self.assertLess(out["receipt"]["S"], 2.83)
        self.assertTrue(pipeline.verify_run("web3", out["receipt"]["run_id"])["all_ok"])


class TamperTests(helpers.Isolated, unittest.TestCase):
    def make(self, service="lottery"):
        out = pipeline.draw(service, {}, "sim", shots=512)
        rid = out["receipt"]["run_id"]
        return rid, store.run_dir(service, rid)

    def edit(self, d, name, fn):
        obj = json.loads((d / name).read_text())
        fn(obj)
        (d / name).write_text(json.dumps(obj, indent=2, sort_keys=True))

    def test_tamper_params(self):
        rid, d = self.make()
        self.edit(d, "params.json", lambda o: o["params"].__setitem__("picks", 5))
        self.assertIn(1, failed(pipeline.verify_run("lottery", rid)))

    def test_tamper_one_bitstring(self):
        rid, d = self.make()
        def flip(o):
            o["A0B0"][0] = "01" if o["A0B0"][0] in ("00", "11") else "00"
        self.edit(d, "bitstrings.json", flip)
        f = failed(pipeline.verify_run("lottery", rid))
        self.assertIn(2, f)          # certificate no longer matches the bits
        self.assertIn(3, f)          # seed no longer matches

    def test_tamper_result(self):
        rid, d = self.make()
        self.edit(d, "result.json", lambda o: o["result"].__setitem__("numbers", [1, 2, 3, 4, 5, 6]))
        f = failed(pipeline.verify_run("lottery", rid))
        self.assertIn(4, f)
        self.assertIn(5, f)          # result hash no longer matches the ledger

    def test_tamper_ledger_entry(self):
        rid, d = self.make()
        con = sqlite3.connect(self.ledger.DB)
        con.execute("UPDATE chain SET winners=? WHERE draw_id=?", (json.dumps(["x", "y", "z"]), rid))
        con.commit()
        v = pipeline.verify_run("lottery", rid)
        self.assertEqual(failed(v), [3, 5])  # seed hash from ledger + chain/hash check

    def test_tamper_commit_entry(self):
        rid, d = self.make()
        con = sqlite3.connect(self.ledger.DB)
        con.execute("UPDATE chain SET winners=? WHERE draw_id=?", (json.dumps(["deadbeef"]), f"{rid}:COMMIT"))
        con.commit()
        f = failed(pipeline.verify_run("lottery", rid))
        self.assertIn(1, f)
        self.assertIn(5, f)

    def test_delete_commit_entry(self):
        rid, d = self.make()
        con = sqlite3.connect(self.ledger.DB)
        con.execute("DELETE FROM chain WHERE draw_id=?", (f"{rid}:COMMIT",))
        con.commit()
        self.assertIn(1, failed(pipeline.verify_run("lottery", rid)))

    def test_forged_certificate_on_blocked_run(self):
        # swap a blocked run's bits for quantum bits: the stored certificate (blocked) no longer matches
        out = pipeline.draw("lottery", {}, "control", shots=512)
        rid = out["receipt"]["run_id"]
        d = store.run_dir("lottery", rid)
        from core import hardware
        (d / "bitstrings.json").write_text(json.dumps(hardware.run_sim(512, True)[0]))
        self.assertIn(2, failed(pipeline.verify_run("lottery", rid)))

    def test_blocked_run_with_injected_output_fails(self):
        out = pipeline.draw("lottery", {}, "classical", shots=256)
        rid = out["receipt"]["run_id"]
        d = store.run_dir("lottery", rid)
        self.edit(d, "result.json", lambda o: o.update(result={"numbers": [1, 2, 3, 4, 5, 6]}))
        self.assertIn(4, failed(pipeline.verify_run("lottery", rid)))

    def test_keys_receipt_tamper_detected(self):
        rid, d = self.make("keys")
        self.edit(d, "result.json", lambda o: o["result"]["quantum_component_fingerprints"].__setitem__(0, "00"))
        self.assertIn(4, failed(pipeline.verify_run("keys", rid)))

    def test_untampered_after_other_activity_stays_valid(self):
        rid, _ = self.make()
        for s in SERVICES:
            pipeline.draw(s, {}, "sim", shots=256)
        self.assertTrue(pipeline.verify_run("lottery", rid)["all_ok"])

    def test_missing_files_do_not_crash(self):
        rid, d = self.make()
        (d / "bitstrings.json").unlink()
        v = pipeline.verify_run("lottery", rid)
        self.assertFalse(v["all_ok"])
        with self.assertRaises(pipeline.PipelineError):
            pipeline.verify_run("lottery", "LOTTERY-nonexistent")


class ScriptTests(helpers.Isolated, unittest.TestCase):
    def run_script(self, *args):
        env = {**os.environ, "PROVAFAIR_LEDGER_DB": self.ledger.DB}
        return subprocess.run([PY, *args], cwd=helpers.BACKEND, env=env, capture_output=True, text=True, timeout=300)

    def test_submit_collect_on_fake_provider_produces_verifiable_run(self):
        o = self.run_script("scripts/submit.py", "--service", "ipo", "--backend", "fake:FakeKingston", "--shots", "512")
        self.assertEqual(o.returncode, 0, o.stderr[-800:])
        rid = o.stdout.split("run_id = ")[1].split()[0]
        d = store.run_dir("ipo", rid)
        self.assertTrue((d / "job_meta.json").exists())          # written immediately on submit
        self.assertFalse((d / "bitstrings.json").exists())       # not collected yet
        self.assertEqual([x["draw_id"] for x in self.ledger.all_entries()], [f"{rid}:COMMIT"])   # committed before results
        o = self.run_script("scripts/collect.py", "--service", "ipo", "--run-id", rid)
        self.assertEqual(o.returncode, 0, o.stderr[-800:])
        self.assertIn("CERTIFIED", o.stdout)
        self.assertEqual(o.stdout.count("[x]"), 5)
        self.assertTrue(pipeline.verify_run("ipo", rid)["all_ok"])
        meta = json.loads((d / "job_meta.json").read_text())
        self.assertEqual(meta["backend"], "fake_kingston")
        self.assertEqual(len(meta["pair"]), 2)
        self.assertIsNotNone(meta["finished"])

    def test_submit_control_circuit_is_blocked_on_fake_provider(self):
        o = self.run_script("scripts/submit.py", "--service", "keys", "--backend", "fake:FakeKingston",
                            "--shots", "512", "--control")
        self.assertEqual(o.returncode, 0, o.stderr[-800:])
        rid = o.stdout.split("run_id = ")[1].split()[0]
        o = self.run_script("scripts/collect.py", "--service", "keys", "--run-id", rid)
        self.assertIn("BLOCKED", o.stdout)
        self.assertTrue(pipeline.verify_run("keys", rid)["all_ok"])
        self.assertEqual(json.loads((store.run_dir("keys", rid) / "job_meta.json").read_text())["entangled"], False)

    def test_open_backend_without_credentials_fails_cleanly_before_any_job(self):
        # must not hang or spend anything: no saved account named 'nonexistent-account-xyz'
        o = self.run_script("scripts/submit.py", "--service", "ipo", "--backend", "open", "--account",
                            "nonexistent-account-xyz", "--shots", "256")
        self.assertNotEqual(o.returncode, 0)


if __name__ == "__main__":
    unittest.main()


class UnrelatedLedgerBreakTests(helpers.Isolated, unittest.TestCase):
    def test_unrelated_tampered_entry_does_not_invalidate_a_run_but_is_reported(self):
        # an old, unrelated entry is forged BEFORE this run exists (like the demo 'tamper' button)
        self.ledger.append("OLD-1", "sim", "demo", 2.8, 0.05, 100, "CERTIFIED", ["a"])
        self.ledger.tamper("OLD-1")
        out = pipeline.draw("lottery", {}, "sim", shots=256)
        v = pipeline.verify_run("lottery", out["receipt"]["run_id"])
        self.assertTrue(v["all_ok"], v)
        self.assertIn("unrelated break at OLD-1", v["checks"][4]["detail"])

    def test_entry_between_commit_and_result_tampered_fails(self):
        out = pipeline.draw("lottery", {}, "sim", shots=256)
        rid = out["receipt"]["run_id"]
        self.ledger.tamper(rid)                      # alters the run's own entry
        self.assertIn(5, failed(pipeline.verify_run("lottery", rid)))
