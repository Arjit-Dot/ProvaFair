# ProvaFair — System Architecture & Code-Level Specification

> **Document Type:** Living Architectural Specification (Full Rewrite on Update)  
> **Target System:** ProvaFair — Quantum-Secured Provably Fair Multi-Service Platform  
> **Last Updated:** 2026-10-23  
> **Current Branch / State:** `feature/backend-ledger` (Enterprise Hardened)

---

## 1. Executive Summary & System Overview

**ProvaFair** is a production-grade, quantum-secured, provably fair randomness engine and ledger platform. It eliminates fraud and seed-tampering in high-stakes distributions—such as lotteries, Initial Public Offering (IPO) share allotments, and Proof-of-Stake blockchain validator elections—by leveraging fundamental quantum mechanics:
- **Quantum Bell Inequalities (CHSH Inequality):** True quantum entanglement generates non-local correlations that cannot be produced or predicted by any classical pseudo-random number generator (PRNG) or deterministic local hidden-variable model. A score of $S - 3\sigma > 2.0$ mathematically certifies genuine quantum entropy.
- **Fail-Closed Policy:** Numbers are never released if the physics verification fails. Classical or compromised sources are immediately blocked.
- **Tamper-Evident Dual-Ledger Architecture:** All draws are committed to an append-only hash-chained ledger and verified via cryptographic SHA-256 Merkle roots and link-by-link integrity audits.
- **Enterprise Middleware:** Incorporates API key authentication, sliding-window rate limiting, request idempotency protection, concurrency locks, circuit batching for quantum hardware compliance (IBM Quantum), and asynchronous webhook dispatching.

---

## 2. Workspace File Tree

```text
ProvaFair/
├── Dockerfile                             # Container deployment configuration
├── README.md                              # High-level architecture and quickstart guide
├── requirements.txt                       # Project dependencies (FastAPI, Qiskit, SQLAlchemy, Streamlit, etc.)
├── start.sh                               # Container entrypoint script
├── app.py                                 # Root Streamlit redirector (delegates execution to frontend/app.py)
├── project_state.md                       # Living architectural specification
├── chain_ledger.db                        # SQLite database storing tamper-evident hash-chain ledger
├── backend/
│   ├── main.py                            # Primary FastAPI application, security, idempotency, and root routes
│   ├── api_v2.py                          # V2 Evidence APIRouter (CHSH analysis, verification, tamper demo)
│   ├── usecases.py                        # Domain adapters for IPO, Lottery, and Blockchain Validator labeling
│   ├── validation.py                      # 1,000-run empirical validation engine (Aer Quantum vs Classical LHV)
│   ├── validation_cache.json              # Cached results for 500 quantum vs 500 classical validation runs
│   ├── ledger.db                          # Primary SQLite database managed via SQLAlchemy (WAL mode)
│   ├── chain_ledger.db                    # Database file instance when accessed relative to backend directory
│   ├── ledger/
│   │   ├── audit_db.py                    # SQLAlchemy ORM layer, WAL pragma, Merkle root, rate limiting, and idempotency
│   │   ├── chain_ledger.py                # Pure hash-chain ledger module with tamper injection & verify tooling
│   │   └── ledger.db                      # Local instance SQLite database
│   ├── quantum/
│   │   ├── chsh_analysis.py               # Rigorous CHSH analysis, error propagation (3-sigma margin), circuit drawer
│   │   ├── chsh_engine.py                 # Core Qiskit Bell state preparation, expectation measurement, QRNG extraction
│   │   ├── entropy.py                     # Bit-stream conversion, rejection sampling, and classical server simulation
│   │   ├── randomness_tests.py            # NIST-style statistical tests (Frequency, Runs, Chi-Square 4-bit blocks)
│   │   └── rigged_engine.py               # Classical deterministic PRNG simulation for fraud demonstration
│   ├── quantum_engine/
│   │   ├── __init__.py                    # Quantum engine package exports
│   │   └── batcher.py                     # Circuit batching partitioner for IBM Quantum hardware compliance
│   └── tests/
│       ├── stress_test.py                 # Concurrency, idempotency bombardment, webhook, & Merkle stress suite
│       └── stress_test_report.md          # Comprehensive execution report of all stress testing phases
└── frontend/
    ├── app.py                             # Modern Streamlit multi-page application root (Streamlit 1.46+ navigation)
    ├── ui/
    │   ├── api.py                         # HTTP client wrapper with caching for frontend-to-backend calls
    │   ├── components.py                  # Reusable HTML/SVG components (CHSH gauges, histograms, circuit viewer)
    │   └── theme.py                       # Glassmorphic CSS design system, typography, aurora effects, badges
    └── views/
        ├── live_draw.py                   # Tab/Page: Real-time quantum draw execution, gauge display, and winner extraction
        ├── validation.py                  # Tab/Page: Empirical 500 vs 500 distribution comparison & statistical tests
        ├── verify.py                      # Tab/Page: Public audit portal checking record hash, link, and chain integrity
        ├── ledger.py                      # Tab/Page: Hash-chain inspection with live tamper and restore demo
        └── insider_attack.py              # Tab/Page: Exploit replay demonstration (stolen seed PRNG attack vs Quantum)
```

