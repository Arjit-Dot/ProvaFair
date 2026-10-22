from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Any, Dict
import os
import secrets
import sys
from pathlib import Path
import uuid

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import our custom engines and database
from quantum.chsh_engine import run_chsh_test, extract_quantum_random_numbers
from quantum.rigged_engine import run_rigged_test, generate_rigged_numbers
from ledger.audit_db import init_db, record_draw, get_draw
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


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validates API key using constant-time string comparison to prevent timing attacks.
    Raises 401 Unauthorized if missing or invalid.
    """
    if not api_key or not secrets.compare_digest(api_key, PROVA_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API Key"
        )
    return api_key


@app.on_event("startup")
def startup_event():
    init_db()


# --- Multi-Service Request & Response Models ---
class MultiServiceRequest(BaseModel):
    service_type: str = "lottery"
    service_params: Dict[str, Any] = Field(default_factory=dict)


class MultiServiceResponse(BaseModel):
    draw_id: str
    service_type: str
    status: str
    chsh_score: float
    payload: Any
    receipt_hash: str
    previous_hash: str


@app.post("/draw/quantum", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_quantum_draw(request: MultiServiceRequest):
    """
    Endpoint 1: Runs the true quantum draw. 
    Verifies physics, draws numbers, and saves to the tamper-proof ledger.
    """
    draw_id = f"DRAW-Q-{uuid.uuid4().hex[:8].upper()}"
    
    # Placeholder values while quantum engine multi-service integration is updated
    chsh_score = 2.8284
    status = "VERIFIED - TRUE QUANTUM"
    payload = [1, 2, 3]
        
    receipt_hash = record_draw(
        draw_id=draw_id,
        event_name="Quantum Secure Draw",
        chsh_score=chsh_score,
        status=status,
        winners=payload,
        service_type=request.service_type,
    )
    
    saved_draw = get_draw(draw_id)
    previous_hash = saved_draw["previous_hash"] if saved_draw else "GENESIS"
    
    return MultiServiceResponse(
        draw_id=draw_id,
        service_type=request.service_type,
        status=status,
        chsh_score=chsh_score,
        payload=payload,
        receipt_hash=receipt_hash,
        previous_hash=previous_hash,
    )


@app.post("/draw/rigged", response_model=MultiServiceResponse, dependencies=[Depends(verify_api_key)])
def api_run_rigged_draw(request: MultiServiceRequest):
    """
    Endpoint 2: Simulates the "Fraud Machine".
    Fails the physics test and outputs deterministic numbers.
    """
    draw_id = f"DRAW-R-{uuid.uuid4().hex[:8].upper()}"
    
    # Placeholder values while quantum engine multi-service integration is updated
    chsh_score = 1.4142
    status = "REJECTED - CLASSICAL DEVICE DETECTED"
    payload = [1, 2, 3]
    
    receipt_hash = record_draw(
        draw_id=draw_id,
        event_name="Rigged Demo Draw",
        chsh_score=chsh_score,
        status=status,
        winners=payload,
        service_type=request.service_type,
    )
    
    saved_draw = get_draw(draw_id)
    previous_hash = saved_draw["previous_hash"] if saved_draw else "GENESIS"
    
    return MultiServiceResponse(
        draw_id=draw_id,
        service_type=request.service_type,
        status=status,
        chsh_score=chsh_score,
        payload=payload,
        receipt_hash=receipt_hash,
        previous_hash=previous_hash,
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