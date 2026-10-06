from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

# Import our custom engines and database
from quantum.chsh_engine import run_chsh_test, extract_quantum_random_numbers
from quantum.rigged_engine import run_rigged_test, generate_rigged_numbers
from ledger.audit_db import init_db, record_draw, get_draw

app = FastAPI(title="ProvaFair API", description="Quantum-secured lottery backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# --- NEW: Create a strict blueprint for our POST requests ---
class DrawRequest(BaseModel):
    num_winners: int = 4
    pool_size: int = 100

@app.post("/draw/quantum")
def api_run_quantum_draw(request: DrawRequest):
    """
    Endpoint 1: Runs the true quantum draw. 
    Verifies physics, draws numbers, and saves to the tamper-proof ledger.
    """
    draw_id = f"DRAW-Q-{uuid.uuid4().hex[:8].upper()}"
    
    cert = run_chsh_test()
    chsh_score = cert["s_score"]
    
    if cert["is_quantum"]:
        status = "VERIFIED - TRUE QUANTUM"
        # Use the values from the JSON body request
        winners = extract_quantum_random_numbers(request.num_winners, request.pool_size)
    else:
        status = "FAILED - SCORE TOO LOW"
        winners = []
        
    receipt_hash = record_draw(draw_id, "Quantum Secure Draw", chsh_score, status, winners)
    
    return {
        "draw_id": draw_id,
        "status": status,
        "chsh_score": chsh_score,
        "is_quantum": cert["is_quantum"],
        "correlations": cert["correlations"],
        "winners": winners,
        "receipt_hash": receipt_hash
    }

@app.post("/draw/rigged")
def api_run_rigged_draw(request: DrawRequest):
    """
    Endpoint 2: Simulates the "Fraud Machine".
    Fails the physics test and outputs deterministic numbers.
    """
    draw_id = f"DRAW-R-{uuid.uuid4().hex[:8].upper()}"
    
    cert = run_rigged_test()
    chsh_score = cert["s_score"]
    
    # Use the values from the JSON body request
    winners = generate_rigged_numbers(request.num_winners, request.pool_size)
    
    status = "REJECTED - CLASSICAL DEVICE DETECTED"
    receipt_hash = record_draw(draw_id, "Rigged Demo Draw", chsh_score, status, winners)
    
    return {
        "draw_id": draw_id,
        "status": status,
        "chsh_score": chsh_score,
        "is_quantum": cert["is_quantum"],
        "correlations": cert["correlations"],
        "winners": winners,
        "receipt_hash": receipt_hash,
        "warning": cert["warning"]
    }

@app.get("/verify/{draw_id}")
def api_verify_draw(draw_id: str):
    """
    Endpoint 3: Public audit API. 
    """
    record = get_draw(draw_id)
    if not record:
        raise HTTPException(status_code=404, detail="Draw ID not found in the public ledger.")
        
    return record