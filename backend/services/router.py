"""FastAPI routes for the four services. Mounted by main.py under /v3."""
import os
from typing import Any, Literal, Optional

import threading

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from core import pipeline, store
from ledger.audit_db import get_idempotency_record, save_idempotency_record
from security import verify_api_key_v3
from services import REGISTRY

router = APIRouter(prefix="/v3", tags=["services"], dependencies=[Depends(verify_api_key_v3)])
_idem_lock = threading.Lock()

DEFAULT_MODE = os.getenv("PROVAFAIR_MODE", "sim")


class DrawBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    mode: Optional[Literal["sim", "control", "classical", "replay"]] = None
    scenario: str = "default"
    shots: int = Field(1024, ge=64, le=8192)
    source_run: Optional[str] = None
    backend: str = "aer"


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except pipeline.PipelineError as e:
        raise HTTPException(e.status, str(e))
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, f"not found: {e}")


@router.get("/mode")
def mode():
    return {"default": DEFAULT_MODE if DEFAULT_MODE in pipeline.MODES else "sim", "modes": list(pipeline.MODES),
            "descriptions": {
                "sim": "Fresh Aer simulator run (labelled SIMULATOR)",
                "control": "Simulator with no entanglement: the rigged-device control, must be blocked",
                "classical": "Seeded classical generator (labelled CLASSICAL), must be blocked",
                "replay": "Re-run the service on a recorded run's bits (labelled as recorded/replayed, never live)"}}


@router.get("/services")
def services():
    return {k: {"label": m.LABEL, "defaults": m.DEFAULTS, "limits": m.LIMITS} for k, m in REGISTRY.items()}


@router.post("/{service}/draw")
def draw(service: str, body: DrawBody, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    """Run a draw. With an Idempotency-Key header a repeated request returns the first result and runs only once.
    Demo keys are returned only on the first call and are never cached or stored."""
    mode_ = body.mode or (DEFAULT_MODE if DEFAULT_MODE in pipeline.MODES else "sim")
    backend = body.backend if body.backend == "aer" or body.backend.startswith("fake:") else "aer"

    def go():
        return _guard(pipeline.draw, service, body.params, mode_, body.scenario, body.shots, body.source_run, backend)

    if not idempotency_key:
        return go()
    ikey = f"v3:{service}:{idempotency_key}"
    with _idem_lock:
        cached = get_idempotency_record(ikey)
        if cached:
            return {**cached, "idempotent_replay": True}
        out = go()
        save_idempotency_record(ikey, out["receipt"]["run_id"], {k: v for k, v in out.items() if k != "demo_keys"})
        return out


@router.get("/{service}/runs")
def runs(service: str, limit: int = 50):
    if service not in REGISTRY:
        raise HTTPException(404, "unknown service")
    return {"runs": store.list_runs(service)[:limit]}


@router.get("/{service}/runs/{run_id}")
def run(service: str, run_id: str):
    return _guard(pipeline.get_run, service, run_id)


@router.post("/verify/{service}/{run_id}")
def verify(service: str, run_id: str):
    return _guard(pipeline.verify_run, service, run_id)