---

## 3. Data Models & Classes

### 3.1 Pydantic Request & Response Models

#### `MultiServiceRequest` (`backend/main.py`)
Model defining multi-tenant draw execution across diverse industries:
- `service_type` (`str`, default: `"lottery"`): Distribution category (`"lottery"`, `"ipo"`, or `"validator"`).
- `service_params` (`Dict[str, Any]`, default: `{}`): Execution parameters (e.g. `{"num_winners": 4, "pool_size": 100}`).
- `webhook_url` (`str | None`, default: `None`): Optional external HTTP POST endpoint for asynchronous webhook completion.

#### `MultiServiceResponse` (`backend/main.py`)
Standardized response payload representing certified draws:
- `draw_id` (`str`): Unique identifier (e.g., `DRAW-Q-A1B2C3D4` or `DRAW-R-B2C3D4E5`).
- `service_type` (`str`): Domain of the draw.
- `status` (`str`): Certification state (`"VERIFIED - TRUE QUANTUM"` or `"REJECTED - CLASSICAL DEVICE DETECTED"`).
- `chsh_score` (`float`): Evaluated Bell test parameter $S$.
- `payload` (`Any`): Generated winners or allocated items (empty if uncertified).
- `receipt_hash` (`str`): Tamper-evident SHA-256 hash receipt.
- `previous_hash` (`str`): Hash pointer to preceding ledger record (`"GENESIS"` if first record).
- `ibm_job_id` (`str`, default: `"SIMULATED"`): Execution job tracker for physical quantum hardware verification.

#### `DrawRequest` (`backend/api_v2.py`)
Evidence-oriented request schema:
- `mode` (`Literal["quantum", "classical"]`, default: `"quantum"`): Selected entropy source.
- `use_case` (`Literal["ipo", "lottery", "validator"]`, default: `"lottery"`): Domain target.
- `pool_size` (`int`, ge=1, le=1,000,000, default: 100): Universe of eligible candidates.
- `num_winners` (`int`, ge=1, le=50, default: 4): Quantity of winners to draw.
- `event_name` (`Optional[str]`, default: `None`): Human-readable event description.
- `record` (`bool`, default: `True`): Flag controlling whether result is committed to `chain_ledger.db`.

---

### 3.2 SQLAlchemy ORM Models (`backend/ledger/audit_db.py`)

