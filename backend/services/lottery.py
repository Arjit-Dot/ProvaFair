"""Lottery: k-of-N number draws, and prize draws among sold tickets."""
from core.stream import Stream, sample

NAME, LABEL = "lottery", "Lottery draw"
LIMITS = "Fixes the generator, not ticket fraud or how winners are paid."
DEFAULTS = {"game": "numbers", "pool": 49, "picks": 6, "bonus": False,
            "n_tickets": 10_000, "tiers": [{"name": "Prize", "winners": 5}]}


def normalize(p: dict) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (p or {}).items() if v is not None}}
    game = p["game"]
    if game == "numbers":
        pool, picks, bonus = int(p["pool"]), int(p["picks"]), bool(p["bonus"])
        if not 2 <= pool <= 100_000:
            raise ValueError("pool must be between 2 and 100000")
        if not 1 <= picks or picks + (1 if bonus else 0) > pool:
            raise ValueError("picks (plus bonus ball) must fit inside the pool")
        return {"game": "numbers", "pool": pool, "picks": picks, "bonus": bonus}
    if game == "tickets":
        n = int(p["n_tickets"])
        tiers = [{"name": str(t["name"]), "winners": int(t["winners"])} for t in p["tiers"]]
        if not 1 <= n <= 100_000:
            raise ValueError("n_tickets must be between 1 and 100000")
        if not tiers or any(t["winners"] < 1 for t in tiers) or sum(t["winners"] for t in tiers) > n:
            raise ValueError("tiers need at least 1 winner each and cannot exceed the ticket count")
        return {"game": "tickets", "n_tickets": n, "tiers": tiers}
    raise ValueError("game must be 'numbers' or 'tickets'")


def compute(p: dict, seed: bytes, label: str) -> dict:
    st = Stream(seed, f"lottery|{label}")
    if p["game"] == "numbers":
        drawn = [i + 1 for i in sample(p["pool"], p["picks"] + (1 if p["bonus"] else 0), st)]
        return {"game": "numbers", "numbers": sorted(drawn[:p["picks"]]),
                "bonus": drawn[p["picks"]] if p["bonus"] else None}
    total = sum(t["winners"] for t in p["tiers"])
    idx = sample(p["n_tickets"], total, st)
    out, pos = [], 0
    for t in p["tiers"]:
        out.append({"tier": t["name"], "tickets": [f"T-{i + 1:06d}" for i in idx[pos:pos + t["winners"]]]})
        pos += t["winners"]
    return {"game": "tickets", "prizes": out}


def run(p: dict, seed: bytes, label: str):
    return compute(p, seed, label), None


def verify(p: dict, seed: bytes, label: str, stored: dict):
    ok = compute(p, seed, label) == stored
    return ok, "draw recomputed from seed and parameters" + ("" if ok else ": MISMATCH")
