"""Seed extraction from per-shot bitstrings (order matters, so counts alone are not enough)."""
import hashlib
import json


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_hex(obj) -> str:
    data = obj if isinstance(obj, (bytes, bytearray)) else canonical(obj).encode()
    return hashlib.sha256(data).hexdigest()


def params_hash(params: dict) -> str:
    return sha256_hex(params)


def derive_seed(bitstrings_by_circuit: dict, params_hash_hex: str, job_id: str, domain: str) -> bytes:
    blob = canonical(bitstrings_by_circuit)
    return hashlib.sha3_256(f"{domain}|{params_hash_hex}|{job_id}|{blob}".encode()).digest()