#### `Draw(Base)`
Table: `draws`
Primary persistence model for certified and rejected draws.
- `draw_id` (`String`, Primary Key): Unique alphanumeric draw identifier.
- `event_name` (`String`, `nullable=False`): Event name / description.
- `timestamp` (`String`, `nullable=False`): ISO-8601 UTC timestamp with `'Z'` suffix.
- `chsh_score` (`Float`, `nullable=False`): Calculated CHSH statistic $S$.
- `status` (`String`, `nullable=False`): System status string.
- `winners` (`Text`, `nullable=False`): JSON-encoded list of winners or payload items.
- `receipt_hash` (`String`, `nullable=False`): SHA-256 digest of concatenated draw attributes and `previous_hash`.
- `service_type` (`String`, `nullable=False`, default: `"lottery"`): Distribution category.
- `previous_hash` (`String`, `nullable=False`): Cryptographic hash pointer linking to preceding row.
- `ibm_job_id` (`String`, `nullable=True`, default: `"SIMULATED"`): Quantum hardware execution audit tracker.
- **Method `to_dict() -> dict`**: Deserializes JSON string `winners` and returns standard dictionary format.

#### `IdempotencyRecord(Base)`
Table: `idempotency_records`
Prevents duplicate requests and double-draw execution under network retries.
- `key` (`String`, Primary Key): Unique caller-supplied idempotency key (from `Idempotency-Key` header).
- `draw_id` (`String`, `nullable=False`): Alphanumeric identifier of the processed draw.
- `response_payload` (`Text`, `nullable=False`): JSON-serialized cached `MultiServiceResponse`.
- `created_at` (`String`, `nullable=False`): ISO-8601 UTC timestamp of creation.

#### `ApiUsageLog(Base)`
Table: `api_usage_logs`
Backs sliding-window rate limiting and client audit tracking.
- `id` (`Integer`, Primary Key, `autoincrement=True`): Serial record ID.
- `api_key` (`String`, `nullable=False`): Client API key making the request.
- `endpoint` (`String`, `nullable=False`): Target path (e.g., `/draw/quantum`).
- `timestamp` (`DateTime`, `default=datetime.utcnow`, `nullable=False`): Request timestamp.

---

### 3.3 Core Domain Classes

#### `ClassicalServer` (`backend/quantum/entropy.py`)
Simulates a classical pseudo-random lottery server vulnerable to insider attacks:
- `__init__(self, seed: int = 1337, bias: float = 0.5)`: Initializes Python standard `random.Random(seed)`.
- `bits(self, n: int) -> np.ndarray`: Produces $n$ bits with probability `bias`.
- `np_rng(self) -> np.random.Generator`: Returns a NumPy RNG seeded deterministically from internal PRNG bits.

#### `ReportLogger` (`backend/tests/stress_test.py`)
Automated test suite recorder:
- `record_phase(...)`: Captures inputs, expected results, actual outputs, and pass/fail verdict.
- `generate_markdown() -> str`: Formats test trajectory into comprehensive Markdown report.

---

## 4. API Endpoints & Controller Specifications

### 4.1 Primary Controller (`backend/main.py`)

#### `POST /draw/quantum`
- **Method / Route:** `api_run_quantum_draw`
- **Policies Applied:** `@RateLimit` (5 req / 60s), `@UseGuards` (`verify_api_key`), Idempotency guard (`Idempotency-Key`), Concurrency Lock (`_draw_lock`), Circuit Batching (`calculate_batches`), Asynchronous Webhooks (`BackgroundTasks`).
- **Input Parameters:**
  - Headers: `X-API-Key: str` (Required), `Idempotency-Key: str | None` (Optional).
  - Body (`MultiServiceRequest`):
    ```json
    {
      "service_type": "lottery",
      "service_params": {"num_winners": 4, "pool_size": 100},
      "webhook_url": "https://callback.corp/hook"
    }
    ```
