"""Tamper-evident hash chain. Each entry hashes its own fields plus the previous hash."""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone

DB = "chain_ledger.db"
GENESIS = "0" * 64
_lock = threading.Lock()
FIELDS = ["draw_id", "mode", "event_name", "timestamp", "chsh_score", "sigma",
          "shots", "status", "winners", "prev_hash"]


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_chain():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS chain (
            idx INTEGER PRIMARY KEY AUTOINCREMENT, draw_id TEXT UNIQUE, mode TEXT, event_name TEXT,
            timestamp TEXT, chsh_score REAL, sigma REAL, shots INTEGER, status TEXT,
            winners TEXT, prev_hash TEXT, hash TEXT, orig_winners TEXT)""")


def compute_hash(rec: dict) -> str:
    payload = {k: rec[k] for k in FIELDS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def append(draw_id, mode, event_name, chsh_score, sigma, shots, status, winners) -> dict:
    with _lock, _conn() as c:
        row = c.execute("SELECT hash FROM chain ORDER BY idx DESC LIMIT 1").fetchone()
        rec = {"draw_id": draw_id, "mode": mode, "event_name": event_name,
               "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "chsh_score": round(chsh_score, 4), "sigma": round(sigma, 4), "shots": shots,
               "status": status, "winners": json.dumps(winners or []),
               "prev_hash": row["hash"] if row else GENESIS}
        rec["hash"] = compute_hash(rec)
        c.execute("""INSERT INTO chain (draw_id,mode,event_name,timestamp,chsh_score,sigma,shots,
                     status,winners,prev_hash,hash) VALUES (:draw_id,:mode,:event_name,:timestamp,
                     :chsh_score,:sigma,:shots,:status,:winners,:prev_hash,:hash)""", rec)
    return rec


def _out(r) -> dict:
    d = dict(r)
    d["winners"] = json.loads(d["winners"])
    d["tampered"] = d.pop("orig_winners") is not None
    return d


def all_entries(limit: int = 200):
    with _conn() as c:
        rows = c.execute("SELECT * FROM (SELECT * FROM chain ORDER BY idx DESC LIMIT ?) ORDER BY idx",
                         (limit,)).fetchall()
    return [_out(r) for r in rows]


def get(draw_id: str):
    with _conn() as c:
        r = c.execute("SELECT * FROM chain WHERE draw_id=?", (draw_id,)).fetchone()
    return _out(r) if r else None


def verify_chain() -> dict:
    """Recompute every hash and check every link."""
    with _conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM chain ORDER BY idx").fetchall()]
    entries, prev, first_break = [], GENESIS, None
    for i, r in enumerate(rows):
        hash_ok = compute_hash(r) == r["hash"]
        link_ok = r["prev_hash"] == prev
        if first_break is None and not (hash_ok and link_ok):
            first_break = i
        entries.append({"draw_id": r["draw_id"], "hash_ok": hash_ok, "link_ok": link_ok})
        prev = r["hash"]
    return {"intact": first_break is None, "first_break_index": first_break,
            "first_break_draw_id": rows[first_break]["draw_id"] if first_break is not None else None,
            "checked": len(rows), "entries": entries}


def tamper(draw_id: str) -> bool:
    """DEMO ONLY: silently rewrite stored winners without re-hashing."""
    with _lock, _conn() as c:
        r = c.execute("SELECT winners, orig_winners FROM chain WHERE draw_id=?", (draw_id,)).fetchone()
        if not r:
            return False
        c.execute("UPDATE chain SET winners=?, orig_winners=COALESCE(orig_winners, winners) WHERE draw_id=?",
                  (json.dumps(["Ticket #000000 (forged)"]), draw_id))
    return True


def restore_all() -> int:
    with _lock, _conn() as c:
        cur = c.execute("UPDATE chain SET winners=orig_winners, orig_winners=NULL WHERE orig_winners IS NOT NULL")
        return cur.rowcount
