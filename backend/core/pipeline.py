"""The shared pipeline every service uses: commit -> run/submit -> certify -> seed -> service -> receipt -> verify."""
import secrets
import shutil
from datetime import datetime, timezone

from core import chsh, hardware, store
from core.seed import canonical, derive_seed, params_hash, sha256_hex
from ledger import chain_ledger as ledger
from services import REGISTRY

MODES = ("sim", "control", "classical", "replay")


class PipelineError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


def _svc(service: str):
    if service not in REGISTRY:
        raise PipelineError(f"unknown service {service!r}", 404)
    return REGISTRY[service]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def badge(meta: dict) -> dict:
    """What the UI must show. A replay is never labelled live."""
    src, replay = meta.get("source"), bool(meta.get("replay_of"))
    when = (meta.get("finished") or meta.get("submitted") or "")[:10]
    if src == "hardware":
        text = "HARDWARE (recorded)" if meta.get("entangled", True) else "HARDWARE (recorded, control: no entanglement)"
    elif src == "classical":
        text = "CLASSICAL"
    elif src == "control-sim":
        text = "SIMULATOR (control, no entanglement)"
    else:
        text = "SIMULATOR (replayed)" if replay else "SIMULATOR"
    return {"text": text, "tone": "hardware" if src == "hardware" else "classical" if src == "classical" else "sim",
            "backend": meta.get("backend"), "date": when, "job_id": meta.get("job_id"),
            "replayed": replay, "replay_of": meta.get("replay_of")}


def commit_run(service: str, params: dict, scenario: str = "default", source: str = "sim") -> tuple[str, dict, dict]:
    """Step 1: validate, hash and commit parameters to the ledger BEFORE any bits exist."""
    svc = _svc(service)
    try:
        norm = svc.normalize(params)
    except (ValueError, TypeError, KeyError) as e:
        raise PipelineError(f"invalid parameters: {e}", 422)
    scenario = (scenario or "default").strip()[:64] or "default"
    full = {"service": service, "scenario": scenario, "params": norm}
    ph = params_hash(full)
    run_id = f"{service.upper()}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(2).upper()}"
    d = store.run_dir(service, run_id, create=True)
    store.write_json(d, "params.json", full)
    (d / "params_hash.txt").write_text(ph)
    ledger.init_chain()
    ledger.append(f"{run_id}:COMMIT", source, service, 0.0, 0.0, 0, "COMMITTED", [ph])
    return run_id, full, {"params_hash": ph, "dir": str(d)}


def _latest_source(service: str) -> str:
    for r in store.list_runs(service):
        if r["certified"] and r["source"] in ("hardware", "sim") and not r["replay_of"]:
            return r["run_id"]
    raise PipelineError(f"no recorded certified {service} run to replay. Run in sim mode (or record hardware) first.", 404)


def acquire_bits(service: str, run_id: str, mode: str, shots: int, source_run: str | None, backend: str):
    """Produce bitstrings.json + job_meta.json for a run (simulator, control, classical or replay)."""
    d = store.run_dir(service, run_id)
    if mode == "replay":
        src_id = source_run or _latest_source(service)
        try:
            sd = store.run_dir(service, src_id)
            meta = store.read_json(sd, "job_meta.json")
            bits = store.read_json(sd, "bitstrings.json")
            cert = store.read_json(sd, "certificate.json")
        except (FileNotFoundError, ValueError):
            raise PipelineError(f"source run {src_id!r} not found", 404)
        if not cert["certified"]:
            raise PipelineError("cannot replay a blocked run", 400)
        meta = {**meta, "replay_of": meta.get("replay_of") or src_id}   # always point at the original run
    else:
        if mode == "sim":
            bits, info = hardware.run_sim(shots, True, backend)
            src = "sim"
        elif mode == "control":
            bits, info = hardware.run_sim(shots, False, backend)
            src = "control-sim"
        elif mode == "classical":
            bits, info = hardware.run_classical(shots)
            src = "classical"
        else:
            raise PipelineError(f"mode must be one of {MODES}", 422)
        meta = {**info, "job_id": f"{src.upper()}-{secrets.token_hex(4).upper()}", "source": src,
                "submitted": _now(), "finished": _now(), "circuits": chsh.SETTING_NAMES}
    store.write_json(d, "job_meta.json", meta)
    store.write_json(d, "bitstrings.json", bits)
    return meta