- **Internal Logic:**
  1. Authenticates client via `verify_api_key` (constant-time token comparison).
  2. Increments and checks client rate limit against sliding 60-second window under `_rate_limit_lock`.
  3. Checks `Idempotency-Key` under `_draw_lock`; if cached, returns existing response immediately.
  4. Computes quantum hardware batch chunks using `calculate_batches(num_winners)`.
  5. Prepares Bell state circuits, measures correlations, verifies $S > 2.0$.
  6. If `webhook_url` is specified, enqueues `process_draw_background` via `background_tasks` and returns HTTP `202 Accepted` with `{"draw_id": draw_id, "status": "QUEUED"}`.
  7. If synchronous, commits draw into SQLAlchemy ledger with hash-link to `previous_hash`, writes idempotency cache, and returns HTTP `200 OK`.
- **Return Structure (`MultiServiceResponse`):**
  ```json
  {
    "draw_id": "DRAW-Q-A1B2C3D4",
    "service_type": "lottery",
    "status": "VERIFIED - TRUE QUANTUM",
    "chsh_score": 2.8284,
    "payload": [12, 34, 56, 78],
    "receipt_hash": "64_hex_character_sha256",
    "previous_hash": "previous_64_hex_character_or_GENESIS",
    "ibm_job_id": "ibm-q-job-c3ddaabe"
  }
  ```

#### `POST /draw/rigged`
- **Method / Route:** `api_run_rigged_draw`
- **Policies Applied:** `@RateLimit` (5 req / 60s), `@UseGuards` (`verify_api_key`), Idempotency guard, Concurrency Lock, Asynchronous Webhooks.
- **Input Parameters:** Same as `/draw/quantum`.
- **Internal Logic:**
  1. Simulates classical local hidden-variable engine bounded by $S \le 2.0$ ($S \approx 1.414$).
  2. Records result with status `"REJECTED - CLASSICAL DEVICE DETECTED"`, `ibm_job_id="SIMULATED"`.
  3. Commits to hash-chained ledger and triggers webhooks if requested.
- **Return Structure (`MultiServiceResponse`):**
  ```json
  {
    "draw_id": "DRAW-R-B2C3D4E5",
    "service_type": "lottery",
    "status": "REJECTED - CLASSICAL DEVICE DETECTED",
    "chsh_score": 1.4142,
    "payload": [1, 2, 3],
    "receipt_hash": "64_hex_character_sha256",
    "previous_hash": "previous_64_hex_character",
    "ibm_job_id": "SIMULATED"
  }
  ```

#### `GET /verify/{draw_id}`
- **Method / Route:** `api_verify_draw(draw_id: str)`
- **Policies Applied:** Public access.
- **Input Parameters:** `draw_id: str` (Path parameter).
- **Internal Logic:** Queries `draws` table in `ledger.db` by primary key. Raises HTTP 404 if record is missing.
- **Return Structure:**
  ```json
  {
    "draw_id": "DRAW-Q-A1B2C3D4",
    "event_name": "Quantum Secure Draw",
    "timestamp": "2026-10-23T12:00:00.000000Z",
    "chsh_score": 2.8284,
    "status": "VERIFIED - TRUE QUANTUM",
    "winners": [12, 34, 56, 78],
    "receipt_hash": "64_hex_character_sha256",
    "service_type": "lottery",
    "previous_hash": "previous_64_hex_character",
    "ibm_job_id": "ibm-q-job-c3ddaabe"
  }
  ```

#### `GET /ledger/root`
- **Method / Route:** `api_get_ledger_root()`
- **Policies Applied:** Public access.
- **Internal Logic:** Fetches all `receipt_hash` entries from `draws` ordered chronologically and computes the single 64-character SHA-256 Merkle root.
- **Return Structure:**
  ```json
  {
    "merkle_root": "cf9fe9d2d350ac2d6a396a5baeb088548f3e95597f1eb95f02fc2a81c1775c52",
    "draw_count": 162
  }
  ```

---

### 4.2 Evidence & Verification Controller (`backend/api_v2.py`)

Mounted at prefix `/v2` with tag `"evidence"`.

#### `GET /v2/usecases`
- **Function:** `get_usecases()`
- **Logic:** Returns dictionary of supported distribution profiles (`ipo`, `lottery`, `validator`) with corresponding nouns, default pool sizes, and default winners.

