# ProvaFair Final: Real Hardware + Four Services

This plan covers:
1. Moving from the Qiskit simulator to real, free quantum hardware
2. Four separate services: **IPO**, **Web3/Blockchain**, **Lottery**, **Keys (cybersecurity)**
3. How each service runs, and how to run and set it up on hardware
4. Saving results locally because of the queue, then replaying them in the presentation

**Code in this file has not been run.** Package versions and API details change, so test every script on a simulator first and check IBM's current docs.

---

# 0. Reality check (read this first)

## What the free tier gives you (checked October 2026)

| Fact | Detail |
|---|---|
| Free plan | IBM Quantum **Open Plan**: up to **10 minutes of QPU runtime per 28-day rolling window** |
| Bonus | One-time offer of **180 minutes for 12 months**, but only after you have used 20 minutes of runtime in a 12-month period, and you need a non-trial account |
| Hardware | The Open Plan fleet includes the Heron r2 processor **ibm_kingston** (the fleet can change, so list what you can see in your account) |
| Execution modes | Open Plan can use **job mode or batch mode only, not sessions** |
| Other providers | I only checked IBM. One source I saw says AWS's free tier covers a simulator, not free hardware |

So the realistic plan is **IBM Open Plan, about 10 minutes total**. Every job counts, so test on a simulator first. Confirm all of this in your own dashboard, since terms change.

## What changes about your claims on real hardware

| Topic | What to expect | What to say |
|---|---|---|
| **S value** | Noise lowers it. Expect somewhere below 2.83 (roughly 2.5 to 2.75 on a good qubit pair, but measure it). Still above 2 means the test passes | Report your real S with its margin, plus the backend name and date |
| **"Device-independent"** | Both qubits sit on one chip. They are not separated, settings are not chosen by independent random sources per round, and loopholes are not closed | Say **"Bell-test-based randomness certification, under stated assumptions."** Do not say "device-independent" or "proves" |
| **Entropy per round** | Below 1 bit when S is below 2.83. A commonly cited rough bound for the simplest case is min-entropy ≥ 1 − log2(1 + √(2 − S²/4)), about 0.49 bits at S = 2.7 and 0.19 at S = 2.4. Verify against the source (Pironio et al., Nature 2010) before quoting | Don't claim "1 bit per shot" |
| **Settings per round** | Batching runs each of the four settings as a block, not randomly per round | State this as a simplification |
| **Cloud provider sees your bits** | IBM runs the job, so IBM sees the results | Matters for the Keys service (section 5.4) |

---

# 1. Architecture: one shared core, four services

```
provafair/
  core/
    hardware.py     # pick backend + qubit pair, submit jobs, collect results
    chsh.py         # E values, S, sigma, pass/block rule
    seed.py         # extract a 256-bit seed from per-shot bits, commit/reveal
    stream.py       # deterministic expander + unbiased integers + shuffle
    ledger.py       # hash-chained ledger (reuse what you built)
    store.py        # save/load run folders
  services/
    ipo.py          # IPO allotment
    web3.py         # validator selection + randomness beacon
    lottery.py      # k-of-N draws
    keys.py         # key/token generation
  api/main.py       # FastAPI routers: /ipo, /web3, /lottery, /keys, /verify
  data/runs/<service>/<run_id>/...   # recorded hardware runs
  scripts/submit.py  scripts/collect.py
```

**Three modes** (set with an environment variable, and show the active mode as a badge in the UI):

| Mode | Source of bits | Badge |
|---|---|---|
| `replay` | Recorded real-hardware run from `data/runs` | "HARDWARE (recorded), backend, date, job ID" |
| `sim` | Qiskit Aer simulator | "SIMULATOR" |
| `classical` | Seeded classical generator (rigged device demo) | "CLASSICAL" |

Presentation runs in `replay`. Never label a replay as live.

---

# 2. Hardware setup (step by step)

1. **Create an IBM Quantum Platform account** and choose the Open Plan. Note the account must be a non-trial account to qualify for the 180-minute offer later.
2. **Get credentials** from the dashboard: your API key and the **instance CRN**.
3. **Install:**
   ```bash
   pip install qiskit qiskit-ibm-runtime qiskit-aer
   ```
