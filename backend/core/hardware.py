"""Circuits and execution backends: Aer simulator, noisy fake backends, and IBM hardware.

Only `submit_job` / `collect_job` ever talk to IBM, and only when backend="open". qiskit_ibm_runtime is imported
lazily so the simulator path works without it.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

from core.chsh import SETTING_NAMES, SETTINGS, lhv_bits

_rigged_rng = np.random.default_rng(1337)   # a classical device with a fixed internal seed


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def chsh_circuit(theta_a: float, theta_b: float, entangle: bool = True) -> QuantumCircuit:
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    if entangle:
        qc.cx(0, 1)
    qc.barrier()
    qc.ry(-theta_a, 0)
    qc.ry(-theta_b, 1)
    qc.measure([0, 1], [0, 1])
    return qc


def build_circuits(entangle: bool = True) -> list[QuantumCircuit]:
    return [chsh_circuit(*SETTINGS[n], entangle=entangle) for n in SETTING_NAMES]


def _aer(backend: str):
    """Returns (simulator, fake_backend_or_None). Fake backends bring that device's noise model."""
    from qiskit_aer import AerSimulator
    if backend == "aer":
        return AerSimulator(), None
    if backend.startswith("fake:"):
        from qiskit_ibm_runtime import fake_provider
        fake = getattr(fake_provider, backend.split(":", 1)[1])()
        return AerSimulator.from_backend(fake), fake
    raise ValueError(f"unknown simulator backend {backend!r}")


def run_sim(shots: int = 1024, entangle: bool = True, backend: str = "aer") -> tuple[dict, dict]:
    """Per-shot bitstrings on a simulator. Returns (bits_by_setting, backend_info)."""
    sim, fake = _aer(backend)
    circuits, pair = build_circuits(entangle), None
    if fake is not None:
        from qiskit import transpile
        pair = list(best_pair(fake))
        circuits = transpile(circuits, fake, initial_layout=pair, optimization_level=1)
    res = sim.run(circuits, shots=shots, memory=True).result()
    bits = {n: res.get_memory(i) for i, n in enumerate(SETTING_NAMES)}
    return bits, {"backend": backend, "pair": pair, "shots": shots, "entangled": entangle}


def run_classical(shots: int = 1024) -> tuple[dict, dict]:
    """The 'rigged device': a stateful classical generator. Bell's theorem caps its S at 2."""
    return lhv_bits(_rigged_rng, shots), {"backend": "classical-lhv", "pair": None, "shots": shots, "entangled": False}


# ----------------------------------------------------------------- hardware helpers
def pair_score(target, q0: int, q1: int) -> float:
    """Two-qubit gate error plus readout error for a connected pair (lower is better)."""
    err = None
    for op in target.operation_names:
        props = target[op]
        if props and (q0, q1) in props and props[(q0, q1)] is not None and props[(q0, q1)].error is not None:
            err = props[(q0, q1)].error
            break
    ro = sum((target["measure"][(q,)].error or 0) for q in (q0, q1))
    return (err if err is not None else 1.0) + ro


def best_pair(backend) -> tuple[int, int]:
    t = backend.target
    return min(backend.coupling_map.get_edges(), key=lambda e: pair_score(t, *e))


def submit_job(run_dir, shots: int = 4096, entangle: bool = True, backend: str = "open",
               account: str = "open") -> dict:
    """Transpile on the best pair and submit. `backend` is "open" (real IBM) or "fake:<Name>" (local, no QPU time).

    Writes job_meta.json immediately. For fake backends the job runs locally and its bitstrings are stored in
    `_local_bits.json` so collect_job behaves the same as for a real job.
    """
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2 as Sampler

    run_dir = Path(run_dir)
    if backend == "open":
        from qiskit_ibm_runtime import QiskitRuntimeService
        service = QiskitRuntimeService(name=account)
        be = service.least_busy(operational=True, simulator=False, min_num_qubits=2)
        local = False
    elif backend.startswith("fake:"):
        from qiskit_ibm_runtime import fake_provider
        be = getattr(fake_provider, backend.split(":", 1)[1])()
        local = True
    else:
        raise ValueError("backend must be 'open' or 'fake:<Name>'")
    q0, q1 = best_pair(be)
    pm = generate_preset_pass_manager(optimization_level=1, backend=be, initial_layout=[q0, q1])
    isa = [pm.run(c) for c in build_circuits(entangle)]
    job = Sampler(mode=be).run(isa, shots=shots)
    meta = {"job_id": job.job_id(), "backend": be.name, "pair": [q0, q1], "shots": shots,
            "circuits": SETTING_NAMES, "entangled": entangle, "submitted": now(), "finished": None,
            "transpiled_depth": [c.depth() for c in isa], "source": "sim" if local else "hardware",
            "local": local}
    if local:
        bits = {n: pub.data.c.get_bitstrings() for n, pub in zip(SETTING_NAMES, job.result())}
        (run_dir / "_local_bits.json").write_text(json.dumps(bits))
    (run_dir / "job_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def collect_job(run_dir, account: str = "open") -> dict:
    """Fetch results for a submitted job and write bitstrings.json (per-shot, in order). Returns updated meta."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "job_meta.json").read_text())
    if meta.get("local"):
        bits = json.loads((run_dir / "_local_bits.json").read_text())
    else:
        from qiskit_ibm_runtime import QiskitRuntimeService
        job = QiskitRuntimeService(name=account).job(meta["job_id"])
        result = job.result()      # waits if not finished
        bits = {n: pub.data.c.get_bitstrings() for n, pub in zip(meta["circuits"], result)}
    meta["finished"] = now()
    (run_dir / "bitstrings.json").write_text(json.dumps(bits))
    (run_dir / "job_meta.json").write_text(json.dumps(meta, indent=2))
    return meta
