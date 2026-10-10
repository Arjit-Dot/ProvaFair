# ProvaFair evidence layer

## Run
    pip install -r requirements.txt
    cd backend  && uvicorn main_example:app --port 8000
    cd frontend && streamlit run app.py

Already have a FastAPI app? Add two lines to your main.py instead of using main_example.py:
    import api_v2
    app.include_router(api_v2.router)

Optional: put a looping `background.mp4` in `frontend/` (or set VIDEO_URL in ui/theme.py).

## Backend (all new files, no changes to your existing engines)
| File | Does |
|---|---|
| quantum/chsh_analysis.py | Qiskit circuits, 4 correlations, sigma, 3-sigma rule, circuit image |
| quantum/entropy.py | Bits to unbiased winners, seeded classical server |
| quantum/randomness_tests.py | Frequency, runs, chi-square |
| ledger/chain_ledger.py | SHA-256 hash chain, verify, tamper (demo), restore |
| usecases.py | IPO / lottery / validator labels |
| validation.py | 500 vs 500 runs, cached |
| api_v2.py | /v2/* endpoints |

## Frontend views
Live draw (items 1-4, 10), Validation (5), Verify a draw (6), Ledger (7), Randomness tests (8), Insider attack (9).