4. **Save credentials once** (use a named account, and keep the token out of git):
   ```python
   from qiskit_ibm_runtime import QiskitRuntimeService
   QiskitRuntimeService.save_account(
       channel="ibm_quantum_platform",
       token="<API_KEY>",
       instance="<CRN>",
       name="open",
       overwrite=True,
   )
   ```
   Add any `.env` or credentials file to `.gitignore`. Never put the token in the README or video.
5. **List backends you can use:**
   ```python
   service = QiskitRuntimeService(name="open")
   for b in service.backends(operational=True, simulator=False):
       print(b.name, b.num_qubits, b.status().pending_jobs)
   ```
6. **Dry run without spending QPU time.** Run the whole pipeline on Aer, and on a fake backend from `qiskit_ibm_runtime.fake_provider`, which mimics real noise.
7. **One tiny hardware job** (a few hundred shots). Check the dashboard for how many seconds it billed, then extrapolate your budget.

---

# 3. Hardware job design

## Circuits (reuse your CHSH circuit)

- Four circuits for the settings A0B0, A0B1, A1B0, A1B1 (H, CNOT, Ry rotations, measure).
- **One control circuit** with the CNOT removed (no entanglement). Run it on the same hardware as a **real "rigged device"**: its S must stay at or below 2. This lets your "blocked" demo come from real hardware too.

## Choose the best qubit pair (costs no QPU time)

Pick the connected pair with the lowest two-qubit gate error plus readout error from the backend's `target`. Sketch:

```python
def pair_score(t, q0, q1):
    err = None
    for op in t.operation_names:
        props = t[op]
        if props and (q0, q1) in props and props[(q0, q1)] is not None \
           and props[(q0, q1)].error is not None:
            err = props[(q0, q1)].error
            break
    ro = sum((t["measure"][(q,)].error or 0) for q in (q0, q1))
    return (err if err is not None else 1.0) + ro

t = backend.target
q0, q1 = min(backend.coupling_map.get_edges(), key=lambda e: pair_score(t, *e))
```

Transpile with that layout:
```python
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
pm = generate_preset_pass_manager(optimization_level=1, backend=backend,
                                  initial_layout=[q0, q1])
isa_circuits = [pm.run(c) for c in circuits]
```

## Job plan (about 6 to 7 jobs)

| Job | Purpose | Shots per circuit |
|---|---|---|
| 0 | Tiny test | 256 |
| 1 | IPO service run | 4096 |
| 2 | Web3 service run | 4096 |
| 3 | Lottery service run | 4096 |
| 4 | Keys service run | 4096 |
| 5 | Control (no entanglement), for the blocked demo | 4096 |
| 6 | Spare | as needed |

Each job holds its circuits together, so one job costs one queue wait. **Measure the billed seconds on job 0 and the first real job before committing to the rest.** A small job like this commonly uses only a few seconds of runtime, but confirm in your dashboard.

**Submit early.** Queue time can be hours, and the 28-day window means a bad run costs real minutes.

---

# 4. The shared pipeline (every service uses the same steps)

1. **Commit.** Hash the draw parameters (`params_hash`) and append it to the ledger **before** submitting. This stops an operator from choosing parameters after seeing the result.
2. **Submit** the job. Immediately save the `job_id` to disk.
3. **Collect** later: reconnect with the saved job ID and download the results.
4. **Certify.** Compute the four E values, S, and σ from the per-shot results. Pass only if S − 3σ > 2.
5. **Extract the seed.** Hash the **per-shot bitstrings** (in order), plus the job ID and `params_hash`, with a domain label, into a 256-bit seed.
6. **Run the service algorithm** using a deterministic stream seeded from that seed.
7. **Write a receipt** and append a ledger entry.
8. **Verify** by recomputing steps 4 to 6 from the saved files.

**Important: store per-shot bitstrings, not only counts.** Counts are a summary and throw away the order and most of the entropy. Use `pub.data.c.get_bitstrings()` and compute counts yourself.

**Why a seed plus a stream?** Free hardware gives you thousands of noisy bits, not millions. You extract one 256-bit seed from them and expand it with a cryptographic function (HMAC-SHA256 in the sketch below). That is the standard "seed a secure generator with real randomness" pattern. The attacker's problem changes from guessing a clock-based seed to guessing a 256-bit seed. Be clear in your pitch that the Bell test certifies the **seed**, and the expansion is cryptographic.