#### `GET /v2/circuit`
- **Function:** `get_circuit()`
- **Logic:** Renders Bell pair measurement circuit using Qiskit. Generates text representation, PNG image encoded as base64 (`iqp-dark` styling), and measurement angle table.

#### `POST /v2/draw`
- **Function:** `draw(req: DrawRequest)`
- **Input:** `DrawRequest`
- **Logic:**
  1. Executes real 2-qubit circuit on Qiskit `AerSimulator` (Quantum) or deterministic PRNG (Classical).
  2. Runs CHSH analysis evaluating $S$, standard deviation $\sigma$, and lower bound $S - 3\sigma$.
  3. Strict Fail-Closed Rule: If $S - 3\sigma \le 2.0$, draw status is `"BLOCKED"` and winners remain `None`.
  4. If certified, runs unbiased rejection sampling (`bits_to_winners`) and applies domain labels (`usecases.labels`).
  5. Commits entry to `chain_ledger.db` with hash linking to preceding block.
  6. Runs NIST-style statistical tests (Frequency, Runs, Chi-square) on generated bit stream.
- **Return Structure:**
  ```json
  {
    "draw_id": "DRAW-Q-E3F4G5H6",
    "mode": "quantum",
    "status": "CERTIFIED",
    "certified": true,
    "use_case": "lottery",
    "event_name": "Lottery draw",
    "pool_size": 1000,
    "winners": ["Ticket #000042", "Ticket #000189"],
    "winner_indices": [41, 188],
    "chsh": {
      "mode": "quantum",
      "S": 2.8251,
      "sigma": 0.0248,
      "margin": 0.0744,
      "lower_bound": 2.7507,
      "certified": true,
      "shots_per_setting": 1024,
      "total_shots": 4096,
      "correlations": [...]
    },
    "randomness": {
      "n_bits": 4096,
      "tests": [...],
      "all_passed": true,
      "ones_fraction": 0.4995
    },
    "bits_preview": "01101001...",
    "timestamp": "2026-10-23T12:00:00Z",
    "hash": "64_hex_hash",
    "prev_hash": "previous_64_hex_hash"
  }
  ```

#### `GET /v2/draw/{draw_id}`
- **Function:** `verify(draw_id: str)`
- **Logic:** Retrieves record from `chain_ledger.db`, re-computes its SHA-256 hash from attributes, verifies link to previous hash, and walks the entire chain to check for any break.
- **Return Structure:** Stored record combined with `lower_bound`, `margin`, `recomputed_hash`, `hash_ok`, `link_ok`, `chain_intact`, `chain_first_break`, and `rule_recheck` (`"PASS"` or `"FAIL"`).

#### `GET /v2/ledger`
- **Function:** `get_ledger(limit: int = 50)`
- **Logic:** Returns up to `limit` entries from `chain_ledger.db` in chronological order with tampered flags.

#### `POST /v2/ledger/verify`
- **Function:** `verify_all()`
- **Logic:** Re-computes every hash and validates every cryptographic link across all rows in `chain_ledger.db`. Returns overall intact status and index/ID of first broken link if detected.

#### `POST /v2/ledger/tamper/{draw_id}`
- **Function:** `tamper(draw_id: str)`
- **Logic:** Demo vulnerability injection. Modifies winners in place to `["Ticket #000000 (forged)"]` without re-hashing, demonstrating that audit verification immediately detects fraud.

#### `POST /v2/ledger/restore`
- **Function:** `restore()`
- **Logic:** Restores all tampered records back to their authentic `orig_winners` values.

#### `GET /v2/validation`
- **Function:** `validation(runs: int = 500, refresh: bool = False)`
- **Logic:** Executes or reads cached batch of 500 quantum circuits vs 500 classical LHV simulations (1,024 shots per setting). Computes statistical distributions (mean, std, min, max, passed, failed) showing separation across Tsirelson's bound ($2\sqrt{2} \approx 2.828$) and classical ceiling ($2.0$).

