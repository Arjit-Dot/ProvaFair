import os
from pathlib import Path

import requests
import streamlit as st


def _load_env():
    """Read PROVAFAIR_API_KEY from the repo-root .env (real environment variables win)."""
    f = Path(__file__).resolve().parents[2] / ".env"
    if f.is_file():
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip().removeprefix("export ").strip(), v.strip().strip("'\""))


_load_env()
API_KEY = os.getenv("PROVAFAIR_API_KEY") or os.getenv("PROVA_API_KEY") or "PROVA-HACK-2026"

API_URL = "http://127.0.0.1:8000"


def call(method: str, path: str, timeout: int = 90, **kw):
    """Returns (data, error_message). Never raises."""
    try:
        headers = {**kw.pop("headers", {}), "X-API-Key": API_KEY}
        r = requests.request(method, f"{API_URL}{path}", timeout=timeout, headers=headers, **kw)
    except Exception:
        return None, f"Cannot reach the backend at {API_URL}. Start it with: uvicorn main:app --port 8000 (from the backend folder)"
    if r.status_code == 200:
        return r.json(), None
    try:
        detail = r.json().get("detail", r.text)
    except Exception:
        detail = r.text
    return None, f"Backend returned {r.status_code}: {detail}"


@st.cache_data(ttl=300, show_spinner=False)
def cached_get(path: str):
    return call("GET", path)
