# Recorded IBM hardware runs (2026-10-24)

Backend `ibm_fez` (Heron, IBM Quantum Open Plan), qubit pair (143, 144) for the 4096-shot runs. Per-shot bitstrings are in each run's `bitstrings.json`; every run passes all 5 Verify checks. Total billed QPU time for all jobs: 32 s.

| Service | Run | Job ID | Shots/setting | S | sigma | Result |
|---|---|---|---|---|---|---|
| IPO | IPO-20261024-115811-95BA | dbe9qpgm94ac738rf0sg | 4096 | 2.726 | 0.023 | CERTIFIED |
| Web3 | WEB3-20261024-115920-7D33 | dbe9r8vpc3tc739lav80 | 4096 | 2.739 | 0.023 | CERTIFIED |
| Lottery | LOTTERY-20261024-115959-BD16 | dbe9rj0m94ac738rf1lg | 4096 | 2.785 | 0.022 | CERTIFIED |
| Keys | KEYS-20261024-120037-5812 | dbe9rs0m94ac738rf200 | 4096 | 2.749 | 0.023 | CERTIFIED |
| Control (no entanglement, run under Lottery) | LOTTERY-20261024-120126-56A6 | dbe9s8fsstms73fbmvl0 | 4096 | 0.080 | 0.027 | BLOCKED (S <= 2, as it must be) |
| IPO test | IPO-20261024-111903-E026 | dbe98d7gdj9s73fldaqg | 256 | 2.719 | 0.091 | CERTIFIED |

S is below the ideal 2.83 because of hardware noise. Pass rule: S - 3 sigma > 2. The Bell-test certifies the seed; a cryptographic function expands it. The Keys run is a demo (recorded seeds are no longer secret).
Dashboard screenshots (`dashboard.png`) still need to be added by hand to each run folder.