#### `POST /v2/insider-attack`
- **Function:** `insider_attack(rounds: int = 5, pool_size: int = 100, num_winners: int = 4)`
- **Logic:** Demonstrates PRNG vulnerability vs Quantum immunity. Attacker extracts seed from classical server and predicts subsequent draws with 100% accuracy. Against certified quantum draws, the seed provides 0 predictive power.

---

## 5. Task Policies, Security, & Concurrency Architecture

### 5.1 Security Guard (`@UseGuards` Equivalent)
- **Dependency:** `verify_api_key(request: Request, api_key: str = Security(api_key_header))`
- **Header:** `X-API-Key`
- **Implementation:**
  - Evaluates provided token against `PROVA_API_KEY` (env var or fallback `"PROVA-HACK-2026"`).
  - Uses `secrets.compare_digest(api_key, PROVA_API_KEY)` to ensure constant execution time and prevent timing side-channel attacks.
  - Rejects invalid requests with HTTP 401 Unauthorized.

### 5.2 Rate Limiting (`@RateLimit` Equivalent)
- **Policy:** Sliding window limit of 5 requests per 60 seconds per API key.
- **Storage:** Persisted in `api_usage_logs` table via `log_api_request()`.
- **Concurrency Control:** Synchronized under `_rate_limit_lock = threading.Lock()`.
- **Violation:** Rejects requests with HTTP 429 Too Many Requests (`"Rate limit exceeded"`).

### 5.3 Request Idempotency
- **Header:** `Idempotency-Key`
- **Storage:** Persisted in `idempotency_records` table (`key`, `draw_id`, `response_payload`, `created_at`).
- **Thread Synchronization:** Wrapped in `_draw_lock = threading.Lock()` to handle simultaneous concurrent burst requests.
- **Behavior:** If a request with an existing key is received, returns the identical cached response and draw ID without re-executing quantum simulation or adding redundant ledger entries.

### 5.4 Circuit Batching Policy
- **Module:** `backend/quantum_engine/batcher.py:calculate_batches(total_circuits, max_per_job=300)`
- **Purpose:** Hardware execution limits (e.g., IBM Quantum backend limits of 300 circuits per job).
- **Behavior:** Automatically partitions large requests into uniform slices (e.g., 750 circuits $\rightarrow$ `[300, 300, 150]`).

### 5.5 Asynchronous Execution & Webhook Delivery
- **Mechanism:** `fastapi.BackgroundTasks` running `process_draw_background(...)`.
- **Flow:** When `webhook_url` is provided in request, the API immediately returns HTTP `202 Accepted` (`{"draw_id": draw_id, "status": "QUEUED"}`). The background worker persists the draw to SQLite, writes idempotency records, and delivers completed draw payload via HTTP POST with 10-second timeout.

### 5.6 Caching Policies (`@Cache` Equivalent)
1. **Frontend Request Caching:** `@st.cache_data(ttl=300, show_spinner=False)` in `frontend/ui/api.py:cached_get()` caches static metadata (`/v2/usecases` and `/v2/circuit`).
2. **Batch Validation Caching:** `backend/validation.py` persists results to `validation_cache.json` to prevent re-running 1,000 quantum circuits on standard page loads unless `refresh=True` is passed.

### 5.7 Database Concurrency & SQLite WAL Mode
- Both SQLite connections enable Write-Ahead Logging (WAL):
  ```sql
  PRAGMA journal_mode=WAL;
  PRAGMA synchronous=NORMAL;
  PRAGMA foreign_keys=ON;
  ```
- Ensures non-blocking concurrent reads and serialized atomic writes under high multi-threaded load.

---

## 6. External Integrations, APIs, & Persistence Layers

