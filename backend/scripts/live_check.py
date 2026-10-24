"""Competition-day readiness check. Read-only: no QPU time is used.

  python scripts/live_check.py

Reports whether live hardware is usable right now, and whether every service has a saved hardware run to fall back to.
"""
import _path  # noqa: F401
from core import hardware, pipeline, store
from services import REGISTRY

cfg = pipeline.live_config()
print(f"Live target: {hardware.live_spec()}  (limit {cfg['max_pending']} queued jobs, wait {cfg['queue_timeout']:g}s, "
      f"cap {cfg['max_jobs']} live jobs per server run)")
probe = hardware.live_probe_safe(60)
if probe["ok"]:
    print(f"IBM reachable. Least busy: {probe['backend']}, {probe['pending']} jobs queued -> "
          + ("LIVE would run on hardware" if probe["pending"] <= cfg["max_pending"] else "LIVE would fall back to saved runs"))
else:
    print(f"IBM NOT reachable ({probe['error']}) -> LIVE would fall back to saved runs")
print("\nSaved hardware runs available for fallback:")
bad = 0
for s in REGISTRY:
    runs = [r for r in store.list_runs(s) if r["certified"] and r["source"] == "hardware" and not r["replay_of"]]
    bad += not runs
    if runs:
        r = runs[0]
        print(f"  {s:8} OK    {r['run_id']}  S = {r['S']:.3f}  {r['backend']}  {r['badge']['date']}")
    else:
        print(f"  {s:8} MISSING  record one with scripts/submit.py --service {s} --backend open")
print("\nREADY: every service can fall back." if not bad else f"\nNOT READY: {bad} service(s) have no saved hardware run.")
