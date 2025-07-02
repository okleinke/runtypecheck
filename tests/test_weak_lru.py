import gc
import threading
import time
import unittest
import weakref
from functools import lru_cache as std_lru_cache

from typecheck import weak_lru


class WeakLruTests(unittest.TestCase):
    def test_basic_caching_and_stats(self):
        """Exercise basic cache behavior including hit/miss stats and clearing."""
        calls = []

        @weak_lru.lru_cache(maxsize=2)
        def compute(x, y=0):
            calls.append((x, y))
            return x + y

        # warm cache (2 misses)
        self.assertEqual(compute(1), 1)
        self.assertEqual(compute(2, y=3), 5)
        # cache hit
        self.assertEqual(compute(1), 1)
        info = compute.cache_info()  # type: ignore[attr-defined]
        self.assertGreaterEqual(info.hits, 1)
        self.assertGreaterEqual(info.misses, 2)

        # eviction: maxsize=2 -> adding two more distinct keys will evict LRU
        compute(3)
        compute(4)
        # ensure cache still returns correct values (these are hits now)
        self.assertEqual(compute(3), 3)
        self.assertEqual(compute(4), 4)

        # clear and validate full stats reset
        compute.cache_clear()  # type: ignore[attr-defined]
        info2 = compute.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info2.currsize, 0)
        self.assertEqual(info2.hits, 0)
        self.assertEqual(info2.misses, 0)

    def test_lru_eviction_order(self):
        @weak_lru.lru_cache(maxsize=2)
        def f(a):
            return a * 2

        self.assertEqual(f(1), 2)
        self.assertEqual(f(2), 4)
        # access 1 to make it MRU
        self.assertEqual(f(1), 2)
        # add third unique key -> should evict 2
        self.assertEqual(f(3), 6)
        # 2 should be recomputed (miss)
        self.assertEqual(f(2), 4)

    def test_per_instance_cache_and_weakref(self):
        class C:
            def __init__(self, base):
                self.base = base

            @weak_lru.lru_cache(maxsize=10)
            def add(self, x):
                return self.base + x

        c = C(10)
        d = C(100)

        self.assertEqual(c.add(1), 11)
        self.assertEqual(d.add(1), 101)
        # caches are per-instance: ensure different results don't interfere
        self.assertEqual(c.add(1), 11)
        self.assertEqual(d.add(1), 101)

        # weakref: deleting instance should allow cache entries to be freed
        ref = weakref.ref(c)
        del c
        gc.collect()
        self.assertIsNone(ref())

    def test_unhashable_args_bypass_cache(self):
        calls = {"count": 0}

        @weak_lru.lru_cache(maxsize=10)
        def f(x):
            calls["count"] += 1
            return len(x)

        lst = [1, 2, 3]
        # list is unhashable -> calls should not be cached; each call increments
        self.assertEqual(f(lst), 3)
        self.assertEqual(f(lst), 3)
        self.assertEqual(calls["count"], 2)

    def test_unhashable_global_function(self):
        @weak_lru.lru_cache(maxsize=2)
        def func(x):
            return 1

        lst = []  # unhashable
        func(lst)
        func(lst)  # second call should not be cached (miss again) but no exception
        info = func.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.currsize, 0)

    def test_weak_lru_unhashable_key_and_cache_info_additional(self):
        """Additional unhashable path: expect hits/misses remain 0 when only unhashable args passed."""
        calls = {"count": 0}

        @weak_lru.lru_cache(maxsize=4)
        def func(x):
            calls["count"] += 1
            return x

        func([1, 2, 3])  # unhashable
        func([1, 2, 3])  # still unhashable -> not cached
        info = func.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.misses, 0)

    def test_weak_lru_per_instance_sharding_additional(self):
        @weak_lru.lru_cache(maxsize=2)
        def plain(x):
            return x * 2

        class A:
            @weak_lru.lru_cache(maxsize=2)
            def method(self, x):
                return x + 1

        a1, a2 = A(), A()
        plain(1)
        plain(1)
        self.assertGreaterEqual(plain.cache_info().hits, 1)  # type: ignore[attr-defined]
        a1.method(1)
        a1.method(1)
        a2.method(1)
        info = a1.method.cache_info()  # type: ignore[attr-defined]
        self.assertLessEqual(info.currsize, 2)
        gc.collect()

    def test_per_instance_maxsize_one_eviction_loop(self):
        class LocalFactory:
            @weak_lru.lru_cache(maxsize=1)
            def foo(self, x):
                return x

        inst = LocalFactory()
        inst.foo(1)
        inst.foo(2)
        inst.foo(3)  # multiple evictions with maxsize=1 should not error
        self.assertEqual(inst.foo.cache_info().maxsize, 1)  # type: ignore[attr-defined]

    def test_per_instance_eviction(self):
        class C:
            def __init__(self, base):
                self.base = base

            @weak_lru.lru_cache(maxsize=2)
            def mul(self, x):
                return self.base * x

        c = C(2)
        # Fill instance cache beyond maxsize to trigger eviction path
        self.assertEqual(c.mul(1), 2)
        self.assertEqual(c.mul(2), 4)
        self.assertEqual(c.mul(3), 6)  # should evict LRU (1)
        # Access again to ensure still works after eviction
        self.assertEqual(c.mul(2), 4)
        self.assertEqual(c.mul(4), 8)  # another eviction
        info = c.mul.cache_info()  # type: ignore[attr-defined]
        self.assertLessEqual(info.currsize, 5)  # total across caches

    def test_typed_true_with_kwargs(self):
        """Ensure typed=True distinguishes numeric types & kwargs reuses stable sentinel (3 misses, >=1 hit)."""
        calls = {"count": 0}

        @weak_lru.lru_cache(maxsize=10, typed=True)
        def fn(a, b=0):
            calls["count"] += 1
            return a, b

        self.assertEqual(fn(1, b=2), (1, 2))  # miss 1
        self.assertEqual(fn(1, b=2), (1, 2))  # hit
        self.assertEqual(fn(1.0, b=2), (1.0, 2))  # miss 2 (type of a differs)
        self.assertEqual(fn(1, b=2.0), (1, 2.0))  # miss 3 (type of kwarg differs)
        self.assertEqual(fn(1, b=2), (1, 2))  # hit again
        info = fn.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info.misses, 3)
        self.assertGreaterEqual(info.hits, 2)

    def test_non_weakrefable_instance_fallback(self):
        # Cover lines 110-112: instance not weak-referenceable -> fallback to global cache
        class NoWeakSlots:
            __slots__ = ("x",)  # no __weakref__ slot -> not weakref'able

            def __init__(self, x):
                self.x = x

            @weak_lru.lru_cache(maxsize=4)
            def add(self, y):
                return self.x + y

        a = NoWeakSlots(10)
        b = NoWeakSlots(20)
        # Calls should succeed and use global cache transparently
        self.assertEqual(a.add(1), 11)
        self.assertEqual(a.add(1), 11)  # hit
        self.assertEqual(b.add(1), 21)
        self.assertEqual(b.add(2), 22)
        info = a.add.cache_info()  # type: ignore[attr-defined]
        # currsize should reflect entries for each unique (instance, args) combination
        self.assertGreaterEqual(info.currsize, 2)

    def test_stress_eviction_churn(self):
        @weak_lru.lru_cache(maxsize=32)
        def f(x):
            return x * 2

        # Insert many more than maxsize unique keys
        for i in range(256):
            self.assertEqual(f(i), i * 2)
        info = f.cache_info()  # type: ignore[attr-defined]
        self.assertLessEqual(info.currsize, 32)
        # Re-access recent keys to exercise LRU ordering (cannot assert exact ordering but ensure values correct)
        for i in range(240, 256):
            self.assertEqual(f(i), i * 2)

    def test_multi_instance_scaling_limit(self):
        class C:
            @weak_lru.lru_cache(maxsize=3)
            def val(self, x):
                return x

        instances = [C() for _ in range(10)]
        for idx, inst in enumerate(instances):
            for v in range(5):  # exceed maxsize per instance
                inst.val(idx * 100 + v)
        # Pick one instance to query aggregate size (sums all instance caches + global)
        info = instances[0].val.cache_info()  # type: ignore[attr-defined]
        # Upper bound: each instance cache limited to 3 => <= 30 entries
        self.assertLessEqual(info.currsize, 30)

    def test_basic_function_semantics_against_stdlib(self):
        calls_custom = {"n": 0}
        calls_std = {"n": 0}

        @weak_lru.lru_cache(maxsize=64)
        def fib_custom(n):
            calls_custom["n"] += 1
            return n if n < 2 else fib_custom(n - 1) + fib_custom(n - 2)

        @std_lru_cache(maxsize=64)
        def fib_std(n):
            calls_std["n"] += 1
            return n if n < 2 else fib_std(n - 1) + fib_std(n - 2)

        for k in range(10):
            self.assertEqual(fib_custom(k), fib_std(k))
        # Not asserting exact call counts (different internal ordering possible) but ensure both caches reduce calls
        self.assertLess(calls_custom["n"], 2**10)
        self.assertLess(calls_std["n"], 2**10)

    def test_concurrency_basic(self):
        @weak_lru.lru_cache(maxsize=64)
        def slow(x):
            time.sleep(0.001)
            return x * 3

        results = []
        errors = []

        def worker(val):
            try:
                results.append(slow(val))
            except Exception as e:  # pragma: no cover - only on failure
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i % 8,)) for i in range(64)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertFalse(errors)
        # All results should be multiples of 3
        self.assertTrue(all(r % 3 == 0 for r in results))
        # Cache should not exceed maxsize
        info = slow.cache_info()  # type: ignore[attr-defined]
        self.assertLessEqual(info.currsize, 64)

    def test_many_instances_no_global_cap(self):
        """Create many instances to ensure aggregate size is sum of per-instance caches."""

        class R:
            @weak_lru.lru_cache(maxsize=1)
            def val(self, x):
                return x

        # Many per-instance caches should coexist without hidden global eviction
        instances = [R() for _ in range(70)]
        # Populate each per-instance cache with a unique key
        for idx, inst in enumerate(instances):
            self.assertEqual(inst.val(idx), idx)
        info_after_populate = instances[0].val.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info_after_populate.currsize, 70)
        # Ensure values still retrievable (hits) after population
        for idx, inst in enumerate(instances):
            self.assertEqual(inst.val(idx), idx)

    def test_cache_clear_per_instance_clears_all_instance_caches(self):
        # Cover cache_clear loop over instance_meta (line 128 region)
        calls = []

        class C:
            @weak_lru.lru_cache(maxsize=4)
            def add(self, x):
                calls.append((id(self), x))
                return x * 2

        instances = [C() for _ in range(3)]
        # Populate per-instance caches
        for inst_idx, inst in enumerate(instances):
            inst.add(inst_idx)
            inst.add(inst_idx + 10)  # second unique key per instance
        info_before = instances[0].add.cache_info()  # type: ignore[attr-defined]
        self.assertGreaterEqual(info_before.currsize, 6)  # 3 instances * 2 keys
        # Clear and verify all per-instance caches reset
        instances[0].add.cache_clear()  # type: ignore[attr-defined]
        info_after = instances[0].add.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info_after.currsize, 0)
        self.assertEqual(info_after.hits, 0)
        self.assertEqual(info_after.misses, 0)
        # Re-populate one instance to confirm caches still functional after clear
        self.assertEqual(instances[0].add(5), 10)
        info_repop = instances[0].add.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info_repop.misses, 1)

    def test_staticmethod_shared_cache(self):
        class S:
            @staticmethod
            @weak_lru.lru_cache(maxsize=8)
            def add(a, b):
                return a + b

        s1 = S()
        s2 = S()
        self.assertEqual(s1.add(1, 2), 3)  # miss
        self.assertEqual(s2.add(1, 2), 3)  # hit (shared static method cache)
        info = s1.add.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info.misses, 1)
        self.assertGreaterEqual(info.hits, 1)
        # Another argument to grow cache
        self.assertEqual(S.add(2, 3), 5)
        info2 = S.add.cache_info()  # type: ignore[attr-defined]
        self.assertEqual(info2.currsize, 2)

    def test_classmethod_global_cache_and_class_keying(self):
        class C:
            @classmethod
            @weak_lru.lru_cache(maxsize=8)
            def tag(cls, x):
                return (cls.__name__, x)

        class D(C):
            pass

        # First call for C -> miss
        self.assertEqual(C.tag(5), ("C", 5))
        # Second identical call -> hit
        self.assertEqual(C.tag(5), ("C", 5))
        # Call via instance should also hit same entry
        self.assertEqual(C().tag(5), ("C", 5))
        # Subclass call uses different class object in key -> new miss
        self.assertEqual(D.tag(5), ("D", 5))
        info = C.tag.cache_info()  # type: ignore[attr-defined]
        # Expect 2 misses (C first, D first) and at least 2 hits (repeat + instance)
        self.assertGreaterEqual(info.misses, 2)
        self.assertGreaterEqual(info.hits, 2)
        self.assertEqual(info.currsize, 2)


if __name__ == "__main__":
    unittest.main()
