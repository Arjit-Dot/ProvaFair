"""ProvaFair evidence API. Mount with:  app.include_router(api_v2.router)"""
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import usecases
from ledger import chain_ledger as ledger
from quantum import chsh_analysis as ch
from quantum import randomness_tests as rt
from quantum.entropy import ClassicalServer, bits_to_winners
from validation import run_validation

router = APIRouter(prefix="/v2", tags=["evidence"])
ledger.init_chain()

SEED = 1337
RIGGED_BIAS = 0.56                       # the rigged server is slightly biased on purpose
_rigged = ClassicalServer(SEED, RIGGED_BIAS)


class DrawRequest(BaseModel):
    mode: Literal["quantum", "classical"] = "quantum"
    use_case: Literal["ipo", "lottery", "validator"] = "lottery"
    pool_size: int = Field(100, ge=1, le=1_000_000)
    num_winners: int = Field(4, ge=1, le=50)
    event_name: Optional[str] = None
    record: bool = True                  # False = dry run, nothing written to the ledger


def execute_draw(req: DrawRequest) -> dict:
    if req.mode == "quantum":
        chsh, bits = ch.run_quantum_chsh()
    else:
        chsh, bits = ch.run_classical_chsh(_rigged.np_rng())
        bits = _rigged.bits(len(bits))   # rigged output comes from the seeded PRNG
    certified = chsh["certified"]
    winners_idx = winners = None
    if certified:                        # numbers are released ONLY after the physics check passes
        try:
            winners_idx = bits_to_winners(bits, req.pool_size, req.num_winners)
        except ValueError as e:
            raise HTTPException(400, str(e))
        winners = usecases.labels(req.use_case, winners_idx)
    draw_id = f"DRAW-{'Q' if req.mode == 'quantum' else 'C'}-{uuid.uuid4().hex[:8].upper()}"
    status = "CERTIFIED" if certified else "BLOCKED"
    event = req.event_name or f"{usecases.USE_CASES[req.use_case]['label']} draw"
    rec = None
    if req.record:
        rec = ledger.append(draw_id, req.mode, event, chsh["S"], chsh["sigma"],
                            chsh["total_shots"], status, winners)
    return {
        "draw_id": draw_id, "mode": req.mode, "status": status, "certified": certified,
        "use_case": req.use_case, "event_name": event, "pool_size": req.pool_size,
        "winners": winners, "winner_indices": winners_idx, "chsh": chsh,
        "randomness": rt.run_all(bits), "bits_preview": "".join(map(str, bits[:96].tolist())),
        "timestamp": rec["timestamp"] if rec else None,
        "hash": rec["hash"] if rec else None, "prev_hash": rec["prev_hash"] if rec else None,
    }


@router.get("/usecases")
def get_usecases():
    return usecases.USE_CASES


@router.get("/circuit")
def get_circuit():
    return ch.circuit_info()


@router.post("/draw")
def draw(req: DrawRequest):
    return execute_draw(req)


@router.get("/draw/{draw_id}")
def verify(draw_id: str):
    rec = ledger.get(draw_id)
    if not rec:
        raise HTTPException(404, "Draw not found")
    chain = ledger.verify_chain()
    me = next(e for e in chain["entries"] if e["draw_id"] == draw_id)
    full = ledger.compute_hash({**rec, "winners": __import__("json").dumps(rec["winners"])})
    sigma_total = rec["sigma"]
    lower = rec["chsh_score"] - ch.SIGMA_K * sigma_total
    return {**rec, "lower_bound": round(lower, 4), "margin": round(ch.SIGMA_K * sigma_total, 4),
            "recomputed_hash": full, "hash_ok": me["hash_ok"], "link_ok": me["link_ok"],
            "chain_intact": chain["intact"], "chain_first_break": chain["first_break_draw_id"],
            "rule_recheck": "PASS" if lower > ch.CLASSICAL_LIMIT else "FAIL"}


@router.get("/ledger")
def get_ledger(limit: int = 50):
    return {"entries": ledger.all_entries(limit)}


@router.post("/ledger/verify")
def verify_all():
    return ledger.verify_chain()


@router.post("/ledger/tamper/{draw_id}")
def tamper(draw_id: str):
    if not ledger.tamper(draw_id):
        raise HTTPException(404, "Draw not found")
    return {"ok": True}


@router.post("/ledger/restore")
def restore():
    return {"restored": ledger.restore_all()}


@router.get("/validation")
def validation(runs: int = 500, refresh: bool = False):
    return run_validation(min(max(runs, 50), 2000), refresh=refresh)


@router.post("/insider-attack")
def insider_attack(rounds: int = 5, pool_size: int = 100, num_winners: int = 4):
    """Attacker knows the seed. Predicts a seeded server, then tries the same on certified quantum draws."""
    victim = ClassicalServer(SEED)           # honest-looking PRNG lottery
    attacker = ClassicalServer(SEED)         # attacker replays it from the stolen seed
    classical, quantum = [], []
    for r in range(1, rounds + 1):
        actual = bits_to_winners(victim.bits(4096), pool_size, num_winners)
        pred = bits_to_winners(attacker.bits(4096), pool_size, num_winners)
        classical.append({"round": r, "actual": actual, "predicted": pred, "match": actual == pred})
    attacker = ClassicalServer(SEED)         # same attack against certified quantum draws
    for r in range(1, rounds + 1):
        chsh, bits = ch.run_quantum_chsh()
        actual = bits_to_winners(bits, pool_size, num_winners)
        pred = bits_to_winners(attacker.bits(4096), pool_size, num_winners)
        quantum.append({"round": r, "actual": actual, "predicted": pred, "match": actual == pred,
                        "S": chsh["S"], "certified": chsh["certified"]})
    return {"seed": SEED, "classical": classical, "quantum": quantum,
            "classical_hits": sum(x["match"] for x in classical),
            "quantum_hits": sum(x["match"] for x in quantum)}
