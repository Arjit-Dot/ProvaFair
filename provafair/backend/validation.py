"""500 vs 500 validation runs. Quantum runs execute real circuits on Aer in one batch."""
import json
import os
import numpy as np
from quantum import chsh_analysis as ch

CACHE = "validation_cache.json"


def _stats(S, sig):
    S, sig = np.array(S), np.array(sig)
    return {"S": [round(float(x), 4) for x in S], "mean": round(float(S.mean()), 4),
            "std": round(float(S.std(ddof=1)), 4), "min": round(float(S.min()), 4),
            "max": round(float(S.max()), 4),
            "passed": int(((S - ch.SIGMA_K * sig) > ch.CLASSICAL_LIMIT).sum()),
            "failed": int(((S - ch.SIGMA_K * sig) <= ch.CLASSICAL_LIMIT).sum()),
            "naive_above_2": int((S > 2).sum())}


def run_validation(runs: int = 500, shots: int = 1024, refresh: bool = False) -> dict:
    if not refresh and os.path.exists(CACHE):
        try:
            d = json.load(open(CACHE))
            if d["runs"] == runs and d["shots"] == shots:
                return d
        except Exception:
            pass
    circs = ch.circuits() * runs
    res = ch._SIM.run(circs, shots=shots).result()
    qS, qSig = [], []
    for r in range(runs):
        same, diff = [], []
        for i in range(4):
            counts = res.get_counts(r * 4 + i)
            eq = counts.get("00", 0) + counts.get("11", 0)
            same.append(eq); diff.append(shots - eq)
        s, _ = ch._summarise(same, diff, None, "quantum", shots)
        qS.append(s["S"]); qSig.append(s["sigma"])
    rng = np.random.default_rng()
    cS, cSig = [], []
    for _ in range(runs):
        s, _ = ch.run_classical_chsh(rng, shots)
        cS.append(s["S"]); cSig.append(s["sigma"])
    out = {"runs": runs, "shots": shots, "quantum": _stats(qS, qSig), "classical": _stats(cS, cSig),
           "classical_limit": ch.CLASSICAL_LIMIT, "quantum_max": round(ch.QUANTUM_MAX, 4)}
    json.dump(out, open(CACHE, "w"))
    return out
