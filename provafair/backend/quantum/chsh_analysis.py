"""CHSH test with full evidence: per-setting correlations, error margins, circuit."""
import math
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

CLASSICAL_LIMIT = 2.0
QUANTUM_MAX = 2 * math.sqrt(2)
SIGMA_K = 3  # pass rule: S - 3*sigma > 2

ANGLES = {"A0": 0.0, "A1": math.pi / 2, "B0": math.pi / 4, "B1": -math.pi / 4}
# S = E(A0,B0) + E(A0,B1) + E(A1,B0) - E(A1,B1)
PAIRS = [("A0", "B0", +1), ("A0", "B1", +1), ("A1", "B0", +1), ("A1", "B1", -1)]

_SIM = AerSimulator()


def build_circuit(theta_a: float, theta_b: float) -> QuantumCircuit:
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)                      # Bell pair
    qc.barrier()
    qc.ry(-theta_a, 0)               # Alice measures at angle theta_a
    qc.ry(-theta_b, 1)               # Bob measures at angle theta_b
    qc.measure([0, 1], [0, 1])
    return qc


def circuits():
    return [build_circuit(ANGLES[a], ANGLES[b]) for a, b, _ in PAIRS]


def circuit_info() -> dict:
    qc = build_circuit(ANGLES["A0"], ANGLES["B0"])
    png = None
    try:
        import io, base64
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig = qc.draw("mpl", style="iqp-dark", scale=1.1)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, transparent=True, bbox_inches="tight")
        png = base64.b64encode(buf.getvalue()).decode()
        plt.close(fig)
    except Exception:
        pass
    return {
        "text": str(qc.draw("text")),
        "png_b64": png,
        "settings": [
            {"name": k, "angle_deg": round(math.degrees(v), 1)} for k, v in ANGLES.items()
        ],
        "caption": "This creates an entangled pair. Each side measures at a different angle.",
    }


def _summarise(n_same, n_diff, alice_bits, mode, shots):
    rows, S, var = [], 0.0, 0.0
    for (a, b, sign), same, diff in zip(PAIRS, n_same, n_diff):
        n = same + diff
        E = (same - diff) / n
        sig = math.sqrt(max(1 - E * E, 1e-12) / n)
        S += sign * E
        var += sig * sig
        rows.append({
            "pair": f"{a},{b}", "angle_a": round(math.degrees(ANGLES[a]), 1),
            "angle_b": round(math.degrees(ANGLES[b]), 1), "sign": sign,
            "n_same": int(same), "n_diff": int(diff), "E": round(E, 4), "sigma": round(sig, 4),
        })
    sigma = math.sqrt(var)
    lower = S - SIGMA_K * sigma
    summary = {
        "mode": mode, "S": round(S, 4), "sigma": round(sigma, 4),
        "margin": round(SIGMA_K * sigma, 4), "lower_bound": round(lower, 4),
        "certified": bool(lower > CLASSICAL_LIMIT),
        "shots_per_setting": shots, "total_shots": shots * 4,
        "correlations": rows, "rule": f"Pass only if S - {SIGMA_K}\u03c3 > {CLASSICAL_LIMIT:g}",
    }
    return summary, alice_bits


def run_quantum_chsh(shots: int = 1024):
    """Real circuit execution on Aer. Returns (summary, alice_bits)."""
    res = _SIM.run(circuits(), shots=shots, memory=True).result()
    same, diff, bits = [], [], []
    for i in range(4):
        mem = res.get_memory(i)  # 'b1 b0' strings, qubit0 = rightmost
        a = np.array([int(m[-1]) for m in mem], dtype=np.uint8)
        b = np.array([int(m[-2]) for m in mem], dtype=np.uint8)
        eq = int((a == b).sum())
        same.append(eq); diff.append(shots - eq); bits.append(a)
    return _summarise(same, diff, np.concatenate(bits), "quantum", shots)


def lhv_counts(rng, shots):
    """Best classical (local hidden variable) strategy: outputs are sign(cos(angle - lambda))."""
    same, diff, bits = [], [], []
    for a, b, _ in PAIRS:
        lam = rng.uniform(0, 2 * math.pi, shots)
        A = np.cos(ANGLES[a] - lam) >= 0
        B = np.cos(ANGLES[b] - lam) >= 0
        eq = int((A == B).sum())
        same.append(eq); diff.append(shots - eq); bits.append(A.astype(np.uint8))
    return same, diff, np.concatenate(bits)


def run_classical_chsh(rng, shots=1024):
    same, diff, bits = lhv_counts(rng, shots)
    return _summarise(same, diff, bits, "classical", shots)
