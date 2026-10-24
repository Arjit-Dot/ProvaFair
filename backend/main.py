from fastapi import FastAPI, HTTPException, Security, Depends, Header, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict
import os
import sys
from pathlib import Path
import uuid
import requests
import threading

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import our custom engines and database
from ledger.audit_db import (
    init_db,
    record_draw,
    get_draw,
    get_idempotency_record,
    save_idempotency_record,
    log_api_request,
    count_recent_requests,
    get_ledger_merkle_root,
    get_ledger_draw_count,
    calculate_merkle_root,
)
import api_v2
import config  # noqa: F401  (loads .env before anything reads PROVAFAIR_API_KEY)
from core import pipeline
from security import PROVA_API_KEY, verify_api_key  # noqa: F401  (PROVA_API_KEY re-exported)
from services import router as services_router

app = FastAPI(title="ProvaFair API", description="Quantum-secured lottery backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v2.router)
app.include_router(services_router.router)

# API key auth + rate limiting live in security.py (key comes from PROVAFAIR_API_KEY in .env)


@app.on_event("startup")
def startup_event():
    init_db()
    if os.getenv("PROVAFAIR_MODE") in ("live", "retrieve") and os.getenv("PROVAFAIR_LIVE_BACKEND", "open") == "open":
        # warm the IBM connection in the background so the first live draw is not slowed by the ~10 s cold start
        threading.Thread(target=lambda: __import__("core.hardware", fromlist=["x"]).live_probe_safe(60), daemon=True).start()


# --- Multi-Service Request & Response Models ---
class MultiServiceRequest(BaseModel):
    service_type: str = "lottery"
    service_params: Dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = None


class MultiServiceResponse(BaseModel):
    draw_id: str
    service_type: str
    status: str
    chsh_score: float
    payload: Any
    receipt_hash: str
    previous_hash: str
    ibm_job_id: str = "SIMULATED"


SERVICE_ALIASES = {"quantum_lottery": "lottery", "validator": "web3", "blockchain": "web3"}


def _legacy_params(service: str, params: dict) -> dict:
    """The old API sent {"num_winners": n}. For the lottery that now means n winners among tickets."""
    params = dict(params or {})
    n = params.pop("num_winners", None)
    if n is not None and service == "lottery" and "game" not in params:
        n = int(n)
        params.update(game="tickets", n_tickets=max(10_000, 2 * n), tiers=[{"name": "Prize", "winners": n}])
    elif n is not None and service == "web3" and "seats" not in params:
        params["seats"] = int(n)
    return params


def _to_response(out: dict) -> tuple[str, str, float, str, Any, str]:
    rc = out["receipt"]
    return rc["run_id"], rc["status"], rc["S"], rc["job_id"], out["result"], rc["service"]


def _persist(out: dict, event_name: str, idempotency_key: str | None, webhook_url: str | None) -> MultiServiceResponse:
    """Record the finished draw in the audit ledger, cache the idempotent response, deliver the webhook."""
    run_id, status_str, s_score, job_id, result, service = _to_response(out)
    receipt_hash = record_draw(draw_id=run_id, event_name=event_name, chsh_score=s_score, status=status_str,
                               winners=result, service_type=service, ibm_job_id=job_id)
    saved = get_draw(run_id)
    response = MultiServiceResponse(
        draw_id=run_id, service_type=service, status=status_str, chsh_score=s_score, payload=result,
        receipt_hash=receipt_hash, previous_hash=saved["previous_hash"] if saved else "GENESIS", ibm_job_id=job_id)
    if idempotency_key:
        save_idempotency_record(idempotency_key, run_id, response.model_dump())
    if webhook_url:
        try:
            requests.post(webhook_url, json=response.model_dump(), timeout=10)
        except Exception:
            pass
    return response


def _background_draw(service, run_id, mode, event_name, idempotency_key, webhook_url):
    out = pipeline.complete_draw(service, run_id, mode)
    _persist(out, event_name, idempotency_key, webhook_url)


_draw_lock = threading.Lock()


def _run(request: MultiServiceRequest, background_tasks: BackgroundTasks, idempotency_key: str | None,
         mode: str, event_name: str):
    service = SERVICE_ALIASES.get(request.service_type, request.service_type)
    if service not in pipeline.REGISTRY:
        raise HTTPException(422, f"unknown service_type {request.service_type!r}; use one of {list(pipeline.REGISTRY)}")

    def go():
        try:
            run_id = pipeline.start_draw(service, _legacy_params(service, request.service_params), mode)
        except pipeline.PipelineError as e:
            raise HTTPException(e.status, str(e))
        if request.webhook_url:
            background_tasks.add_task(_background_draw, service, run_id, mode, event_name, idempotency_key,
                                      request.webhook_url)
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"draw_id": run_id, "status": "QUEUED"})
        out = pipeline.complete_draw(service, run_id, mode)
        resp = _persist(out, event_name, idempotency_key, None)
        return resp

    if idempotency_key:
        with _draw_lock:                       # check-then-run must be atomic so duplicates run only once
            cached = get_idempotency_record(idempotency_key)
            if cached:
                return MultiServiceResponse(**cached)
            return go()
    return go()


@app.post("/draw/quantum", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_quantum_draw(
    request: MultiServiceRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Runs the real pipeline in sim mode: Aer CHSH circuits, certification, then the requested service.
    The response carries the real CHSH score and the real job id (SIM-... on the simulator).
    Keys are never returned here (responses are cached); use POST /v3/keys/draw for demo keys."""
    return _run(request, background_tasks, idempotency_key, "sim", "Quantum Secure Draw")


@app.post("/draw/rigged", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_rigged_draw(
    request: MultiServiceRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """The fraud-machine demo: a classical device runs the same pipeline. It fails the CHSH rule and is BLOCKED."""
    return _run(request, background_tasks, idempotency_key, "classical", "Rigged Demo Draw")


@app.get("/verify/{draw_id}")
def api_verify_draw(draw_id: str):
    """
    Endpoint 3: Public audit API. 
    """
    record = get_draw(draw_id)
    if not record:
        raise HTTPException(status_code=404, detail="Draw ID not found in the public ledger.")
        
    return record


@app.get("/ledger/root")
def api_get_ledger_root():
    """
    Public audit endpoint returning the cryptographic Merkle root of the entire ledger.
    """
    merkle_root = get_ledger_merkle_root()
    draw_count = get_ledger_draw_count()
    return {
        "merkle_root": merkle_root,
        "draw_count": draw_count,
    }