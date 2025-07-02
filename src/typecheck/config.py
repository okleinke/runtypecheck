"""Global configuration for the typecheck package.

Users can tweak defaults instead of supplying decorator arguments repeatedly.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Dict, Type

from . import utils  # to keep DEFAULT_SAMPLE_SIZE in sync


@dataclass
class TypeCheckConfig:
    sample_size: int = 5
    strict_mode: bool = False
    deep_checking: bool = False
    strict_return_mode: bool = False
    lazy_iterable_validation: bool = True  # if True, wrap iterables with validating iterator
    fallback_policy: str = "silent"  # silent | warn | error for unsupported constructs
    forward_ref_policy: str = "permissive"  # permissive | strict (error if unresolved)
    _lock: RLock = RLock()

    @property
    def custom_validators(self) -> Dict[Type, Callable]:
        # Local import to avoid circular dependency at module import time
        try:
            from . import validators  # type: ignore

            return validators._custom_validators  # type: ignore[attr-defined]
        except Exception:
            # On very early import edge cases return empty mapping
            return {}

    def set_sample_size(self, n: int) -> None:
        if n <= 0:
            raise ValueError("sample_size must be positive")
        with self._lock:
            self.sample_size = n
            utils.DEFAULT_SAMPLE_SIZE = n

    def set_fallback_policy(self, policy: str) -> None:
        if policy not in ("silent", "warn", "error"):
            raise ValueError("fallback_policy must be one of: silent, warn, error")
        with self._lock:
            self.fallback_policy = policy

    def set_forward_ref_policy(self, policy: str) -> None:
        if policy not in ("permissive", "strict"):
            raise ValueError("forward_ref_policy must be one of: permissive, strict")
        with self._lock:
            self.forward_ref_policy = policy

    def reset(self) -> None:
        with self._lock:
            self.sample_size = 5
            self.strict_mode = False
            self.deep_checking = False
            self.strict_return_mode = False
            self.lazy_iterable_validation = True
            self.fallback_policy = "silent"
            self.forward_ref_policy = "permissive"
            utils.DEFAULT_SAMPLE_SIZE = 5


config = TypeCheckConfig()

__all__ = ["config", "TypeCheckConfig"]
