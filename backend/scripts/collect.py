"""Fetch a submitted job's per-shot results and finalize the run (certificate, seed, service output, receipt)."""
import argparse

import _path  # noqa: F401
from core import hardware, pipeline, store

ap = argparse.ArgumentParser()
ap.add_argument("--service", required=True, choices=["ipo", "web3", "lottery", "keys"])
ap.add_argument("--run-id", required=True)
ap.add_argument("--account", default="open")
a = ap.parse_args()

d = store.run_dir(a.service, a.run_id)
meta = hardware.collect_job(d, a.account)
receipt, _ = pipeline.finalize_run(a.service, a.run_id)
print(f"{a.run_id}: {receipt['status']}  S = {receipt['S']} ± {receipt['sigma']}  "
      f"backend {receipt['backend']}  job {receipt['job_id']}")
v = pipeline.verify_run(a.service, a.run_id)
for c in v["checks"]:
    print(f"  [{'x' if c['ok'] else ' '}] {c['name']}")
