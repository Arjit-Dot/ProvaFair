"""Bit stream -> unbiased winners, plus the predictable classical server."""
import random
import numpy as np


class ClassicalServer:
    """Seeded PRNG lottery server. Anyone who knows the seed can replay it."""

    def __init__(self, seed: int = 1337, bias: float = 0.5):
        self.seed, self.bias = seed, bias
        self.rng = random.Random(seed)

    def bits(self, n: int) -> np.ndarray:
        return np.array([1 if self.rng.random() < self.bias else 0 for _ in range(n)], dtype=np.uint8)

    def np_rng(self) -> np.random.Generator:
        return np.random.default_rng(self.rng.getrandbits(64))


def bits_to_winners(bits, pool_size: int, k: int):
    """Rejection sampling: no modulo bias, no duplicates."""
    k = min(k, pool_size)
    width = max(1, (pool_size - 1).bit_length())
    pos, out, seen = 0, [], set()
    while len(out) < k:
        if pos + width > len(bits):
            raise ValueError("Not enough entropy for this request. Reduce winners or pool size.")
        v = 0
        for b in bits[pos:pos + width]:
            v = (v << 1) | int(b)
        pos += width
        if v < pool_size and v not in seen:
            seen.add(v); out.append(v)
    return out
