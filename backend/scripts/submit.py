"""Commit parameters, then submit the CHSH job. Exits right after writing job_meta.json.

  python scripts/submit.py --service ipo --backend fake:FakeKingston          # local noisy fake, no QPU time
  python scripts/submit.py --service ipo --backend open --shots 4096          # REAL IBM hardware (uses QPU minutes)
  add --control for the no-entanglement control circuit, --params file.json for custom parameters
"""
import argparse
import json

import _path  # noqa: F401
from core import hardware, pipeline, store

ap = argparse.ArgumentParser()
ap.add_argument("--service", required=True, choices=["ipo", "web3", "lottery", "keys"])
ap.add_argument("--params", help="JSON file with service parameters (defaults used if omitted)")
ap.add_argument("--scenario", default="default")
ap.add_argument("--backend", default="fake:FakeKingston", help="'open' for real IBM hardware, or fake:<Name>")
ap.add_argument("--shots", type=int, default=4096)
ap.add_argument("--control", action="store_true", help="remove the CNOT (no entanglement)")
ap.add_argument("--account", default="open", help="saved QiskitRuntimeService account name")
a = ap.parse_args()

if a.backend == "open":
    print("About to submit to REAL IBM hardware. This spends QPU runtime from your Open Plan allowance.")
params = json.load(open(a.params)) if a.params else {}
source = "hardware" if a.backend == "open" else "sim"
run_id, _, info = pipeline.commit_run(a.service, params, a.scenario, source=source)
meta = hardware.submit_job(info["dir"], a.shots, not a.control, a.backend, a.account)
print(f"Committed params_hash {info['params_hash']}")
print(f"Submitted {meta['job_id']} on {meta['backend']} (pair {meta['pair']}). run_id = {run_id}")
print(f"Next: python scripts/collect.py --service {a.service} --run-id {run_id}")
