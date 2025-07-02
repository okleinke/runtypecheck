"""Weak-reference-aware LRU cache decorator.

Provides the familiar ``functools.lru_cache`` surface (``maxsize``, ``typed``,
``cache_info()``, ``cache_clear()``) while avoiding memory leaks for bound
methods by storing per-instance caches in a ``WeakKeyDictionary``. When an
instance is garbage collected its cache entries disappear automatically.

Differences from ``functools.lru_cache``:
* Unhashable call arguments are executed without caching instead of raising ``TypeError``.
* Per-instance sharding for methods (identified heuristically) instead of a single shared cache.
"""

import inspect
import threading
import warnings
import weakref
from collections import OrderedDict, namedtuple
from typing import Any
from typing import Callable as TypingCallable
from typing import Optional, Protocol, TypeVar

CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

# Stable sentinel separating positional args tuple from kwargs items in a key
_KW_MARKER = object()


def _make_key(args, kwargs, typed: bool):
    """Return a hashable cache key; raise ``TypeError`` if any part is unhashable."""
    key = args
    if kwargs:
        # Use a tuple of sorted items to make kwargs order-independent with stable marker
        items = tuple(sorted(kwargs.items()))
        key = key + (_KW_MARKER,) + items
    if typed:
        types = tuple(type(v) for v in args)
        if kwargs:
            types += tuple(type(v) for _, v in sorted(kwargs.items()))
        key = (key, types)
    # Ensure key is hashable
    hash(key)
    return key


def lru_cache(maxsize: Optional[int] = 128, typed: bool = False):
    """LRU cache decorator with weak per-instance caching for methods.

    Plain functions share one cache. Methods (heuristically detected) receive
    a distinct cache per instance stored weakly so they do not keep instances alive.
    """

    F = TypeVar("F", bound=TypingCallable[..., Any])

    class LRUWrapper(Protocol):  # minimal protocol for wrapper attributes
        cache_info: TypingCallable[[], CacheInfo]
        cache_clear: TypingCallable[[], None]
        __wrapped__: TypingCallable[..., Any]

        def __call__(self, *args: Any, **kwargs: Any) -> Any: ...  # pragma: no cover

    def decorating_function(user_function: F) -> LRUWrapper:  # type: ignore[name-defined]
        # Warn on unbounded cache usage (mirrors functools accept but emits a hint).
        if maxsize is None:
            warnings.warn(
                "weak_lru.lru_cache called with maxsize=None (unbounded); memory may grow without bound.",
                ResourceWarning,
                stacklevel=2,
            )  # pragma: no cover
        sig = inspect.signature(user_function)
        param_names = list(sig.parameters.keys())
        qualname = getattr(user_function, "__qualname__", "")
        # Method detection: try resolving containing class from qualname; fall back for <locals>.
        is_bound_method = False
        if "." in qualname:
            parts = qualname.split(".")
            module = inspect.getmodule(user_function)
            if module is not None:
                for i in range(len(parts) - 1):
                    cls_candidate = getattr(module, parts[i], None)
                    if isinstance(cls_candidate, type) and user_function.__name__ in getattr(
                        cls_candidate, "__dict__", {}
                    ):
                        is_bound_method = True
                        break
        if not is_bound_method and ("<locals>" in qualname and len(param_names) > 0):  # local class/function fallback
            is_bound_method = True

        # Global cache (plain functions)
        global_cache: OrderedDict[Any, Any] = OrderedDict()
        global_lock = threading.RLock()

        # Per-instance metadata: instance -> (cache OrderedDict, lock)
        instance_meta: "weakref.WeakKeyDictionary[Any, tuple[OrderedDict[Any, Any], threading.RLock]]" = (
            weakref.WeakKeyDictionary()
        )
        instance_meta_lock = threading.RLock()  # protects creation/removal in instance_meta

        # Shared statistics across all caches (shards + global)
        hits = 0
        misses = 0

        # No aggregate cap: each instance cache respects only its own maxsize.

        def cache_info():
            # Compose total current size across shards + global
            currsize = 0
            if is_bound_method:
                with instance_meta_lock:
                    for cache, _lk in instance_meta.values():  # pragma: no branch - simple iteration
                        currsize += len(cache)
            with global_lock:
                currsize += len(global_cache)
            return CacheInfo(hits, misses, maxsize, currsize)

        def cache_clear():
            nonlocal hits, misses
            with global_lock:
                global_cache.clear()
            with instance_meta_lock:
                # Clear each per-instance shard
                for cache, _lk in list(instance_meta.values()):
                    cache.clear()
            hits = misses = 0

        def wrapper(*args: Any, **kwargs: Any):
            nonlocal hits, misses
            use_instance = is_bound_method and len(args) > 0
            cache = None
            cache_lock: threading.RLock | None = None

            if use_instance:
                # First arg is instance (self/cls)
                instance = args[0]  # type: ignore[assignment]
                # Create or fetch per-instance cache + lock
                try:
                    with instance_meta_lock:
                        cache_tuple = instance_meta.get(instance)
                        if cache_tuple is None:
                            cache_tuple = (OrderedDict(), threading.RLock())
                            instance_meta[instance] = cache_tuple
                        cache, cache_lock = cache_tuple
                except TypeError:
                    # Instance not weak-referenceable -> fallback to global cache
                    use_instance = False

            if not use_instance:
                cache = global_cache
                cache_lock = global_lock

            # Exclude bound instance from key for per-instance caches
            key_args = args[1:] if use_instance else args
            try:
                key = _make_key(key_args, kwargs, typed)
            except TypeError:
                return user_function(*args, **kwargs)  # unhashable -> no caching

            # Lookup (move-to-MRU on hit)
            assert cache is not None and cache_lock is not None  # for type checkers
            with cache_lock:
                try:
                    result = cache.pop(key)
                    cache[key] = result  # move to MRU
                    hits += 1
                    return result
                except KeyError:
                    misses += 1

            # Miss: compute outside lock
            result = user_function(*args, **kwargs)

            # Insert & enforce per-cache maxsize (LRU eviction policy)
            with cache_lock:
                cache[key] = result
                if maxsize is not None and maxsize > 0:
                    while len(cache) > maxsize:
                        cache.popitem(last=False)
            return result

        # Attach public API attributes
        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        wrapper.__wrapped__ = user_function  # type: ignore[attr-defined]

        return wrapper  # type: ignore[return-value]

    # end decorating_function

    # Return the actual decorator
    return decorating_function
