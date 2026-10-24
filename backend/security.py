"""API key auth + sliding-window rate limit, shared by the legacy /draw routes and the /v3 service routes."""
import os
import secrets
import threading

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

import config  # noqa: F401  (loads .env)
from ledger.audit_db import count_recent_requests, log_api_request

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
# API_KEY from .env / environment. PROVA_API_KEY and the old demo key remain as fallbacks.
PROVA_API_KEY = os.getenv("API_KEY") or os.getenv("PROVA_API_KEY") or "PROVA-HACK-2026"

_lock = threading.Lock()


def _check(request: Request, api_key: str | None, bucket_suffix: str, limit: int) -> str:
    if not api_key or not secrets.compare_digest(api_key, PROVA_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    bucket = api_key + bucket_suffix        # separate quota per route family
    with _lock:
        if count_recent_requests(bucket, window_seconds=60) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        log_api_request(bucket, request.url.path if request else "unknown")
    return api_key


def verify_api_key(request: Request, api_key: str = Security(api_key_header)) -> str:
    """Legacy /draw routes: 5 requests per 60 seconds (constant-time key comparison)."""
    return _check(request, api_key, "", 5)


def verify_api_key_v3(request: Request, api_key: str = Security(api_key_header)) -> str:
    """/v3 service routes: same key, its own quota (default 120 per 60 seconds, set V3_RATE_LIMIT)."""
    return _check(request, api_key, "|v3", int(os.getenv("V3_RATE_LIMIT", "120")))
