import threading
import time

# Use a TypeVar binding scenario across threads to ensure no leakage
from typing import TypeVar

from typecheck import typecheck

T = TypeVar("T")


@typecheck()
def echo_pair(a: T, b: T):
    return a, b


results = []


def worker(val1, val2, delay):
    time.sleep(delay)
    results.append(echo_pair(val1, val2))


def test_thread_local_typevar_context():
    # Launch threads with different types; permissive model allows mismatch but contexts must not collide
    threads = [
        threading.Thread(target=worker, args=(1, 2, 0.01)),
        threading.Thread(target=worker, args=("a", "b", 0.0)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Ensure both results captured without assertion errors or cross-thread crashes
    assert len(results) == 2
    assert (1, 2) in results and ("a", "b") in results
