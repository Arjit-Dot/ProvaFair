# ProvaFair: Quantum Design & Architecture Choices

This document explains the scientific and mathematical reasoning behind the core functions in `chsh_engine.py`. It bridges the gap between quantum physics principles and practical software engineering.

---

### 1. `create_bell_pair()`
**Goal:** Initialize the quantum state.

*   **Choice: The Hadamard Gate (`qc.h(0)`)**
    *   **Reason:** Standard classical bits are strictly 0 or 1. The Hadamard gate forces the first qubit into a perfect 50/50 superposition. This is the root source of true randomness in the universe—it guarantees the outcome cannot be known until measured.
*   **Choice: The CNOT Gate (`qc.cx(0, 1)`)**
    *   **Reason:** This creates **entanglement**. It logically links the second qubit to whatever the first qubit collapses into. Without the CNOT gate, the two qubits would act entirely independently. Independent qubits can only yield a maximum CHSH correlation score of 2.0 (the classical limit). Entanglement is strictly required to hit the 2.82 quantum score.

---

### 2. `measure_chsh_setting()`
**Goal:** Perform a single rotation and measure correlation.

*   **Choice: `Ry` Rotations (Y-axis)**
    *   **Reason:** To test for quantum entanglement, we must measure the qubits from different spatial perspectives (bases). Rotating along the Y-axis (`Ry`) is the most direct way to change the measurement angle in real space without introducing unnecessary complex numbers (phases) that occur with X or Z axis rotations.
*   **Choice: Expectation Value Formula `(n00 + n11 - n01 - n10) / total`**
    *   **Reason:** This is the standard statistical formula for mapping binary outcomes to a correlation spectrum. Matches (`00`, `11`) pull the score toward +1 (perfect correlation), while mismatches (`01`, `10`) pull it toward -1 (perfect anti-correlation). 

---

### 3. `run_chsh_test()`
**Goal:** Calculate the final physics grade.

*   **Choice: The Four Specific Angles ($0, \pi/2$ and $\pi/4, 3\pi/4$)**
    *   **Reason:** These are not arbitrary. In 1969, physicists Clauser, Horne, Shimony, and Holt proved that these exact rotational angles mathematically maximize the violation of local classical physics. Any other combination of angles will yield a score lower than 2.82, potentially failing the threshold and looking like a classical rigged machine.
*   **Choice: The Minus Sign in `abs(E1 - E2 + E3 + E4)`**
    *   **Reason:** The negative sign on the second term is the mathematical trick that exposes classical fraud. In classical physics, trying to maximize this equation creates a contradiction that physically limits the score to $\leq 2$. Quantum entanglement bypasses this contradiction, allowing the score to reach Tsirelson's bound ($2\sqrt{2} \approx 2.828$).

---

### 4. `extract_quantum_random_numbers()`
**Goal:** Generate fair, bias-free lottery numbers.

*   **Choice: `memory=True` in the Simulator**
    *   **Reason:** By default, quantum computers aggregate results to save memory (e.g., just returning "500 zeros, 500 ones"). `memory=True` forces the machine to return the exact chronological sequence of every single shot. We need this sequence because the *order* of the bits is our random data.
*   **Choice: 1024 Shots**
    *   **Reason:** Measuring 2 qubits 1,024 times yields exactly 2,048 bits of raw entropy. In modern cryptography, a 2048-bit key is the gold standard (used in RSA encryption). It creates a number so astronomically large that it is physically impossible for an attacker or insider to guess or brute-force.
*   **Choice: `"".join()` to create a PRNG Seed**
    *   **Reason:** We could try to convert raw binary directly to lottery numbers, but this creates **modulo bias** (if the applicant pool size isn't a perfect power of 2, some participants get a mathematically higher chance of winning). By joining all measurements into one massive 2048-bit integer and injecting it into a standard PRNG sampler, we guarantee perfectly flat, unbiased distribution across any pool size.