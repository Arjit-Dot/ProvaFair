"""Keys: derive keys/tokens from a certified seed mixed with local OS entropy.

IBM (or any cloud provider) sees the raw hardware bits, so the quantum seed alone is not secret from them.
Each key is HKDF(quantum_seed || os.urandom(32)). Keys are returned once to the caller and never stored.
Recorded seeds are public demo data, so keys made from them are demo keys only.
"""
import base64
import hashlib
import os

from core.stream import hkdf

NAME, LABEL = "keys", "Key and token generation"
LIMITS = ("Demo keys, not for real use: recorded seeds are no longer secret. Does not replace a hardware security "
          "module. Fingerprints include local entropy, so only the quantum component can be re-derived.")
DEFAULTS = {"length_bits": 256, "count": 4, "format": "hex", "purpose": "api-token"}


def normalize(p: dict) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (p or {}).items() if v is not None}}
    try:
        out = {"length_bits": int(p["length_bits"]), "count": int(p["count"]),
               "format": str(p["format"]), "purpose": str(p["purpose"]).strip()}
    except (TypeError, ValueError):
        raise ValueError("length_bits and count must be integers")
    if out["length_bits"] not in (128, 192, 256, 384, 512):
        raise ValueError("length_bits must be one of 128, 192, 256, 384, 512")
    if not 1 <= out["count"] <= 64:
        raise ValueError("count must be between 1 and 64")
    if out["format"] not in ("hex", "base64"):
        raise ValueError("format must be 'hex' or 'base64'")
    if not 1 <= len(out["purpose"]) <= 64:
        raise ValueError("purpose must be 1 to 64 characters")
    return out


def _info(label: str, purpose: str, i: int) -> bytes:
    return f"keys|{label}|{purpose}|{i}".encode()


def _fp(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(p: dict, seed: bytes, label: str):
    local = os.urandom(32)
    n = p["length_bits"] // 8
    keys, fps, qfps = [], [], []
    for i in range(p["count"]):
        info = _info(label, p["purpose"], i)
        k = hkdf(seed + local, info, n)
        keys.append(k.hex() if p["format"] == "hex" else base64.b64encode(k).decode())
        fps.append(_fp(k))
        qfps.append(_fp(hkdf(seed, info, n)))
    result = {"purpose": p["purpose"], "count": p["count"], "length_bits": p["length_bits"],
              "format": p["format"], "fingerprints": fps, "quantum_component_fingerprints": qfps,
              "warning": "demo keys, not for real use"}
    return result, keys


def verify(p: dict, seed: bytes, label: str, stored: dict):
    n = p["length_bits"] // 8
    qfps = [_fp(hkdf(seed, _info(label, p["purpose"], i), n)) for i in range(p["count"])]
    ok = (stored.get("quantum_component_fingerprints") == qfps and len(stored.get("fingerprints", [])) == p["count"]
          and "keys" not in stored)
    return ok, ("quantum component re-derived from the seed; final fingerprints also include local entropy "
                "and cannot be recomputed" + ("" if ok else ": MISMATCH"))