| Integration Target | Type | Module / Config | Purpose |
|---|---|---|---|
| **SQLAlchemy ORM (SQLite)** | Database | `backend/ledger/audit_db.py` (`ledger.db`) | Stores draws, idempotency mappings, and API request logs with WAL concurrency |
| **SQLite Hash-Chain Engine** | Database | `backend/ledger/chain_ledger.py` (`chain_ledger.db`) | Append-only hash chain linking every draw record to the preceding block hash |
| **Qiskit Aer Simulator** | Quantum Engine | `backend/quantum/chsh_analysis.py`, `chsh_engine.py` | Local quantum statevector & measurement simulator executing Bell state circuits |
| **IBM Quantum Hardware Audit** | External Metadata | `ibm_job_id` tracking in `audit_db.py` | Tracks physical hardware execution job references (`ibm-q-job-xxxxxxxx`) |
| **External Webhooks** | Outbound HTTP | `requests.post(webhook_url, json=...)` in `backend/main.py` | Delivers completed quantum draw receipts asynchronously to tenant backends |
| **Streamlit Frontend** | Client UI | `frontend/ui/api.py` targeting `http://127.0.0.1:8000` | Multi-page glassmorphic interface consuming both core and `/v2` endpoints |

---

## 7. Cryptographic Algorithms & Integrity Formulas

### 7.1 CHSH Inequality Formulation
For measurement settings $A_0 = 0$, $A_1 = \pi/2$, $B_0 = \pi/4$, $B_1 = -\pi/4$:
$$S = E(A_0, B_0) + E(A_0, B_1) + E(A_1, B_0) - E(A_1, B_1)$$
Where correlation expectation is evaluated from coincidences:
$$E(a, b) = \frac{N_{00} + N_{11} - N_{01} - N_{10}}{N_{00} + N_{11} + N_{01} + N_{10}}$$
With variance propagation:
$$\sigma_E = \sqrt{\frac{1 - E^2}{N}}, \quad \sigma_S = \sqrt{\sum \sigma_{E_i}^2}$$
Certification Rule:
$$\text{Status} = \begin{cases} \text{CERTIFIED}, & S - 3\sigma_S > 2.0 \\ \text{BLOCKED}, & S - 3\sigma_S \le 2.0 \end{cases}$$

### 7.2 Draw Hash Chaining
For draw record $i$, receipt hash $H_i$ is computed as:
$$H_i = \text{SHA-256}\Big(\text{draw\_id} : \text{event} : \text{ts} : S : \text{status} : \text{json(winners)} : H_{i-1}\Big)$$
Where $H_0 = \text{"GENESIS"}$ or $64\text{ zeroes}$.

### 7.3 Binary Merkle Root
Given chronological list of receipt hashes $[H_1, H_2, \dots, H_n]$:
1. If length is odd, duplicate final hash.
2. Pairwise concatenate adjacent elements: $H_{parent} = \text{SHA-256}(H_{2k-1} \parallel H_{2k})$.
3. Recursively repeat until single 64-character Merkle root remains.

---

## 8. Summary of Changes & Retired Features

- **Removed Single-Purpose Schema:** Replaced raw SQL strings with SQLAlchemy ORM models (`Draw`, `IdempotencyRecord`, `ApiUsageLog`) featuring WAL journaling.
- **Removed Unauthenticated Endpoints:** Protected draw operations with constant-time API key guards and sliding-window rate limiters.
- **Removed Blocking Synchronous Draw Requirement:** Added asynchronous execution with HTTP 202 Accepted and webhook delivery.
- **Added Enterprise Concurrency Hardening:** Integrated thread locks (`_rate_limit_lock`, `_draw_lock`) preventing race conditions during burst traffic.
- **Replaced 3-Tab Monolith UI:** Modernized into Streamlit 1.46+ top-navigation multi-page app with distinct views for Live Draws, Chain Auditing, Validation, and Insider Attack demonstrations.
- **Verified Enterprise Stress Testing:** Validated with 4-phase stress test suite confirming 100% compliance across rate limits, idempotency bombardment, webhook batching, and Merkle tree calculations.