**Each real draw needs a fresh certified seed.** For the demo you reuse a recorded seed to show several scenarios, using a different label per scenario. Say so.

---

# 5. The four services

## 5.1 IPO allotment service

**Purpose:** fair, reproducible allotment when an offer is oversubscribed.

| | |
|---|---|
| **Inputs** | Total shares offered, retail percentage, lot size, price, applicant list (ID, lots applied for) |
| **Derived values** | Lots available = floor(retail shares ÷ lot size). Applicants N. Oversubscription ratio |
| **Algorithm** | If N ≤ lots available, every valid applicant gets a lot. Otherwise shuffle applicant IDs with Fisher–Yates (using unbiased integers) and give the first `lots available` applicants one lot each. Also publish the full shuffled order as the waiting list |
| **Hardware use** | One certified seed per offer |
| **Receipt** | Parameters, `params_hash`, job ID, backend, S ± σ, seed hash, allottee list, waiting-list order |
| **Verify step** | Recompute the shuffle from seed and parameters, and compare |
| **Demo scenarios** | (a) Undersubscribed offer, everyone allotted. (b) Heavily oversubscribed offer, most applicants lose |
| **Limits to state** | Rules vary by country and offer, so this is a simplified model. It does not detect duplicate or fake applicants, and it does not decide who is eligible |

## 5.2 Web3 / blockchain service

**Purpose:** unbiased validator selection and a public randomness beacon.

| | |
|---|---|
| **Inputs** | Validator list with stakes, number of seats, epoch ID |
| **Algorithm** | Stake-weighted selection without replacement: pick a number uniformly in [0, remaining stake) with exact integers, find the validator it falls on, remove them, repeat. Also output a 32-byte **beacon value** |
| **Hardware use** | One certified seed per epoch |
| **Receipt** | Committee, beacon value, parameters hash, job ID, S ± σ |
| **Optional on-chain anchor** | Store `(epochId, beaconHash)` in a small smart contract on a free **testnet**. The contract cannot check the quantum test, but it fixes the record publicly, which closes the "rewrite the whole ledger" gap |
| **Verify step** | Recompute committee and beacon from the seed |
| **Demo scenarios** | (a) 5 seats from 20 validators with uneven stakes. (b) A repeat with a different epoch label |
| **Limits to state** | The testnet anchor proves timing and consistency, not randomness quality |

## 5.3 Lottery service

**Purpose:** k-of-N number draws and winner selection among sold tickets.

| | |
|---|---|
| **Inputs** | Pool size N, picks k, optional bonus ball, optional ticket list and number of winners per prize tier |
| **Algorithm** | Sample without replacement using unbiased integers, then sort. For ticket draws, shuffle ticket IDs and take the first `winners` |
| **Hardware use** | One certified seed per draw |
| **Receipt** | Winning numbers or tickets, parameters hash, job ID, S ± σ |
| **Verify step** | Recompute from seed and parameters |
| **Demo scenarios** | (a) 6 of 49 numbers. (b) A prize draw among 10,000 ticket IDs |
| **Pairs with** | Your attack demo: the same attacker that predicts a clock-seeded draw gets no foothold here |
| **Limits to state** | Fixes the generator, not ticket fraud or how winners are paid |

## 5.4 Keys service (cybersecurity)

**Purpose:** generate keys, API tokens, and nonces from a certified seed.

| | |
|---|---|
| **Inputs** | Length (for example 256 bits), count, format (hex or base64), purpose label |
| **Algorithm** | Derive each key from the seed with HKDF or HMAC, using the purpose label and an index so keys differ. **Mix in local OS randomness** (`os.urandom`) |
| **Hardware use** | One certified seed per batch |
| **Receipt** | Key **fingerprints** (hashes), purpose, job ID, S ± σ. **Never publish or store real keys in the receipt** |

**Two honest security points you must make:**
1. **IBM sees the raw results of your job**, so a key derived only from hardware bits is not secret from the provider. Mix the quantum seed with local entropy: `key = HKDF(quantum_seed ‖ os.urandom(32))`. Then an attacker needs to know both.
2. **Recorded seeds are no longer secret.** Your demo keys must be labelled "demo keys, not for real use". In a real deployment the seed would be used once and never displayed.