def finalize_run(service: str, run_id: str) -> tuple[dict, object]:
    """Steps 4-7: certify, extract seed, run the service, write receipt + ledger entry."""
    svc = _svc(service)
    d = store.run_dir(service, run_id)
    full = store.read_json(d, "params.json")
    ph = (d / "params_hash.txt").read_text().strip()
    meta = store.read_json(d, "job_meta.json")
    bits = store.read_json(d, "bitstrings.json")
    cert = chsh.chsh_from_bits(bits)
    store.write_json(d, "certificate.json", cert)
    label, secret, seed_hash = full["scenario"], None, None
    if cert["certified"]:                      # fail closed: no seed, no numbers unless the physics check passes
        seed = derive_seed(bits, ph, meta["job_id"], f"provafair/{service}/{label}")
        seed_hash = sha256_hex(seed)
        result, secret = svc.run(full["params"], seed, label)
        stored = {"status": "CERTIFIED", "result": result}
    else:
        stored = {"status": "BLOCKED", "result": None}
    store.write_json(d, "result.json", stored)
    result_hash = sha256_hex(stored)
    total = sum(cert["shots"].values())
    rec = ledger.append(run_id, meta["source"], service, cert["S"], cert["sigma"], total, stored["status"],
                        [ph, seed_hash, result_hash])
    receipt = {"run_id": run_id, "service": service, "scenario": label, "status": stored["status"],
               "certified": cert["certified"], "source": meta["source"], "backend": meta.get("backend"),
               "job_id": meta.get("job_id"), "replay_of": meta.get("replay_of"), "params_hash": ph,
               "S": cert["S"], "sigma": cert["sigma"], "lower_bound": cert["lower_bound"], "seed_hash": seed_hash,
               "result_hash": result_hash, "ledger_hash": rec["hash"], "ledger_prev_hash": rec["prev_hash"],
               "finalized": _now(), "badge": badge(meta), "limits": svc.LIMITS}
    store.write_json(d, "receipt.json", receipt)
    return receipt, secret


def start_draw(service: str, params: dict, mode: str = "sim", scenario: str = "default", shots: int = 1024) -> str:
    """Validate and commit a draw; returns the run id immediately (the heavy part is complete_draw)."""
    if mode not in MODES:
        raise PipelineError(f"mode must be one of {MODES}", 422)
    if not 64 <= shots <= 8192:
        raise PipelineError("shots per setting must be between 64 and 8192", 422)
    return commit_run(service, params, scenario, source={"control": "control-sim"}.get(mode, mode))[0]


def complete_draw(service: str, run_id: str, mode: str = "sim", shots: int = 1024,
                  source_run: str | None = None, backend: str = "aer") -> dict:
    """Get bits (simulator / control / classical / replay), certify, run the service, write the receipt."""
    try:
        acquire_bits(service, run_id, mode, shots, source_run, backend)
    except PipelineError:
        shutil.rmtree(store.run_dir(service, run_id), ignore_errors=True)
        raise
    receipt, secret = finalize_run(service, run_id)
    d = store.run_dir(service, run_id)
    out = {"receipt": receipt, "certificate": store.read_json(d, "certificate.json"),
           "result": store.read_json(d, "result.json")["result"], "params": store.read_json(d, "params.json")}
    if secret is not None:
        out["demo_keys"] = secret       # returned once, never stored
    return out


def draw(service: str, params: dict, mode: str = "sim", scenario: str = "default", shots: int = 1024,
         source_run: str | None = None, backend: str = "aer") -> dict:
    """Full run in one call."""
    run_id = start_draw(service, params, mode, scenario, shots)
    return complete_draw(service, run_id, mode, shots, source_run, backend)


def get_run(service: str, run_id: str) -> dict:
    _svc(service)
    d = store.run_dir(service, run_id)
    if not store.exists(d, "receipt.json"):
        raise PipelineError("run not found", 404)
    return {n: store.read_json(d, f"{n}.json") for n in ("receipt", "params", "certificate", "result", "job_meta")}


