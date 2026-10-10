# ProvaFair Website: What to Add

**Current state:** the site shows the hash ID, the quantum output, and biased results, with explanatory text.
**Problem:** it shows *results* but not *proof*. Judges can't see why the draw is trustworthy.
**Goal:** make the site show the evidence behind every draw, not only the outcome.

---

## Priority guide

| Priority | Meaning |
|---|---|
| P1 | Must have. Directly supports "results and initial validation". |
| P2 | Strong differentiator. Add if P1 is done. |
| P3 | Nice to have. Skip if short on time. |

---

## P1: Must have

### 1. Live CHSH score gauge
- A gauge or bar showing the current score **S**, with two marked lines: **S = 2** (classical limit) and **S ≈ 2.83** (quantum maximum).
- Colour zones: red at or below 2, green clearly above 2.
- Show **S ± margin of error**, not just a single number.
- Show the pass/fail rule in plain text, e.g. "Pass only if S − 3σ > 2".
- Why: this is the core of your idea. The gauge is the verification step made visible.

### 2. Clear PASS / BLOCKED state
- When the score is too low, show a large "DRAW BLOCKED" state and **do not display any random number**.
- When it passes, show "DRAW CERTIFIED" and release the number.
- Why: the "block" moment is your strongest demo beat. It must be unmistakable.

### 3. Correlation breakdown panel
- A small table of the four correlation terms that make up S, plus the final calculation.
- Show the number of shots used.
- Why: shows the score is computed, not hard-coded. Technical judges will look for this.

### 4. Circuit view
- Display the Qiskit circuit diagram (Hadamard, CNOT, measurements at chosen angles).
- Add a one-line caption: "This creates an entangled pair, each side measures at a different angle."
- Why: the hackathon requires "circuit execution". Seeing the circuit on the site proves it's real.

### 5. Validation page (500 vs 500 runs)
- Two overlaid histograms of S: quantum mode vs classical/rigged mode.
- Vertical lines at S = 2 and S ≈ 2.83.
- Summary numbers beneath: mean S, spread, and how many runs passed or failed in each mode.
- Why: this is your "initial validation" evidence. It is the most important chart in the project.

### 6. Verify page that actually verifies
- Input: a Draw ID or hash.
- Output: draw result, timestamp, the S score and margin, shots used, the previous hash, and a "chain intact" status.
- Why: right now it displays a hash. It should let someone *check* a draw.

---

## P2: Strong differentiators

### 7. Hash-chain ledger view
- A visual list of draws where each entry shows its own hash and the previous hash, linked in order.
- Add a **"Verify chain"** button that re-computes all hashes.
- Add a **"Tamper with record"** button (demo only) that edits an old entry. The chain check then turns red at that exact entry.
- Why: shows the ledger is *tamper-evident*. Use that wording, not "tamper-proof".

### 8. Randomness quality tests
- A panel running standard checks on the output bits: frequency (0s vs 1s), runs test, chi-square.
- Show pass/fail for each. Your biased mode should visibly fail one or more.
- Why: gives a second, independent line of evidence beyond CHSH, and explains your biased-results feature.

### 9. "Insider attack" replay (Tipton-style)
- A small seeded pseudo-random generator that an "attacker" can predict.
- Show the attacker correctly predicting the next 5 draws.
- Then show the attacker failing to predict certified draws.
- Why: turns your background story into something people can watch.

### 10. Use-case selector
- A dropdown: **IPO allotment**, **Lottery**, **Blockchain validator selection**.
- Each one changes the input (a list of applicants, ticket numbers, or validator IDs) and shows who was selected.
- Why: proves the system is general and ties back to your three target areas.

---
