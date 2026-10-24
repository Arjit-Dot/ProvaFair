"""CHSH certification computed from per-shot bitstrings.

Settings follow S = E(A0B0) + E(A0B1) + E(A1B0) - E(A1B1). The pass rule is S - 3*sigma > 2.
"""
import math
import numpy as np

CLASSICAL_LIMIT = 2.0
QUANTUM_MAX = 2 * math.sqrt(2)
SIGMA_K = 3

SETTING_NAMES = ["A0B0", "A0B1", "A1B0", "A1B1"]
SETTINGS = {"A0B0": (0.0, math.pi / 4), "A0B1": (0.0, -math.pi / 4),
            "A1B0": (math.pi / 2, math.pi / 4), "A1B1": (math.pi / 2, -math.pi / 4)}
SIGNS = {"A0B0": 1, "A0B1": 1, "A1B0": 1, "A1B1": -1}


def chsh_from_bits(bits: dict) -> dict:
    """bits: {"A0B0": ["00","11",...], ...} -> certificate dict."""
    missing = [k for k in SETTING_NAMES if k not in bits or not bits[k]]
    if missing:
        raise ValueError(f"missing settings: {missing}")
    E, sig, n, S, var = {}, {}, {}, 0.0, 0.0
    for k in SETTING_NAMES:
        shots = bits[k]
        same = sum(1 for s in shots if s in ("00", "11"))
        n[k] = len(shots)
        E[k] = (2 * same - n[k]) / n[k]
        sig[k] = math.sqrt(max(1 - E[k] ** 2, 1e-12) / n[k])
        S += SIGNS[k] * E[k]
        var += sig[k] ** 2
    sigma = math.sqrt(var)
    lower = S - SIGMA_K * sigma
    return {
        "E": {k: round(E[k], 6) for k in SETTING_NAMES},
        "E_sigma": {k: round(sig[k], 6) for k in SETTING_NAMES},
        "shots": n,
        "S": round(S, 6), "sigma": round(sigma, 6), "threshold": CLASSICAL_LIMIT,
        "sigma_k": SIGMA_K, "lower_bound": round(lower, 6),
        "certified": bool(lower > CLASSICAL_LIMIT),
        "rule": f"Pass only if S - {SIGMA_K}σ > {CLASSICAL_LIMIT:g}",
    }


def lhv_bits(rng: np.random.Generator, shots: int) -> dict:
    """Best local-hidden-variable strategy, in the same per-shot format as hardware output."""
    out = {}
    for k in SETTING_NAMES:
        a, b = SETTINGS[k]
        lam = rng.uniform(0, 2 * math.pi, shots)
        A = (np.cos(a - lam) >= 0).astype(int)
        B = (np.cos(b - lam) >= 0).astype(int)
        out[k] = [f"{x}{y}" for x, y in zip(B, A)]
    return out
