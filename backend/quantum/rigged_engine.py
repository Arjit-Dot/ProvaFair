import random

# The starting seed. A real server sets this once when it boots up.
GLOBAL_RIGGED_SEED = 1337

# We initialize the Generator ONCE. 
# This means every draw will advance the internal state and look completely random.
rigged_prng = random.Random(GLOBAL_RIGGED_SEED)

def run_rigged_test() -> dict:
    """
    Simulates a classical hardware device (Local Hidden Variable).
    According to Bell's Theorem, classical systems cannot exceed a CHSH score of 2.0.
    """
    fake_s_score = round(random.uniform(1.40, 1.95), 3)
    
    return {
        "s_score": fake_s_score,
        "is_quantum": False,
        "correlations": {
            "E(A0, B0)": round(fake_s_score / 4, 3), 
            "E(A0, B1)": round(fake_s_score / -4, 3),
            "E(A1, B0)": round(fake_s_score / 4, 3),
            "E(A1, B1)": round(fake_s_score / 4, 3)
        },
        "warning": "Deterministic classical ceiling hit (S <= 2.0). Potential seed rigging or classical device."
    }

def generate_rigged_numbers(num_winners: int, pool_size: int = 100) -> list[int]:
    """
    Produces deterministic numbers using the global stateful PRNG.
    To the public, these look perfectly random because they change every time.
    """
    # Uses the running PRNG state, NOT a fresh seed every time.
    winners = rigged_prng.sample(range(1, pool_size + 1), num_winners)
    return sorted(winners)

if __name__ == "__main__":
    print("--- THE PUBLIC LOTTERY DRAW ---")
    print("Running 3 draws. Because the PRNG is stateful, they all look completely different:")
    draw_1 = generate_rigged_numbers(4, 100)
    draw_2 = generate_rigged_numbers(4, 100)
    draw_3 = generate_rigged_numbers(4, 100)
    
    print(f"   Draw 1 IDs: {draw_1}")
    print(f"   Draw 2 IDs: {draw_2}")
    print(f"   Draw 3 IDs: {draw_3}")
    print("   (To the public, this looks like a perfectly fair lottery.)")

    print("\n--- THE HACKER'S LAPTOP ---")
    print(f"The hacker stole the boot seed ({GLOBAL_RIGGED_SEED}). Watch them predict the future:")
    
    # The hacker sets up their own generator at home with the stolen seed
    hacker_prng = random.Random(1337)
    
    hacker_pred_1 = sorted(hacker_prng.sample(range(1, 101), 4))
    hacker_pred_2 = sorted(hacker_prng.sample(range(1, 101), 4))
    hacker_pred_3 = sorted(hacker_prng.sample(range(1, 101), 4))
    
    print(f"   Hacker predicted Draw 1: {hacker_pred_1}")
    print(f"   Hacker predicted Draw 2: {hacker_pred_2}")
    print(f"   Hacker predicted Draw 3: {hacker_pred_3}")
    
    print("\n🚨 FRAUD DETECTED: The sequence was predetermined before the event even started!")