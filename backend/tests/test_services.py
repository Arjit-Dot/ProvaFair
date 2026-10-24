import json
import os
import sqlite3
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

import helpers
from core import pipeline, store
from services import ipo, keys, lottery, web3

SEED = bytes(range(32))


def seeds(n):
    return (i.to_bytes(8, "big") * 4 for i in range(n))


class IpoTests(unittest.TestCase):
    def test_undersubscribed_everyone_allotted(self):
        p = ipo.normalize({"n_applicants": 100})            # 350,000 retail shares / 100 = 3500 lots
        r = ipo.compute(p, SEED, "a")
        self.assertEqual(r["lots_available"], 3500)
        self.assertFalse(r["oversubscribed"])
        self.assertEqual(len(r["allottees"]), 100)
        self.assertEqual(r["waiting_list"], [])

    def test_oversubscribed_exact_winners_no_duplicates_full_permutation(self):
        p = ipo.normalize({"n_applicants": 5000})
        r = ipo.compute(p, SEED, "a")
        self.assertTrue(r["oversubscribed"])
        self.assertEqual(len(r["allottees"]), 3500)
        self.assertEqual(len(set(r["allottees"])), 3500)
        self.assertEqual(len(r["waiting_list"]), 1500)
        self.assertEqual(sorted(r["allottees"] + r["waiting_list"]), [f"APP-{i:06d}" for i in range(1, 5001)])
        self.assertEqual(r["oversubscription_ratio"], round(5000 / 3500, 4))

    def test_heavy_oversubscription_and_floor(self):
        p = ipo.normalize({"total_shares": 10_050, "retail_pct": 100, "lot_size": 100, "n_applicants": 1000})
        r = ipo.compute(p, SEED, "a")
        self.assertEqual(r["lots_available"], 100)          # floor(10050 / 100)
        self.assertEqual(len(r["allottees"]), 100)

    def test_allotment_is_fair_over_many_seeds(self):
        p = ipo.normalize({"total_shares": 10_000, "retail_pct": 100, "lot_size": 1000, "n_applicants": 20})  # 10 of 20
        wins = Counter()
        for s in seeds(2000):
            wins.update(ipo.compute(p, s, "f")["allottees"])
        freqs = np.array([wins[f"APP-{i:06d}"] for i in range(1, 21)])
        chi = ((freqs - 1000) ** 2 / 1000).sum()
        self.assertLess(chi, 43.8)                          # df=19, p=0.001

    def test_explicit_applicants_and_validation(self):
        p = ipo.normalize({"applicants": [{"id": "x", "lots": 2}, {"id": "y"}], "total_shares": 1000,
                           "retail_pct": 100, "lot_size": 1000})
        self.assertEqual(ipo.compute(p, SEED, "a")["lots_available"], 1)
        for bad in ({"applicants": [{"id": "a"}, {"id": "a"}]}, {"lot_size": 0}, {"retail_pct": 0},
                    {"retail_pct": 101}, {"n_applicants": 0}, {"applicants": [{"id": ""}]},
                    {"applicants": [{"id": "a", "lots": 0}]}, {"total_shares": "abc"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                ipo.normalize(bad)

    def test_deterministic(self):
        p = ipo.normalize({})
        self.assertEqual(ipo.compute(p, SEED, "a"), ipo.compute(p, SEED, "a"))
        self.assertNotEqual(ipo.compute(p, SEED, "a"), ipo.compute(p, SEED, "b"))


class Web3Tests(unittest.TestCase):
    def test_no_repeats_right_size_and_beacon(self):
        p = web3.normalize({"n_validators": 20, "seats": 5, "epoch_id": 3})
        r = web3.compute(p, SEED, "a")
        ids = [v["id"] for v in r["committee"]]
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(len(bytes.fromhex(r["beacon"])), 32)

    def test_all_seats_selects_everyone(self):
        p = web3.normalize({"n_validators": 12, "seats": 12})
        self.assertEqual(len({v["id"] for v in web3.compute(p, SEED, "a")["committee"]}), 12)

    def test_stake_weighted_frequency(self):
        p = web3.normalize({"validators": [{"id": "big", "stake": 700}, {"id": "mid", "stake": 200},
                                           {"id": "small", "stake": 100}], "seats": 1})
        c = Counter(web3.compute(p, s, "w")["committee"][0]["id"] for s in seeds(4000))
        for k, share in (("big", .7), ("mid", .2), ("small", .1)):
            self.assertAlmostEqual(c[k] / 4000, share, delta=0.035)

    def test_uneven_default_stakes_chi_square(self):
        p = web3.normalize({"n_validators": 10, "seats": 1})
        stakes = {v["id"]: v["stake"] for v in web3._gen(10)}
        self.assertGreater(len(set(stakes.values())), 3)    # genuinely uneven
        total, n = sum(stakes.values()), 6000
        c = Counter(web3.compute(p, s, "w")["committee"][0]["id"] for s in seeds(n))
        chi = sum((c[k] - n * v / total) ** 2 / (n * v / total) for k, v in stakes.items())
        self.assertLess(chi, 27.88)                         # df=9, p=0.001

    def test_epoch_changes_beacon_label_changes_committee(self):
        a = web3.compute(web3.normalize({"epoch_id": 1}), SEED, "a")
        b = web3.compute(web3.normalize({"epoch_id": 2}), SEED, "a")
        self.assertNotEqual(a["beacon"], b["beacon"])
        self.assertNotEqual(web3.compute(web3.normalize({}), SEED, "x")["beacon"],
                            web3.compute(web3.normalize({}), SEED, "y")["beacon"])

    def test_validation(self):
        for bad in ({"seats": 0}, {"n_validators": 3, "seats": 4}, {"epoch_id": -1},
                    {"validators": [{"id": "a", "stake": 0}]}, {"validators": [{"id": "a", "stake": 1}, {"id": "a", "stake": 1}]}):
            with self.assertRaises(ValueError, msg=str(bad)):
                web3.normalize(bad)


class LotteryTests(unittest.TestCase):
    def test_6_of_49(self):
        for s in seeds(50):
            r = lottery.compute(lottery.normalize({}), s, "l")
            self.assertEqual(len(r["numbers"]), 6)
            self.assertEqual(r["numbers"], sorted(set(r["numbers"])))
            self.assertTrue(all(1 <= n <= 49 for n in r["numbers"]))
            self.assertIsNone(r["bonus"])

    def test_bonus_distinct_from_main(self):
        for s in seeds(50):
            r = lottery.compute(lottery.normalize({"bonus": True}), s, "l")
            self.assertNotIn(r["bonus"], r["numbers"])
            self.assertTrue(1 <= r["bonus"] <= 49)

    def test_number_frequency_uniform(self):
        n = 3000
        c = Counter(x for s in seeds(n) for x in lottery.compute(lottery.normalize({}), s, "u")["numbers"])
        exp = n * 6 / 49
        chi = sum((c[i] - exp) ** 2 / exp for i in range(1, 50))
        self.assertLess(chi, 85.4)                          # df=48, p=0.001

    def test_ticket_draw_10000_no_duplicates(self):
        p = lottery.normalize({"game": "tickets", "n_tickets": 10000,
                               "tiers": [{"name": "Grand", "winners": 1}, {"name": "Second", "winners": 49}]})
        r = lottery.compute(p, SEED, "t")
        allt = [t for tier in r["prizes"] for t in tier["tickets"]]
        self.assertEqual([len(t["tickets"]) for t in r["prizes"]], [1, 49])
        self.assertEqual(len(set(allt)), 50)
        self.assertTrue(all(1 <= int(t[2:]) <= 10000 for t in allt))

    def test_validation(self):
        for bad in ({"pool": 5, "picks": 6}, {"pool": 6, "picks": 6, "bonus": True}, {"game": "x"},
                    {"game": "tickets", "n_tickets": 5, "tiers": [{"name": "a", "winners": 6}]},
                    {"game": "tickets", "tiers": []}, {"picks": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                lottery.normalize(bad)


class KeysTests(unittest.TestCase):
    def test_keys_differ_by_index_and_purpose(self):
        p = keys.normalize({"count": 8})
        res, ks = keys.run(p, SEED, "a")
        self.assertEqual(len(set(ks)), 8)
        self.assertTrue(all(len(bytes.fromhex(k)) == 32 for k in ks))
        res2, _ = keys.run(keys.normalize({"count": 8, "purpose": "other"}), SEED, "a")
        self.assertNotEqual(res["quantum_component_fingerprints"], res2["quantum_component_fingerprints"])

    def test_same_seed_twice_differs_because_of_local_entropy(self):
        p = keys.normalize({})
        r1, k1 = keys.run(p, SEED, "a")
        r2, k2 = keys.run(p, SEED, "a")
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(r1["fingerprints"], r2["fingerprints"])
        self.assertEqual(r1["quantum_component_fingerprints"], r2["quantum_component_fingerprints"])

    def test_formats_and_lengths(self):
        for bits in (128, 256, 512):
            _, ks = keys.run(keys.normalize({"length_bits": bits, "format": "base64", "count": 2}), SEED, "a")
            import base64
            self.assertTrue(all(len(base64.b64decode(k)) == bits // 8 for k in ks))

    def test_result_has_no_key_material_and_demo_label(self):
        res, ks = keys.run(keys.normalize({}), SEED, "a")
        blob = json.dumps(res)
        self.assertTrue(all(k not in blob for k in ks))
        self.assertIn("demo keys", res["warning"])

    def test_validation(self):
        for bad in ({"length_bits": 100}, {"count": 0}, {"count": 65}, {"format": "pem"}, {"purpose": ""}):
            with self.assertRaises(ValueError, msg=str(bad)):
                keys.normalize(bad)


class KeysPipelineTests(helpers.Isolated, unittest.TestCase):
    def test_no_key_material_persisted_anywhere(self):
        out = pipeline.draw("keys", {"count": 3}, "sim", shots=256)
        self.assertEqual(len(out["demo_keys"]), 3)
        d = store.run_dir("keys", out["receipt"]["run_id"])
        blobs = "".join(p.read_text() for p in Path(d).iterdir())
        blobs += json.dumps(sqlite3.connect(self.ledger.DB).execute("select * from chain").fetchall())
        self.assertTrue(all(k not in blobs for k in out["demo_keys"]))
        self.assertNotIn("demo_keys", pipeline.get_run("keys", out["receipt"]["run_id"]))


if __name__ == "__main__":
    unittest.main()
