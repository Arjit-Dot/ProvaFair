"""Deterministic stream expanded from a certified seed (HMAC-SHA256), with unbiased integers."""
import hashlib
import hmac


class Stream:
    def __init__(self, seed: bytes, label: str):
        self.key = hmac.new(seed, label.encode(), hashlib.sha256).digest()
        self.ctr = 0

    def bytes(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            out += hmac.new(self.key, self.ctr.to_bytes(8, "big"), hashlib.sha256).digest()
            self.ctr += 1
        return out[:n]

    def randbelow(self, n: int) -> int:
        """Uniform in [0, n) by rejection sampling, so there is no modulo bias."""
        if n <= 0:
            raise ValueError("n must be positive")
        if n == 1:
            return 0
        k = (n - 1).bit_length()
        nbytes = (k + 7) // 8
        while True:
            x = int.from_bytes(self.bytes(nbytes), "big") >> (8 * nbytes - k)
            if x < n:
                return x


def shuffle(items, stream: Stream) -> list:
    """Fisher-Yates."""
    a = list(items)
    for i in range(len(a) - 1, 0, -1):
        j = stream.randbelow(i + 1)
        a[i], a[j] = a[j], a[i]
    return a


def sample(population_size: int, k: int, stream: Stream) -> list[int]:
    """k distinct indices from range(population_size), in draw order (partial Fisher-Yates)."""
    if not 0 <= k <= population_size:
        raise ValueError("k must be between 0 and the population size")
    pool = list(range(population_size)) if population_size <= 2_000_000 else None
    if pool is None:
        raise ValueError("population too large")
    for i in range(k):
        j = i + stream.randbelow(population_size - i)
        pool[i], pool[j] = pool[j], pool[i]
    return pool[:k]


def hkdf(ikm: bytes, info: bytes, length: int, salt: bytes = b"") -> bytes:
    """RFC 5869 HKDF-SHA256."""
    prk = hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]
