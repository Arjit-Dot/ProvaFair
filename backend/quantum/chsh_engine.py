import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
import random

simulator = AerSimulator()

def create_bell_pair() -> QuantumCircuit:
    """
    Creates a 2-qubit quantum circuit and entangles them into 
    the Bell state |Phi+> = (|00> + |11>) / sqrt(2).
    """
    # Create a circuit with 2 quantum bits (qubits) and 2 classical bits (for measurement)
    qc = QuantumCircuit(2, 2)
    
    # Apply Hadamard (H) gate to qubit 0 to put it in a 50/50 superposition
    qc.h(0)
    
    # Apply Controlled-NOT (CX) gate to entangle qubit 1 with qubit 0
    qc.cx(0, 1)
    
    return qc


def measure_chsh_setting(a_angle: float, b_angle: float, shots: int = 1000) -> float:
    """
    Applies rotations to Alice's and Bob's qubits, measures them, 
    and calculates the correlation score (Expectation Value).
    """
    # 1. Get a fresh entangled Bell pair
    qc = create_bell_pair()
    
    # 2. Rotate Alice's qubit (qubit 0) by a_angle using the Ry (Y-axis rotation) gate
    if a_angle != 0.0:
        qc.ry(a_angle, 0)
        
    # 3. Rotate Bob's qubit (qubit 1) by b_angle
    if b_angle != 0.0:
        qc.ry(b_angle, 1)
        
    # 4. Measure both qubits
    qc.measure([0, 1], [0, 1])
    
    # 5. Run the simulation
    result = simulator.run(qc, shots=shots).result()
    counts = result.get_counts()
    
    # 6. Extract the counts (default to 0 if a specific combination didn't occur)
    n00 = counts.get('00', 0)
    n11 = counts.get('11', 0)
    n01 = counts.get('01', 0)
    n10 = counts.get('10', 0)
    
    total = n00 + n11 + n01 + n10
    
    # 7. Calculate correlation E(a, b)
    # Matches (00, 11) pull the score toward +1
    # Mismatches (01, 10) pull the score toward -1
    expectation_value = (n00 + n11 - n01 - n10) / total
    
    return expectation_value

def run_chsh_test(shots_per_basis: int = 1000) -> dict:
    """
    Runs the 4 CHSH measurement configurations:
    Alice angles: A0 = 0, A1 = pi/2
    Bob angles:   B0 = pi/4, B1 = 3*pi/4
    Calculates S = |E(A0, B0) - E(A0, B1) + E(A1, B0) + E(A1, B1)|
    """
    # 1. Define the optimal measurement angles (in radians)
    a0 = 0.0
    a1 = np.pi / 2
    
    b0 = np.pi / 4
    b1 = 3 * np.pi / 4

    # 2. Run the 4 different "interrogation" scenarios
    e_a0_b0 = measure_chsh_setting(a0, b0, shots_per_basis)
    e_a0_b1 = measure_chsh_setting(a0, b1, shots_per_basis)
    e_a1_b0 = measure_chsh_setting(a1, b0, shots_per_basis)
    e_a1_b1 = measure_chsh_setting(a1, b1, shots_per_basis)

    # 3. Apply the CHSH formula 
    # Notice the minus sign on the second term! That is the mathematical key.
    s_score = abs(e_a0_b0 - e_a0_b1 + e_a1_b0 + e_a1_b1)

    # 4. Package the results for our FastAPI backend to consume
    return {
        "s_score": round(float(s_score), 3),
        "is_quantum": bool(s_score > 2.0),
        "correlations": {
            "E(A0, B0)": round(e_a0_b0, 3),
            "E(A0, B1)": round(e_a0_b1, 3),
            "E(A1, B0)": round(e_a1_b0, 3),
            "E(A1, B1)": round(e_a1_b1, 3)
        }
    }

def extract_quantum_random_numbers(num_winners: int, pool_size: int = 100) -> list[int]:
    """
    Measures pure entangled Bell pairs to generate a raw stream of quantum bits,
    and mathematically extracts the specified number of unique winners.
    """
    # 1. Create a fresh Bell pair and measure it immediately (no rotations)
    qc = create_bell_pair()
    qc.measure([0, 1], [0, 1])
    
    # 2. Run 1024 shots with memory=True to capture the exact sequence of 1s and 0s
    result = simulator.run(qc, shots=1024, memory=True).result()
    raw_measurements = result.get_memory() 
    # Example output: ['00', '11', '00', '11', '11', ...]
    
    # 3. Mash all 1024 measurements together into one giant binary string
    giant_binary_string = "".join(raw_measurements)
    
    # 4. Convert that massive binary string into an infinitely large integer
    quantum_seed = int(giant_binary_string, 2)
    
    # 5. Extract the winners (Crypto Extractor / Sampler)
    # We feed our pure quantum entropy into a sampler to fairly pick from the pool size
    prng = random.Random(quantum_seed)
    
    # Pick 'num_winners' (e.g., 4) from the pool (e.g., 1 to 100) without duplicates
    winners = prng.sample(range(1, pool_size + 1), num_winners)
    
    return sorted(winners)


if __name__ == "__main__":
    print("1. Running CHSH Bell Test for Verification...")
    cert = run_chsh_test()
    print(f"   Score: {cert['s_score']} (Valid: {cert['is_quantum']})")
    
    print("\n2. Extracting Quantum Winners...")
    # Let's draw 4 winners from a pool of 100 people
    winning_numbers = extract_quantum_random_numbers(num_winners=4, pool_size=100)
    print(f"   The winning IDs are: {winning_numbers}")