**Pitch for this service:** "Keys whose seed comes from a Bell-tested source and can be audited, combined with local randomness so no single party is trusted." Do not claim it replaces a hardware security module.

---

# 6. Local storage and replay (handling the queue)

## What to save for every run

```
data/runs/<service>/<run_id>/
  params.json         # draw parameters
  params_hash.txt     # committed before submit
  job_meta.json       # job_id, backend name, qubit pair, shots, submit time, finish time, transpiled depth
  bitstrings.json     # per-shot bitstrings for each circuit, in order
  certificate.json    # E values, S, sigma, pass/block, threshold
  result.json         # the service output
  receipt.json        # everything above plus seed hash and ledger entry hash
  dashboard.png       # screenshot of the job page in the IBM dashboard
```

Also save the whole `data/runs` folder in a second place (cloud drive or a USB stick) and commit the non-secret parts to the repo.

## Collect and replay

- `submit.py` sends the job, writes `job_meta.json` with the job ID right away, and exits.
- `collect.py` reconnects later with `service.job(job_id)`, checks its status, and when done, writes the bitstrings and certificate. It can run any time, even after your submit script has ended.
- In `replay` mode, the API simply loads these files. Parameter changes during the demo re-run the **service algorithm** on the recorded seed (instant), not the hardware.

## How to present it honestly

- Say it out loud: "These results come from a real run on [backend] on [date], job ID [id]. Free-tier queues take hours, so we recorded them in advance and the demo replays the saved data."
- Show the dashboard screenshot or open the job page in your account.
- Keep the mode badge on screen.
- Judges can't look up your job, so the job metadata plus the recomputable verification is your evidence.
- If you also did a simulator run, label it clearly and keep it separate.

---

# 7. Code skeletons (untested)

## `core/stream.py`: deterministic stream, unbiased integers, shuffle

```python
import hmac, hashlib

class Stream:
    def __init__(self, seed: bytes, label: str):
        self.key = hmac.new(seed, label.encode(), hashlib.sha256).digest()
        self.ctr = 0

    def _bytes(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            out += hmac.new(self.key, self.ctr.to_bytes(8, "big"), hashlib.sha256).digest()
            self.ctr += 1
        return out[:n]

    def randbelow(self, n: int) -> int:        # uniform in [0, n), no modulo bias
        k = (n - 1).bit_length()
        nbytes = (k + 7) // 8
        while True:
            x = int.from_bytes(self._bytes(nbytes), "big") >> (8 * nbytes - k)
            if x < n:
                return x

def shuffle(items, stream):                     # Fisher-Yates
    a = list(items)
    for i in range(len(a) - 1, 0, -1):
        j = stream.randbelow(i + 1)
        a[i], a[j] = a[j], a[i]
    return a
```

## `core/seed.py`: seed from per-shot bits

```python
import hashlib, json

def derive_seed(bitstrings_by_circuit: dict, params_hash: str, job_id: str, domain: str) -> bytes:
    blob = json.dumps(bitstrings_by_circuit, sort_keys=True, separators=(",", ":"))
    return hashlib.sha3_256(f"{domain}|{params_hash}|{job_id}|{blob}".encode()).digest()
```

## `scripts/submit.py`: build, transpile, submit

```python
import json, numpy as np
from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

SETTINGS = {"A0B0": (0, np.pi/4), "A0B1": (0, -np.pi/4),
            "A1B0": (np.pi/2, np.pi/4), "A1B1": (np.pi/2, -np.pi/4)}

def chsh(a, b, entangle=True):
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    if entangle:
        qc.cx(0, 1)
    qc.ry(-a, 0); qc.ry(-b, 1)
    qc.measure([0, 1], [0, 1])
    return qc

def submit(run_dir, entangle=True, shots=4096):
    service = QiskitRuntimeService(name="open")
    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=2)
    t = backend.target
    q0, q1 = min(backend.coupling_map.get_edges(), key=lambda e: pair_score(t, *e))
    pm = generate_preset_pass_manager(optimization_level=1, backend=backend,
                                      initial_layout=[q0, q1])
    names = list(SETTINGS)
    circuits = [pm.run(chsh(*SETTINGS[n], entangle)) for n in names]
    job = Sampler(mode=backend).run(circuits, shots=shots)
    json.dump({"job_id": job.job_id(), "backend": backend.name, "pair": [q0, q1],
               "shots": shots, "circuits": names, "entangled": entangle},
              open(f"{run_dir}/job_meta.json", "w"))
    print("Submitted", job.job_id(), "on", backend.name)
```

