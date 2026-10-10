"""Three standard checks on a bit stream. Pass threshold: p > 0.01 (chi-square: stat < 30.58)."""
import math
import numpy as np

ALPHA = 0.01
CHI2_CRIT_15DOF = 30.578  # alpha = 0.01


def frequency_test(bits):
    n = len(bits)
    ones = int(bits.sum())
    s = abs(2 * ones - n) / math.sqrt(n)
    p = math.erfc(s / math.sqrt(2))
    return {"name": "Frequency (0s vs 1s)", "stat": round(ones / n, 4), "p_value": round(p, 4),
            "detail": f"{ones} ones, {n - ones} zeros", "passed": p > ALPHA}


def runs_test(bits):
    n = len(bits)
    pi = bits.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return {"name": "Runs", "stat": 0, "p_value": 0.0, "detail": "Skipped: frequency too far off",
                "passed": False}
    v = 1 + int((bits[1:] != bits[:-1]).sum())
    p = math.erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi)))
    return {"name": "Runs", "stat": v, "p_value": round(p, 4), "detail": f"{v} runs observed",
            "passed": p > ALPHA}


def chi_square_test(bits):
    nib = len(bits) // 4
    vals = bits[: nib * 4].reshape(nib, 4) @ np.array([8, 4, 2, 1])
    counts = np.bincount(vals, minlength=16)
    exp = nib / 16
    chi = float(((counts - exp) ** 2 / exp).sum())
    return {"name": "Chi-square (4-bit blocks)", "stat": round(chi, 2), "p_value": None,
            "detail": f"{chi:.1f} vs limit {CHI2_CRIT_15DOF} (15 dof)", "passed": chi < CHI2_CRIT_15DOF}


def run_all(bits):
    bits = np.asarray(bits, dtype=np.uint8)
    tests = [frequency_test(bits), runs_test(bits), chi_square_test(bits)]
    return {"n_bits": int(len(bits)), "tests": tests, "all_passed": all(t["passed"] for t in tests),
            "ones_fraction": round(float(bits.mean()), 4)}
