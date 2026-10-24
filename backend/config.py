"""Loads KEY=VALUE pairs from the repo-root .env (and backend/.env) into os.environ without overriding real env vars."""
import os
from pathlib import Path

_loaded = False


def load_env() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    here = Path(__file__).resolve().parent
    for f in (here.parent / ".env", here / ".env"):
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().removeprefix("export ").strip(), v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v


load_env()
