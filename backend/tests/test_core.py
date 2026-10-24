import unittest

import numpy as np

import helpers  # noqa: F401
from core import chsh, hardware
from core.stream import Stream, hkdf, sample, shuffle

SEED = bytes(range(32))


class StreamTests(unittest.TestCase):
    def test_deterministic_same_seed_and_label(self):
        a, b = Stream(SEED, "x"), Stream(SEED, "x")
        self.assertEqual([a.randbelow(1000) for _ in range(50)], [b.randbelow(1000) for _ in range(50)])

    def test_labels_and_seeds_diverge(self):
        base = [Stream(SEED, "x").randbelow(10**9) for _ in range(1)]
        self.assertNotEqual(base, [Stream(SEED, "y").randbelow(10**9)])
        self.assertNotEqual(base, [Stream(bytes(32), "x").randbelow(10**9)])

    def test_randbelow_uniform_chi_square(self):
        # fixed seed, so deterministic. df=n-1, critical values at p=0.001
        for n, crit in ((7, 22.46), (10, 27.88), (100, 148.2), (6, 20.52)):
            st, draws = Stream(SEED, f"chi{n}"), 200 * n
            counts = np.bincount([st.randbelow(n) for _ in range(draws)], minlength=n)
            chi = ((counts - draws / n) ** 2 / (draws / n)).sum()
            self.assertLess(chi, crit, f"n={n} chi2={chi:.1f}")
            self.assertEqual(counts.sum(), draws)

    def test_randbelow_edges(self):
        st = Stream(SEED, "e")
        self.assertEqual(st.randbelow(1), 0)
        with self.assertRaises(ValueError):
            st.randbelow(0)
        self.assertTrue(all(0 <= st.randbelow(2**70 + 1) <= 2**70 for _ in range(20)))

    def test_shuffle_is_permutation_and_deterministic(self):
        items = list(range(500))
        a, b = shuffle(items, Stream(SEED, "s")), shuffle(items, Stream(SEED, "s"))
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), items)
        self.assertNotEqual(a, items)

    def test_shuffle_position_uniform(self):
        # first element of a 5-item shuffle should be uniform over 5 values
        counts = np.zeros(5)
        for i in range(2000):
            counts[shuffle(range(5), Stream(i.to_bytes(8, "big"), "p"))[0]] += 1
        chi = ((counts - 400) ** 2 / 400).sum()
        self.assertLess(chi, 18.47)   # df=4, p=0.001

    def test_sample_distinct_and_in_range(self):
        out = sample(49, 7, Stream(SEED, "k"))
        self.assertEqual(len(set(out)), 7)
        self.assertTrue(all(0 <= x < 49 for x in out))
        with self.assertRaises(ValueError):
            sample(5, 6, Stream(SEED, "k"))

    def test_hkdf_rfc5869_vector(self):
        # RFC 5869 test case 1
        ikm = bytes.fromhex("0b" * 22)
        salt = bytes.fromhex("000102030405060708090a0b0c")
        info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
        okm = hkdf(ikm, info, 42, salt)
        self.assertEqual(okm.hex(), "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")


class ChshTests(unittest.TestCase):
    def test_aer_entangled_certified(self):
        for _ in range(3):
            bits, _ = hardware.run_sim(1024, True)
            c = chsh.chsh_from_bits(bits)
            self.assertTrue(c["certified"], c)
            self.assertGreater(c["S"], 2.6)
            self.assertLessEqual(c["S"], 3.0)

    def test_control_no_entanglement_blocked(self):
        c = chsh.chsh_from_bits(hardware.run_sim(1024, False)[0])
        self.assertFalse(c["certified"])
        self.assertLessEqual(c["S"], 2.0)

    def test_classical_lhv_blocked_many_times(self):
        for _ in range(20):
            c = chsh.chsh_from_bits(hardware.run_classical(1024)[0])
            self.assertFalse(c["certified"], c)

    def test_noisy_fake_backend_lower_but_honest(self):
        bits, info = hardware.run_sim(2048, True, "fake:FakeKingston")
        c = chsh.chsh_from_bits(bits)
        self.assertGreater(c["S"], 2.0)
        self.assertLess(c["S"], 2.83)      # noise must lower it below the ideal
        self.assertEqual(len(info["pair"]), 2)

    def test_pass_rule_boundary(self):
        # Hand-built bits: E=+/-0.5 on every term gives S=2.0 exactly -> not certified
        def mk(e, n=1000):
            same = int((e + 1) / 2 * n)
            return ["00"] * same + ["01"] * (n - same)
        bits = {"A0B0": mk(.5), "A0B1": mk(.5), "A1B0": mk(.5), "A1B1": mk(-.5)}
        c = chsh.chsh_from_bits(bits)
        self.assertAlmostEqual(c["S"], 2.0, places=6)
        self.assertFalse(c["certified"])

    def test_missing_setting_rejected(self):
        with self.assertRaises(ValueError):
            chsh.chsh_from_bits({"A0B0": ["00"]})

    def test_bitstrings_are_per_shot_and_ordered(self):
        bits, _ = hardware.run_sim(256, True)
        self.assertTrue(all(len(v) == 256 and all(s in ("00", "01", "10", "11") for s in v) for v in bits.values()))


if __name__ == "__main__":
    unittest.main()
