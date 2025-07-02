"""Micro-benchmark: compare a `@typecheck()` decorated sieve vs a plain sieve.

This measures wall-clock time with `time.perf_counter_ns()`; rdtsc requires
native code so we use a portable high-resolution timer instead.
"""

import math
import statistics
from time import perf_counter_ns
from typing import List

from typecheck import typecheck


def _measure(func, iterations: int) -> int:
    start = perf_counter_ns()
    for i in range(iterations):
        func(i)
    end = perf_counter_ns()
    return end - start


@typecheck()
def sieve_decorated(_i: int) -> List[int]:
    """Return list of primes up to 100 using the Sieve of Eratosthenes."""
    n = 100
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0:2] = [False, False]
    p = 2
    while p * p <= n:
        if sieve[p]:
            for multiple in range(p * p, n + 1, p):
                sieve[multiple] = False
        p += 1
    return [i for i, is_prime in enumerate(sieve) if is_prime]


def sieve_plain(_i: int) -> List[int]:
    """Plain (undecorated) version of the sieve for comparison."""
    n = 100
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0:2] = [False, False]
    p = 2
    while p * p <= n:
        if sieve[p]:
            for multiple in range(p * p, n + 1, p):
                sieve[multiple] = False
        p += 1
    return [i for i, is_prime in enumerate(sieve) if is_prime]


def test_benchmark_sieve_decorated_vs_plain():
    iterations = 500
    warmup_rounds = 3
    measured_rounds = 100

    # Warmup: exercise caches and similar startup costs
    for _ in range(warmup_rounds):
        _measure(sieve_decorated, iterations)
        _measure(sieve_plain, iterations)

    # Run measured rounds and collect results silently
    decorated_ms = []
    plain_ms = []
    overhead_ms = []
    for _ in range(measured_rounds):
        dec_ns = _measure(sieve_decorated, iterations)
        plain_ns = _measure(sieve_plain, iterations)
        dec_m = dec_ns / 1_000_000
        pl_m = plain_ns / 1_000_000
        decorated_ms.append(dec_m)
        plain_ms.append(pl_m)
        overhead_ms.append(dec_m - pl_m)

    def _percentile(data, pct: float) -> float:
        """Return the percentile value using linear interpolation."""
        if not data:
            return 0.0
        data_sorted = sorted(data)
        k = (len(data_sorted) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data_sorted[int(k)]
        d0 = data_sorted[int(f)] * (c - k)
        d1 = data_sorted[int(c)] * (k - f)
        return d0 + d1

    median_dec = statistics.median(decorated_ms)
    median_plain = statistics.median(plain_ms)
    p95_dec = _percentile(decorated_ms, 95.0)
    p95_plain = _percentile(plain_ms, 95.0)
    median_overhead = statistics.median(overhead_ms)
    p95_overhead = _percentile(overhead_ms, 95.0)

    # Print summary after all measured rounds complete
    print("\nBenchmark percentiles (ms):")
    print(f"iterations: {iterations}, warmups: {warmup_rounds}, rounds: {measured_rounds}")
    print(f"decorated median: {median_dec:.3f} ms, 95%: {p95_dec:.3f} ms")
    print(f"plain     median: {median_plain:.3f} ms, 95%: {p95_plain:.3f} ms")
    print(f"overhead  median: {median_overhead:.3f} ms, 95%: {p95_overhead:.3f} ms")

    print("benchmark complete")


if __name__ == "__main__":
    test_benchmark_sieve_decorated_vs_plain()
