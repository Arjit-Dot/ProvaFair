# ProvaFair: Verifiable Quantum Randomness

*Randomness you can verify, not just trust.*

## The problem

Lotteries, IPO allotments and blockchain validator selection all depend on random number generators. Ordinary computers use pseudo-random generators (PRNGs), which are deterministic: anyone who knows the seed can predict every outcome. From the outside, a fair draw and a rigged draw look identical.

## The solution

ProvaFair runs a simulated quantum **Bell test (CHSH)** on entangled qubits alongside every draw. The test produces a score **S**:

- **S ≤ 2**: the source behaves classically and could be predictable. The draw is **blocked** and no numbers are released.
- **S > 2** (maximum ≈ 2.83): the source shows quantum entanglement, which no seed or hidden variable can explain. The draw is **certified**.

Every certified draw is written to a SHA-256 hash-chained ledger, so anyone can audit it later.

## 1. Install

Requires Python 3.10+.

```bash
git clone git@github.com:Arjit-Dot/ProvaFair.git
cd ProvaFair

python3 -m venv env
source env/bin/activate          # Windows: env\Scripts\activate

pip install -r requirements.txt
```

`requirements.txt` installs Streamlit, Qiskit and Qiskit Aer, NumPy, pandas, Plotly, FastAPI, Uvicorn and Requests.

## 2. Run

You need **two terminals**, both with the virtual environment activated (`source env/bin/activate`). Start the backend first.

**Terminal 1: backend API** (FastAPI, port 8000)

```bash
cd ProvaFair/backend
uvicorn main:app --reload --port 8000
```

**Terminal 2: frontend** (Streamlit, port 8501)

```bash
cd ProvaFair/frontend
streamlit run app.py
```

Open **http://localhost:8501** in your browser. The frontend calls the backend at `http://127.0.0.1:8000`. If the backend isn't running, the pages show an error panel instead of results.

## 3. Using the app

The pages are in the top navigation bar. A suggested order for a first walkthrough:

### Live draw

Run a draw and see the evidence behind it.

1. Choose a **Use case**: lottery, IPO allotment or validator selection. This sets sensible defaults for the pool and winners.
2. Choose the **Engine**: *Quantum* for a real entangled circuit, or *Classical (seeded)* to simulate a rigged or predictable source.
3. Set the **Pool** size and the number of **Winners**, then click **Run draw**.
4. Read the results:
   - **Verdict and CHSH gauge**: S with its margin, against the classical limit (2) and the quantum maximum (≈ 2.83). Quantum is certified. Classical is **blocked** and **no numbers are shown**.
   - **Selected winners**: shown only when certified, along with the Draw ID.
   - **Correlation breakdown**: the four correlation terms and the shot count behind S.
   - **Circuit**: the Qiskit circuit (Hadamard, CNOT, measurements at the chosen angles).

Copy the Draw ID to use on the Verify page.

### Validation

The main evidence that the test separates quantum from classical.

1. Click **Run validation**. It runs 500 quantum and 500 classical CHSH tests (1,024 shots per setting). This can take a while.
2. Compare the two histograms of S, with lines at S = 2 and S ≈ 2.83, and the summary numbers (mean, spread, pass and fail counts).
3. Click **Re-run from scratch** to ignore the cached result and recompute.

### Verify a draw

Check a past draw, as a public auditor would.

1. Paste a **Draw ID** (for example `DRAW-Q-...`), or pick one from **Or pick a recent draw**.
2. Click **Verify draw**.
3. Review the checks: the winning numbers, timestamp, S score and margin, shots used, hashes, and whether the chain is intact.

### Ledger

The tamper-evident hash chain of all draws. Each record stores its own hash and the previous record's hash.

1. Click **Add 3 sample draws** if the ledger is empty.
2. Click **Verify chain** to recompute every hash. A healthy chain shows as intact.
3. Pick a record under **Record to edit** and click **Tamper with record (demo)**. Verify again and the chain breaks at exactly that record.
4. Click **Restore** to undo the tampering.

### Insider attack

A demo of why seeded PRNGs are unsafe. This page can be hidden with the **Insider attack page** toggle in the sidebar.

1. Pick **Classical draw** and click **Run the attack**. The attacker, holding the stolen seed, predicts the next five draws exactly.
2. Switch to **Quantum draw** and run it again. The attacker's predictions fail against certified quantum draws.

## Project layout

```
backend/
  main.py, api_v2.py     FastAPI app and the /v2 endpoints used by the UI
  quantum/               chsh_engine.py (quantum), rigged_engine.py (classical),
                         chsh_analysis.py, entropy.py, randomness_tests.py
  ledger/                audit_db.py, chain_ledger.py (SQLite hash-chained ledger)
  validation.py          500 vs 500 validation runs
  usecases.py            lottery / IPO / validator configurations
frontend/
  app.py                 Streamlit entry point and navigation
  views/                 live_draw, validation, verify, ledger, insider_attack
  ui/                    theme, components, API client
```

## How the physics works

- **Bell pair:** a Hadamard gate puts qubit 0 in a 50/50 superposition, and a CNOT entangles qubit 1 with it. Without entanglement, the CHSH score can't exceed 2.
- **Measurement:** each qubit is measured after a Y-axis (`Ry`) rotation. The correlation is `E = (n00 + n11 - n01 - n10) / total`.
- **CHSH score:** four angle settings (0, π/2 and π/4, 3π/4) give the maximum violation. `S = |E1 - E2 + E3 + E4|`. Classical sources are limited to S ≤ 2, and quantum reaches Tsirelson's bound of 2√2 ≈ 2.83.
- **Random numbers:** the raw per-shot measurement outcomes (1,024 shots) are turned into unbiased winner IDs.
- **Classical engine:** `rigged_engine.py` uses a seeded Python PRNG (seed `1337`). It is capped at S ≤ 2 and is fully predictable to anyone with the seed, which is what the Insider attack page exploits.
- **Ledger:** each draw record (ID, event, S, status, winners) is hashed with SHA-256 and chained to the previous record's hash in SQLite, so edits are detectable. It is tamper-evident, not tamper-proof.

## Tech stack

Python 3.10+, IBM Qiskit (Aer simulator), FastAPI + Uvicorn, Streamlit, Plotly, SQLite.
