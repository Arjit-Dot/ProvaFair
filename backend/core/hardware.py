"""Circuits and execution backends: Aer simulator, noisy fake backends, and IBM hardware.

Only `submit_job` / `collect_job` ever talk to IBM, and only when backend="open". qiskit_ibm_runtime is imported
lazily so the simulator path works without it.
"""
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

from core.chsh import SETTING_NAMES, SETTINGS, lhv_bits

_rigged_rng = np.random.default_rng(1337)   # a classical device with a fixed internal seed


_services: dict = {}
_backends: dict = {}


def get_service(account: str = "open"):
    """Cached QiskitRuntimeService (creating one takes ~5 s, which would blow the live-probe budget)."""
    if account not in _services:
        from qiskit_ibm_runtime import QiskitRuntimeService
        _services[account] = QiskitRuntimeService(name=account)
    return _services[account]


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
    """Transpile on the best pair and submit. `backend` is "open" / "open:<name>" (real IBM) or "fake:<Name>" (local, no QPU time).

    Writes job_meta.json immediately. For fake backends the job runs locally and its bitstrings are stored in
    `_local_bits.json` so collect_job behaves the same as for a real job.
    """
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2 as Sampler

    run_dir = Path(run_dir)
    if backend == "open" or backend.startswith("open:"):
        service = get_service(account)
        if backend == "open":
            be = service.least_busy(operational=True, simulator=False, min_num_qubits=2)
        else:
            be = service.backend(backend.split(":", 1)[1])
        local = False
    elif backend.startswith("fake:"):
        from qiskit_ibm_runtime import fake_provider
        be = getattr(fake_provider, backend.split(":", 1)[1])()
        local = True
    else:
        raise ValueError("backend must be 'open', 'open:<name>' or 'fake:<Name>'")
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
        job = get_service(account).job(meta["job_id"])
        result = job.result()      # waits if not finished
        bits = {n: pub.data.c.get_bitstrings() for n, pub in zip(meta["circuits"], result)}
    meta["finished"] = now()
    (run_dir / "bitstrings.json").write_text(json.dumps(bits))
    (run_dir / "job_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


# ----------------------------------------------------------------- live mode
def live_spec() -> str:
    """Where live draws run: real IBM ("open") or a local noisy fake for rehearsals ("fake:FakeKingston")."""
    return os.getenv("PROVAFAIR_LIVE_BACKEND", "open")


def _scrub(msg: str) -> str:
    for k in ("API_KEY", "IBM_TOKEN", "QISKIT_IBM_TOKEN"):
        v = os.getenv(k)
        if v:
            msg = msg.replace(v, "***")
    return msg[:200]


def live_probe(account: str = "open") -> dict:
    """Read-only check (no QPU time): which backend is least busy and how many jobs are queued on it."""
    spec = live_spec()
    if spec.startswith("fake:"):
        return {"ok": True, "spec": spec, "backend": spec.split(":", 1)[1], "pending": 0, "simulated": True}
    service = get_service(account)
    if account not in _backends:                      # device list is stable, only queue length changes
        _backends[account] = [b for b in service.backends(operational=True, simulator=False) if b.num_qubits >= 2]
    live = []
    for b in _backends[account]:
        st = b.status()
        if st.operational:
            live.append((st.pending_jobs, b))
    if not live:
        raise RuntimeError("no operational backend")
    pending, be = min(live, key=lambda x: x[0])
    return {"ok": True, "spec": f"open:{be.name}", "backend": be.name, "pending": pending, "simulated": False}


def live_probe_safe(timeout: float = 10.0, account: str = "open") -> dict:
    """live_probe that never raises or hangs: returns {"ok": False, "error": ...} when IBM is unreachable."""
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(live_probe, account).result(timeout=timeout)
    except FutureTimeout:
        return {"ok": False, "error": f"no answer from IBM within {timeout:g}s"}
    except Exception as e:
        return {"ok": False, "error": _scrub(f"{type(e).__name__}: {e}")}
    finally:
        ex.shutdown(wait=False)


def wait_for_job(run_dir, queue_timeout: float, run_timeout: float = 120.0, poll: float = 1.0,
                 account: str = "open") -> str:
    """Wait for a submitted job. Returns "done", "timeout" (still queued; the job is cancelled so it costs nothing)
    or "error:<status>". Once the job is running we let it finish (it is only seconds and is already billed)."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "job_meta.json").read_text())
    if meta.get("local"):
        return "done"
    job = get_service(account).job(meta["job_id"])
    t0, running_since = time.time(), None
    while True:
        st = str(getattr(job.status(), "name", job.status())).upper()
        if st == "DONE":
            return "done"
        if st in ("ERROR", "CANCELLED"):
            return f"error:{st}"
        if st == "RUNNING":
            running_since = running_since or time.time()
            if time.time() - running_since > run_timeout:
                return "error:RUN_TIMEOUT"
        elif time.time() - t0 > queue_timeout:
            try:
                job.cancel()
            except Exception:
                pass
            return "timeout"
        time.sleep(poll)
