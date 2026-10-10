# ProvaFair: Backend Architecture & Core Modules

The ProvaFair backend is divided into two primary domains: the **Quantum Engine** (which handles the physics and number generation) and the **Ledger** (which handles immutable record-keeping).

Below is a breakdown of the critical folders and the functions that power them.

---

## 📂 1. `quantum/` (The Physics Engines)
This folder contains the logic for generating numbers. It houses both the true quantum generator and the classical "fraud" simulator used for the vulnerability demo.

### 📄 `chsh_engine.py` (The Production Quantum Server)
This file uses IBM's Qiskit to simulate a real quantum computer. It generates mathematically verifiable random numbers using quantum entanglement.

*   **`create_bell_pair(qc)`**
    *   **Purpose:** Initializes the quantum state. Applies a Hadamard gate and a CNOT gate to two qubits to entangle them. This entanglement is the root source of true, unpredictable randomness.
*   **`measure_chsh_setting(qc, theta_A, theta_B)`**
    *   **Purpose:** Measures the entangled qubits at specific physical angles. By rotating the measurement perspectives, it gathers data to prove the qubits are communicating non-locally.
*   **`run_chsh_test()`**
    *   **Purpose:** The ultimate lie detector test. It runs measurements at four specific angles and calculates the CHSH score. If the score is $> 2.0$, it mathematically guarantees no "seed" or hidden variable was used. 
*   **`extract_quantum_random_numbers(num_winners, pool_size)`**
    *   **Purpose:** Fires the quantum circuit 1,024 times, recording the exact sequence of qubit collapses. It safely transforms this raw quantum entropy into unbiased winning lottery IDs.

### 📄 `rigged_engine.py` (The Vulnerability Simulator)
This file mimics a standard, classical lottery server. It proves why standard hardware is vulnerable to insider attacks.

*   **`run_rigged_test()`**
    *   **Purpose:** Simulates a classical device trying to pass the Bell test. It restricts the CHSH score to a strict maximum of $2.0$ (the classical limit), intentionally failing the verification check.
*   **`generate_rigged_numbers(num_winners, pool_size)`**
    *   **Purpose:** Uses standard Python Pseudorandom Number Generation (PRNG) tied to a global boot seed (e.g., `1337`). It demonstrates that if an attacker knows this seed, they can perfectly recreate and predict all future lottery numbers.

---

## 📂 2. `ledger/` (The Immutable Database)
Once a draw is completed, the data must be locked away securely so it can be audited by the public later. This folder handles data persistence and cryptographic receipts.

### 📄 `audit_db.py` (The Tamper-Proof Storage)
This file manages a portable SQLite database (`ledger.db`) that acts as our public blockchain or record book.

*   **`init_db()`**
    *   **Purpose:** Runs when the server starts. It creates the `draws` table if it doesn't already exist, establishing columns for the Draw ID, physics score, status, winners, and timestamps.
*   **`record_draw(draw_id, event_name, chsh_score, status, winners)`**
    *   **Purpose:** The save mechanism. It takes all the data from a completed draw, packages it together, and hashes it using **SHA-256**. This creates a unique, permanent cryptographic receipt. It then saves everything to the SQLite database.
*   **`get_draw(draw_id)`**
    *   **Purpose:** The public audit function. It accepts a specific Draw ID from a user and fetches the exact history of that draw from the database, allowing anyone to verify the physics score and the winning numbers.