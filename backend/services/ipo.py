"""IPO allotment: fair, reproducible allotment when an offer is oversubscribed (simplified model)."""
from core.stream import Stream, shuffle

NAME, LABEL = "ipo", "IPO allotment"
LIMITS = ("Simplified model: every valid applicant is allotted one lot until lots run out. Rules differ by country "
          "and offer. It does not detect duplicate or fake applicants and does not decide eligibility.")
DEFAULTS = {"total_shares": 1_000_000, "retail_pct": 35.0, "lot_size": 100, "price": 100.0, "n_applicants": 5000}


def normalize(p: dict) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (p or {}).items() if v is not None}}
    try:
        out = {"total_shares": int(p["total_shares"]), "retail_pct": float(p["retail_pct"]),
               "lot_size": int(p["lot_size"]), "price": float(p["price"])}
    except (TypeError, ValueError):
        raise ValueError("total_shares, retail_pct, lot_size and price must be numbers")
    if out["total_shares"] <= 0 or out["lot_size"] <= 0 or out["price"] <= 0:
        raise ValueError("total_shares, lot_size and price must be positive")
    if not 0 < out["retail_pct"] <= 100:
        raise ValueError("retail_pct must be in (0, 100]")
    apps = p.get("applicants")
    if apps:
        ids = []
        for a in apps:
            if not isinstance(a, dict) or not str(a.get("id", "")).strip():
                raise ValueError("each applicant needs an id")
            if int(a.get("lots", 1)) < 1:
                raise ValueError("applicants must apply for at least 1 lot")
            ids.append(str(a["id"]))
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate applicant ids in the list")
        if len(ids) > 100_000:
            raise ValueError("at most 100000 applicants")
        out["applicants"] = [{"id": str(a["id"]), "lots": int(a.get("lots", 1))} for a in apps]
    else:
        n = int(p["n_applicants"])
        if not 1 <= n <= 100_000:
            raise ValueError("n_applicants must be between 1 and 100000")
        out["n_applicants"] = n
    return out


def _ids(p: dict) -> list[str]:
    if "applicants" in p:
        return [a["id"] for a in p["applicants"]]
    return [f"APP-{i + 1:06d}" for i in range(p["n_applicants"])]


def compute(p: dict, seed: bytes, label: str) -> dict:
    ids = _ids(p)
    lots = (int(p["total_shares"] * p["retail_pct"] / 100) // p["lot_size"])
    n = len(ids)
    over = n > lots
    if over:
        order = shuffle(ids, Stream(seed, f"ipo|{label}"))
        allottees, waiting = order[:lots], order[lots:]
    else:
        allottees, waiting = ids, []
    return {"lots_available": lots, "applicants": n, "oversubscribed": over,
            "oversubscription_ratio": round(n / lots, 4) if lots else None,
            "allottees": allottees, "waiting_list": waiting}


def run(p: dict, seed: bytes, label: str):
    return compute(p, seed, label), None


def verify(p: dict, seed: bytes, label: str, stored: dict):
    ok = compute(p, seed, label) == stored
    return ok, "allotment recomputed from seed and parameters" + ("" if ok else ": MISMATCH")
