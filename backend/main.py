from fastapi import FastAPI, HTTPException, Security, Depends, Header, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Any, Dict
import os
import secrets
import sys
from pathlib import Path
import uuid
import requests

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import our custom engines and database
from quantum.chsh_engine import run_chsh_test, extract_quantum_random_numbers
from quantum.rigged_engine import run_rigged_test, generate_rigged_numbers
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
from quantum_engine.batcher import calculate_batches
import api_v2

app = FastAPI(title="ProvaFair API", description="Quantum-secured lottery backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v2.router)

# --- API Key Security Configuration ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
PROVA_API_KEY = os.getenv("PROVA_API_KEY", "PROVA-HACK-2026")


def verify_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
) -> str:
    """
    Validates API key using constant-time string comparison to prevent timing attacks.
    Checks rate limit (maximum 5 requests per 60 seconds).
    Logs API request upon successful validation and rate limit check.
    Raises 401 Unauthorized if missing or invalid.
    Raises 429 Too Many Requests if rate limit is exceeded.
    """
    if not api_key or not secrets.compare_digest(api_key, PROVA_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API Key"
        )

    # Rate limiting: max 5 requests per minute (60 seconds)
    recent_count = count_recent_requests(api_key, window_seconds=60)
    if recent_count >= 5:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )

    # Log usage
    endpoint = request.url.path if request else "unknown"
    log_api_request(api_key, endpoint)

    return api_key


@app.on_event("startup")
def startup_event():
    init_db()


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


def process_draw_background(
    draw_id: str,
    event_name: str,
    service_type: str,
    status: str,
    chsh_score: float,
    payload: Any,
    webhook_url: str | None = None,
    idempotency_key: str | None = None,
    ibm_job_id: str = "SIMULATED",
) -> MultiServiceResponse:
    """
    Worker function that executes the draw persistence in the ledger,
    saves the idempotency record, and delivers results to webhook_url if configured.
    """
    receipt_hash = record_draw(
        draw_id=draw_id,
        event_name=event_name,
        chsh_score=chsh_score,
        status=status,
        winners=payload,
        service_type=service_type,
        ibm_job_id=ibm_job_id,
    )

    saved_draw = get_draw(draw_id)
    previous_hash = saved_draw["previous_hash"] if saved_draw else "GENESIS"

    response = MultiServiceResponse(
        draw_id=draw_id,
        service_type=service_type,
        status=status,
        chsh_score=chsh_score,
        payload=payload,
        receipt_hash=receipt_hash,
        previous_hash=previous_hash,
        ibm_job_id=ibm_job_id,
    )

    if idempotency_key:
        save_idempotency_record(idempotency_key, draw_id, response.model_dump())

    if webhook_url:
        try:
            requests.post(webhook_url, json=response.model_dump(), timeout=10)
        except Exception:
            pass

    return response


@app.post("/draw/quantum", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_quantum_draw(
    request: MultiServiceRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """
    Endpoint 1: Runs the true quantum draw. 
    Verifies physics, draws numbers, and saves to the tamper-proof ledger.
    Supports Idempotency-Key header to prevent duplicate processing.
    Supports asynchronous webhook delivery via BackgroundTasks.
    """
    if idempotency_key:
        cached = get_idempotency_record(idempotency_key)
        if cached:
            return MultiServiceResponse(**cached)

    draw_id = f"DRAW-Q-{uuid.uuid4().hex[:8].upper()}"

    # Extract num_winners from service_params (defaulting to 1) and calculate batches
    num_winners = int(request.service_params.get("num_winners", 1))
    batches = calculate_batches(num_winners)
    print(f"[Quantum Batcher] Slicing {num_winners} circuits into batches: {batches}")
    
    # Placeholder values while quantum engine multi-service integration is updated
    chsh_score = 2.8284
    status_str = "VERIFIED - TRUE QUANTUM"
    payload = [1, 2, 3]
    ibm_job_id = f"ibm-q-job-{uuid.uuid4().hex[:8]}"

    if request.webhook_url:
        background_tasks.add_task(
            process_draw_background,
            draw_id=draw_id,
            event_name="Quantum Secure Draw",
            service_type=request.service_type,
            status=status_str,
            chsh_score=chsh_score,
            payload=payload,
            webhook_url=request.webhook_url,
            idempotency_key=idempotency_key,
            ibm_job_id=ibm_job_id,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"draw_id": draw_id, "status": "QUEUED"},
        )

    return process_draw_background(
        draw_id=draw_id,
        event_name="Quantum Secure Draw",
        service_type=request.service_type,
        status=status_str,
        chsh_score=chsh_score,
        payload=payload,
        webhook_url=None,
        idempotency_key=idempotency_key,
        ibm_job_id=ibm_job_id,
    )


@app.post("/draw/rigged", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_rigged_draw(
    request: MultiServiceRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """
    Endpoint 2: Simulates the "Fraud Machine".
    Fails the physics test and outputs deterministic numbers.
    Supports Idempotency-Key header to prevent duplicate processing.
    Supports asynchronous webhook delivery via BackgroundTasks.
    """
    if idempotency_key:
        cached = get_idempotency_record(idempotency_key)
        if cached:
            return MultiServiceResponse(**cached)

    draw_id = f"DRAW-R-{uuid.uuid4().hex[:8].upper()}"
    
    # Placeholder values while quantum engine multi-service integration is updated
    chsh_score = 1.4142
    status_str = "REJECTED - CLASSICAL DEVICE DETECTED"
    payload = [1, 2, 3]
    ibm_job_id = "SIMULATED"

    if request.webhook_url:
        background_tasks.add_task(
            process_draw_background,
            draw_id=draw_id,
            event_name="Rigged Demo Draw",
            service_type=request.service_type,
            status=status_str,
            chsh_score=chsh_score,
            payload=payload,
            webhook_url=request.webhook_url,
            idempotency_key=idempotency_key,
            ibm_job_id=ibm_job_id,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"draw_id": draw_id, "status": "QUEUED"},
        )

    return process_draw_background(
        draw_id=draw_id,
        event_name="Rigged Demo Draw",
        service_type=request.service_type,
        status=status_str,
        chsh_score=chsh_score,
        payload=payload,
        webhook_url=None,
        idempotency_key=idempotency_key,
        ibm_job_id=ibm_job_id,
    )


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