"""The shared pipeline every service uses: commit -> run/submit -> certify -> seed -> service -> receipt -> verify."""
import os
import secrets
import shutil
import threading
from datetime import datetime, timezone

from core import chsh, hardware, store
from core.seed import canonical, derive_seed, params_hash, sha256_hex
from ledger import chain_ledger as ledger
from services import REGISTRY

MODES = ("sim", "control", "classical", "replay", "live", "retrieve")

# live mode: try real hardware, fall back to a saved hardware run (never silently, never labelled live)
_live_lock = threading.Lock()
_live_used = 0


def live_config() -> dict:
    return {"max_pending": int(os.getenv("LIVE_MAX_PENDING", "0")),
            "queue_timeout": float(os.getenv("LIVE_QUEUE_TIMEOUT", "30")),
            "probe_timeout": float(os.getenv("LIVE_PROBE_TIMEOUT", "15")),
            "max_jobs": int(os.getenv("LIVE_MAX_JOBS", "25")), "used": _live_used}


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
    la = meta.get("live_attempt") or {}
    when = (meta.get("finished") or meta.get("submitted") or "")[:10]
    if src == "hardware":
        text = "HARDWARE (recorded)" if meta.get("entangled", True) else "HARDWARE (recorded, control: no entanglement)"
    elif src == "classical":
        text = "CLASSICAL"
    elif src == "control-sim":
        text = "SIMULATOR (control, no entanglement)"
    else:
        text = "SIMULATOR (replayed)" if replay else "SIMULATOR"
    note = None
    ra = meta.get("retrieve_attempt") or {}
    if ra.get("outcome") == "ibm":
        text = "HARDWARE (recorded, retrieved from IBM)" if src == "hardware" else text
        note = None
    elif ra.get("outcome") == "local":
        note = f"Could not retrieve from IBM: {ra.get('reason')}. Using the saved local copy of the same job."
    if la.get("outcome") == "live":
        text = "HARDWARE (live)" if src == "hardware" else "SIMULATOR (live, fake backend)"
    elif la.get("outcome") == "fallback":
        note = f"Live hardware unavailable: {la.get('reason')}. Showing saved run {meta.get('replay_of')}."
    return {"live": la.get("outcome"), "note": note, "text": text, "tone": "hardware" if src == "hardware" else "classical" if src == "classical" else "sim",
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


def _latest_source(service: str, hardware_only: bool = False) -> str:
    kinds = ("hardware",) if hardware_only else ("hardware", "sim")
    for r in store.list_runs(service):
        if r["certified"] and r["source"] in kinds and not r["replay_of"]:
            return r["run_id"]
    what = "hardware " if hardware_only else ""
    raise PipelineError(f"no recorded certified {what}{service} run to replay. "
                        + ("Record one with scripts/submit.py first." if hardware_only
                           else "Run in sim mode (or record hardware) first."), 404)


def _replay_into(service: str, d, src_id: str) -> dict:
    """Copy a recorded certified run's bits into run dir d. The run keeps pointing at the original."""
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
    meta.pop("live_attempt", None)
    store.write_json(d, "job_meta.json", meta)
    store.write_json(d, "bitstrings.json", bits)
    return meta


def _retrieve_into(service: str, d, source_run: str | None) -> dict:
    """Submit-ahead / retrieve-at-demo: fetch a finished hardware job's bits from IBM by its saved job ID,
    cross-check them against the local copy, then run the rest of the pipeline on them.

    If IBM cannot be reached we use the local copy of the same job and say so. If IBM and the local copy
    disagree we refuse: one of them has been altered."""
    src_id = source_run or _latest_source(service, hardware_only=True)
    try:
        sd = store.run_dir(service, src_id)
        meta = store.read_json(sd, "job_meta.json")
        cert = store.read_json(sd, "certificate.json")
    except (FileNotFoundError, ValueError):
        raise PipelineError(f"source run {src_id!r} not found", 404)
    if meta.get("source") != "hardware" or meta.get("local"):
        raise PipelineError("retrieve works only for runs recorded from real IBM hardware", 400)
    if not cert["certified"]:
        raise PipelineError("cannot reuse a blocked run", 400)
    local = store.read_json(sd, "bitstrings.json") if store.exists(sd, "bitstrings.json") else None
    got = hardware.fetch_job_bits_safe(meta["job_id"], meta.get("circuits"), live_config()["probe_timeout"] * 2)
    if got["ok"]:
        if local is not None and got["bits"] != local:
            raise PipelineError(f"bits retrieved from IBM for job {meta['job_id']} do not match the saved copy "
                                f"in {src_id}: one of them has been altered. Refusing to use either.", 409)
        bits = got["bits"]
        att = {"outcome": "ibm", "reason": None, "fetched_at": _now(), "matches_local": None if local is None else True}
    elif local is not None:
        bits = local
        att = {"outcome": "local", "reason": got["error"], "fetched_at": None, "matches_local": None}
    else:
        raise PipelineError(f"cannot retrieve job {meta['job_id']} from IBM ({got['error']}) and there is no local copy", 503)
    out = {**meta, "replay_of": meta.get("replay_of") or src_id, "retrieve_attempt": att}
    out.pop("live_attempt", None)
    store.write_json(d, "job_meta.json", out)
    store.write_json(d, "bitstrings.json", bits)
    return out


def _try_live(service: str, d, shots: int) -> tuple[dict | None, dict]:
    """Attempt a live run. Returns (meta, attempt). meta is None when we must fall back, with attempt['reason']."""
    global _live_used
    cfg = live_config()
    att = {"outcome": "fallback", "reason": None, "pending": None, "backend": None}
    if _live_used >= cfg["max_jobs"]:
        att["reason"] = f"live job cap reached ({cfg['max_jobs']}), protecting the QPU allowance"
        return None, att
    if not _live_lock.acquire(blocking=False):
        att["reason"] = "another live run is in progress"
        return None, att
    try:
        probe = hardware.live_probe_safe(cfg["probe_timeout"])
        if not probe["ok"]:
            att["reason"] = f"cannot reach IBM ({probe['error']})"
            return None, att
        att.update(pending=probe["pending"], backend=probe["backend"])
        if probe["pending"] > cfg["max_pending"]:
            att["reason"] = f"{probe['pending']} jobs queued on {probe['backend']} (limit {cfg['max_pending']})"
            return None, att
        try:
            _live_used += 1
            hardware.submit_job(d, shots, True, probe["spec"])
            res = hardware.wait_for_job(d, cfg["queue_timeout"])
            if res == "done":
                meta = hardware.collect_job(d)
                meta["live_attempt"] = {**att, "outcome": "live", "reason": None}
                store.write_json(d, "job_meta.json", meta)
                return meta, meta["live_attempt"]
            att["reason"] = (f"job still queued after {cfg['queue_timeout']:g}s, cancelled" if res == "timeout"
                             else f"hardware job ended with {res}")
        except Exception as e:
            att["reason"] = f"live submission failed ({hardware._scrub(f'{type(e).__name__}: {e}')})"
        return None, att
    finally:
        _live_lock.release()


def acquire_bits(service: str, run_id: str, mode: str, shots: int, source_run: str | None, backend: str):
    """Produce bitstrings.json + job_meta.json for a run (simulator, control, classical, replay or live)."""
    d = store.run_dir(service, run_id)
    if mode == "replay":
        return _replay_into(service, d, source_run or _latest_source(service))
    if mode == "retrieve":
        return _retrieve_into(service, d, source_run)
    if mode == "live":
        meta, att = _try_live(service, d, shots)
        if meta is not None:
            return meta
        for stale in ("_local_bits.json", "bitstrings.json"):
            (d / stale).unlink(missing_ok=True)
        try:
            src_id = _latest_source(service, hardware_only=True)
        except PipelineError as e:
            raise PipelineError(f"live hardware unavailable ({att['reason']}) and no recorded hardware run to fall "
                                f"back to for {service}", 503) from e
        meta = _replay_into(service, d, src_id)
        meta["live_attempt"] = att
        store.write_json(d, "job_meta.json", meta)
        return meta
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
               "job_id": meta.get("job_id"), "replay_of": meta.get("replay_of"), "live_attempt": meta.get("live_attempt"), "retrieve_attempt": meta.get("retrieve_attempt"), "params_hash": ph,
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
    return commit_run(service, params, scenario, source={"control": "control-sim", "live": "hardware", "retrieve": "hardware"}.get(mode, mode))[0]


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
        ok3 = sha256_hex(seed) == receipt["seed_hash"] == (entry["winners"][1] if entry and len(entry["winners"]) == 3 else None)
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

    # 5. ledger entries: this run's COMMIT..result segment of the hash chain must be intact.
    #    An unrelated break elsewhere in a shared ledger is reported but does not invalidate this run.
    chain = ledger.verify_chain()
    order = [e["draw_id"] for e in chain["entries"]]
    seg_ok, seg_detail = False, "no ledger entry"
    if entry and commit and commit["draw_id"] in order and run_id in order:
        i, j = order.index(commit["draw_id"]), order.index(run_id)
        seg = chain["entries"][i:j + 1]
        seg_ok = i < j and all(e["hash_ok"] and e["link_ok"] for e in seg)
        seg_detail = (f"{len(seg)} chained entries from the commitment to the result are intact" if seg_ok
                      else "an entry between the commitment and the result is altered or out of order")
    ok5 = bool(seg_ok and stored and len(entry["winners"]) == 3 and entry["winners"][2] == sha256_hex(stored) == receipt["result_hash"]
               and entry["hash"] == receipt["ledger_hash"])
    d5 = seg_detail if (seg_ok and ok5) else (seg_detail if not seg_ok else "ledger entry does not match the files")
    if not chain["intact"] and ok5:
        d5 += f" (note: the shared ledger has an unrelated break at {chain['first_break_draw_id']})"
    add(5, "Ledger entry and hash chain", ok5, d5)
    return {"run_id": run_id, "service": service, "all_ok": all(c["ok"] for c in checks), "checks": checks,
            "badge": receipt["badge"] if receipt else None}
