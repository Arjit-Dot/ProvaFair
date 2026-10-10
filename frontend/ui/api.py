import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"


def call(method: str, path: str, timeout: int = 90, **kw):
    """Returns (data, error_message). Never raises."""
    try:
        r = requests.request(method, f"{API_URL}{path}", timeout=timeout, **kw)
    except Exception:
        return None, f"Cannot reach the backend at {API_URL}. Start it with: uvicorn main_example:app --port 8000"
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
