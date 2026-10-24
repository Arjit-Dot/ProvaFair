"""Web3: stake-weighted validator selection without replacement, plus a 32-byte randomness beacon."""
from core.stream import Stream

NAME, LABEL = "web3", "Validator selection and beacon"
LIMITS = ("The Bell test certifies the seed, not the chain. An optional testnet anchor would fix the record "
          "publicly (timing and consistency), not prove randomness quality.")
DEFAULTS = {"n_validators": 20, "seats": 5, "epoch_id": 1}


def _gen(n: int) -> list[dict]:
    return [{"id": f"validator-{i + 1:03d}", "stake": 32 * (1 + (i * 7919) % 23)} for i in range(n)]


def normalize(p: dict) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (p or {}).items() if v is not None}}
    try:
        out = {"seats": int(p["seats"]), "epoch_id": int(p["epoch_id"])}
    except (TypeError, ValueError):
        raise ValueError("seats and epoch_id must be integers")
    if out["epoch_id"] < 0:
        raise ValueError("epoch_id must be >= 0")
    vals = p.get("validators")
    if vals:
        seen = set()
        for v in vals:
            if not isinstance(v, dict) or not str(v.get("id", "")).strip() or int(v.get("stake", 0)) <= 0:
                raise ValueError("each validator needs an id and a positive integer stake")
            if str(v["id"]) in seen:
                raise ValueError("duplicate validator ids")
            seen.add(str(v["id"]))
        out["validators"] = [{"id": str(v["id"]), "stake": int(v["stake"])} for v in vals]
        n = len(vals)
    else:
        n = int(p["n_validators"])
        if not 1 <= n <= 5000:
            raise ValueError("n_validators must be between 1 and 5000")
        out["n_validators"] = n
    if not 1 <= out["seats"] <= n:
        raise ValueError("seats must be between 1 and the number of validators")
    return out


def compute(p: dict, seed: bytes, label: str) -> dict:
    remaining = [dict(v) for v in (p.get("validators") or _gen(p["n_validators"]))]
    st = Stream(seed, f"web3|{label}")
    committee = []
    for _ in range(p["seats"]):
        total = sum(v["stake"] for v in remaining)
        r = st.randbelow(total)          # exact integer, uniform over remaining stake
        acc = 0
        for i, v in enumerate(remaining):
            acc += v["stake"]
            if r < acc:
                committee.append(remaining.pop(i))
                break
    beacon = Stream(seed, f"web3-beacon|{label}|{p['epoch_id']}").bytes(32).hex()
    return {"epoch_id": p["epoch_id"], "committee": committee, "beacon": beacon}


def run(p: dict, seed: bytes, label: str):
    return compute(p, seed, label), None


def verify(p: dict, seed: bytes, label: str, stored: dict):
    ok = compute(p, seed, label) == stored
    return ok, "committee and beacon recomputed from seed and parameters" + ("" if ok else ": MISMATCH")
