"""Centralized error message helpers for typecheck.

Provides consistent type name formatting and message construction so that
all raised TypeCheckError instances follow the same style.
"""

from __future__ import annotations

from typing import Any

from . import TypeCheckError  # type: ignore
from .utils import format_type as _raw_format_type


def fmt_type(t: Any) -> str:
    """Return a human-friendly type representation.

    Wraps utils.format_type but normalizes builtins and removes angle-bracketed
    class wrappers (<class 'int'> -> int).
    """
    name = getattr(t, "__name__", None)
    if name:
        return name
    s = _raw_format_type(t)
    if s.startswith("<class '") and s.endswith("'>"):
        inner = s[len("<class '") : -2]
        return inner.split(".")[-1]
    return s


def mismatch(param: str, func: str, expected: Any, actual_value: Any) -> TypeCheckError:
    return TypeCheckError(
        (
            f"Type mismatch for parameter '{param}' in function '{func}': "
            f"expected {fmt_type(expected)}, got {type(actual_value).__name__} "
            f"({actual_value!r})"
        )
    )


def container_mismatch(param: str, func: str, expected: Any, container_name: str, actual_value: Any) -> TypeCheckError:
    return TypeCheckError(
        (
            f"Type mismatch for parameter '{param}' in function '{func}': "
            f"expected {fmt_type(expected)} ({container_name}), got "
            f"{type(actual_value).__name__} ({actual_value!r})"
        )
    )


def return_mismatch(func: str, expected: Any, actual_value: Any) -> TypeCheckError:
    return TypeCheckError(
        (
            f"Return value type mismatch in function '{func}': expected "
            f"{fmt_type(expected)}, got {type(actual_value).__name__} "
            f"({actual_value!r})"
        )
    )


__all__ = [
    "fmt_type",
    "mismatch",
    "container_mismatch",
    "return_mismatch",
]
