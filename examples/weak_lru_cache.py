"""Minimal Fibonacci performance comparison with and without weak_lru caching.

Does repeated timed single-call comparisons after a warmup phase.
"""

from time import perf_counter
from typecheck import weak_lru


def fib_plain(n: int) -> int:  # naive exponential recursion
    if n < 2:
        return n
    return fib_plain(n - 1) + fib_plain(n - 2)


@weak_lru.lru_cache(maxsize=256)
def fib_cached(n: int) -> int:
    if n < 2:
        return n
    return fib_cached(n - 1) + fib_cached(n - 2)


def time_ms(fn, *args):
    t0 = perf_counter()
    val = fn(*args)
    return val, (perf_counter() - t0) * 1000


def one_run(n: int):
    # Plain (no cache)
    v_plain, plain_ms = time_ms(fib_plain, n)
    # Cached cold then hot
    fib_cached.cache_clear()  # type: ignore[attr-defined]
    _, cached_cold_ms = time_ms(fib_cached, n)
    _, cached_hot_ms = time_ms(fib_cached, n)
    speedup = plain_ms / cached_hot_ms if cached_hot_ms else float("inf")
    return v_plain, plain_ms, cached_cold_ms, cached_hot_ms, speedup, fib_cached.cache_info()  # type: ignore[attr-defined]


if __name__ == "__main__":
    N = 30
    WARMUP = 3
    RUNS = 3

    for _ in range(WARMUP):
        one_run(N)  # warm cache & JIT-like effects

    results = [one_run(N) for _ in range(RUNS)]

    print(f"Fibonacci weak_lru benchmark n={N} (warmup {WARMUP}, measured {RUNS})")
    print("run | plain_ms  cached_cold_ms  cached_hot_ms  speedup  hits/misses size")
    print("-" * 72)
    for i, (val, plain_ms, cold_ms, hot_ms, speed, info) in enumerate(results, 1):
        print(
            f"{i:>3} | {plain_ms:9.2f}  {cold_ms:14.2f}  {hot_ms:13.2f}  {speed:7.1f}x  "
            f"{info.hits}/{info.misses} {info.currsize}/{info.maxsize}"
        )

    # Averages
    def avg(idx):
        return sum(r[idx] for r in results) / RUNS

    avg_speed = sum(r[4] for r in results) / RUNS
    print("-" * 72)
    print(
        f"avg plain={avg(1):.2f} ms cached_hot={avg(3):.2f} ms speedup={avg_speed:.1f}x"
    )