# ----------------------------------------------------------------- verify
def verify_run(service: str, run_id: str) -> dict:
    """Recompute everything from saved files. Returns five separately reported checks."""
    svc = _svc(service)
    d = store.run_dir(service, run_id)
    if not store.exists(d, "receipt.json"):
        raise PipelineError("run not found", 404)
    checks = []

    def add(cid, name, ok, detail):
        checks.append({"id": cid, "name": name, "ok": ok, "detail": detail})

    def load(name):
        try:
            return store.read_json(d, name)
        except Exception:
            return None

    full, bits, meta = load("params.json"), load("bitstrings.json"), load("job_meta.json")
    cert, stored, receipt = load("certificate.json"), load("result.json"), load("receipt.json")
    try:
        ph_file = (d / "params_hash.txt").read_text().strip()
    except Exception:
        ph_file = None
    ledger.init_chain()
    entry = ledger.get(run_id)
    commit = ledger.get(f"{run_id}:COMMIT")

    # 1. parameters match what was committed before the bits existed
    ph = params_hash(full) if full else None
    ok1 = bool(ph and ph == ph_file == receipt["params_hash"] and commit and commit["winners"][:1] == [ph])
    add(1, "Parameters match the commitment made before the draw", ok1,
        "params.json re-hashed and compared with params_hash.txt, the receipt and the ledger COMMIT entry")

    # 2. certificate recomputed from per-shot bits
    try:
        re_cert = chsh.chsh_from_bits(bits)
        ok2 = re_cert == cert and (re_cert["certified"] == (receipt["status"] == "CERTIFIED"))
        d2 = f"S = {re_cert['S']:.4f} ± {re_cert['sigma']:.4f}, S − 3σ = {re_cert['lower_bound']:.4f} ({'above' if re_cert['certified'] else 'not above'} 2)"
    except Exception as ex:
        re_cert, ok2, d2 = None, False, f"cannot recompute: {ex}"
    add(2, "CHSH certificate recomputed from per-shot bitstrings", ok2, d2)

    # 3. seed recomputed
    seed = None
    if re_cert and re_cert["certified"] and meta and ph:
        seed = derive_seed(bits, ph, meta["job_id"], f"provafair/{service}/{full['scenario']}")
        ok3 = sha256_hex(seed) == receipt["seed_hash"] == (entry["winners"][1] if entry else None)
        add(3, "Seed recomputed from bits, job ID and parameters", ok3, "SHA3-256 over domain | params hash | job ID | bits")
    elif re_cert and not re_cert["certified"]:
        ok3 = receipt["seed_hash"] is None
        add(3, "Seed recomputed from bits, job ID and parameters", ok3,
            "run was blocked: no seed may exist" if ok3 else "blocked run has a seed")
    else:
        add(3, "Seed recomputed from bits, job ID and parameters", False, "inputs unavailable")

    # 4. service output recomputed
    if seed is not None and stored and stored.get("result") is not None:
        try:
            ok4, d4 = svc.verify(full["params"], seed, full["scenario"], stored["result"])
        except Exception as ex:
            ok4, d4 = False, f"recompute failed: {ex}"
    elif re_cert and not re_cert["certified"]:
        ok4 = bool(stored) and stored.get("result") is None
        d4 = "run was blocked: no output may exist" if ok4 else "blocked run has output"
    else:
        ok4, d4 = False, "inputs unavailable"
    add(4, "Service output recomputed from the seed", ok4, d4)

    # 5. ledger entry and chain
    chain = ledger.verify_chain()
    ok5 = bool(entry and stored and chain["intact"] and entry["winners"][2] == sha256_hex(stored)
               == receipt["result_hash"] and entry["hash"] == receipt["ledger_hash"])
    d5 = ("ledger entry matches the receipt and the whole chain is intact" if ok5 else
          "no ledger entry" if not entry else
          f"chain broken at {chain['first_break_draw_id']}" if not chain["intact"] else "ledger entry does not match the files")
    add(5, "Ledger entry and hash chain", ok5, d5)
    return {"run_id": run_id, "service": service, "all_ok": all(c["ok"] for c in checks), "checks": checks,
            "badge": receipt["badge"] if receipt else None}