(`pair_score` is the function from section 3.)

## `scripts/collect.py`: fetch results later

```python
import json
from qiskit_ibm_runtime import QiskitRuntimeService

def collect(run_dir):
    meta = json.load(open(f"{run_dir}/job_meta.json"))
    service = QiskitRuntimeService(name="open")
    job = service.job(meta["job_id"])
    print("Status:", job.status())
    result = job.result()                                # waits if not finished
    bits = {name: pub.data.c.get_bitstrings()            # per-shot, in order
            for name, pub in zip(meta["circuits"], result)}
    json.dump(bits, open(f"{run_dir}/bitstrings.json", "w"))
```

## Computing E and S from the bitstrings

```python
import numpy as np

def chsh_from_bits(bits):                    # bits: {"A0B0": ["00","11",...], ...}
    E, n = {}, {}
    for k, shots in bits.items():
        same = sum(1 for s in shots if s in ("00", "11"))
        E[k] = (2 * same - len(shots)) / len(shots)
        n[k] = len(shots)
    S = E["A0B0"] + E["A0B1"] + E["A1B0"] - E["A1B1"]
    sigma = np.sqrt(sum((1 - E[k]**2) / n[k] for k in E))
    return E, S, sigma, (S - 3 * sigma > 2)
```

Check the circuit and result field names (`c`) against your Qiskit version. A circuit built with `QuantumCircuit(2, 2)` names its classical register `c` by default.

---

# 8. What "Verify" means per service

For every service, the Verify page should **recompute, not just display**:

1. Re-hash `params.json` and compare with the committed `params_hash`.
2. Recompute E, S, σ from `bitstrings.json` and check S − 3σ > 2.
3. Recompute the seed from the bits, job ID, and parameters.
4. Re-run the service algorithm and compare with `result.json`.
5. Check the ledger entry and the chain.

Show each check as its own line with a tick or cross. This is the strongest part of your demo, because anyone can repeat it.

---

# 9. What to say and what not to say

| Say | Don't say |
|---|---|
| "Bell-test-based certification under stated assumptions" | "Device-independent" or "proves fairness" |
| "S = [value] ± [margin] on [backend], [date]" | "S ≈ 2.83" (that is the ideal, not your hardware result) |
| "Recorded from a real run; the free-tier queue takes hours" | Presenting a replay as live |
| "The Bell test certifies the seed, a cryptographic function expands it" | "Every number is quantum random" |
| "Keys are mixed with local entropy because the cloud sees the bits" | "Quantum keys are unhackable" |
| "Control circuit without entanglement stays at or below 2 on real hardware" | "Any scripted device is detected" (you tested one control) |

---

# 10. Suggested work order and checklist

**Order**
1. Refactor into `core/` with the simulator still working (nothing breaks).
2. Set up the IBM account and credentials, then run the tiny test job.
3. **Submit the four service jobs and the control job as early as possible**, since queue time is the schedule risk.
4. While they queue, build the four services and their Verify checks on simulator data.
5. Collect results, and compare real S against your simulated S.
6. Build `replay` mode and the mode badge.
7. Take dashboard screenshots, back up `data/runs`.
8. Update the README, scripts, and slides to the new claims.
9. Rehearse the presentation entirely in `replay` mode, with the network off.

**Checklist**
- [ ] Credentials saved, token not in git
- [ ] Tiny job run, billed seconds checked, budget estimated
- [ ] Best qubit pair chosen and recorded
- [ ] Per-shot bitstrings saved (not only counts)
- [ ] Control circuit run on hardware
- [ ] Parameters committed before each submit
- [ ] Four services each have: params, algorithm, receipt, verify
- [ ] Keys service mixes local entropy and labels demo keys
- [ ] Replay mode works offline, with a visible mode badge
- [ ] Dashboard screenshots and a backup of `data/runs`
- [ ] README updated: Bell-test-based certification, real S value, simplified IPO rules
- [ ] Presentation says clearly that results are recorded from real hardware
