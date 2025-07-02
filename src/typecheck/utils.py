"""Utility constants and helper functions shared across the typecheck package."""

from typing import Any

DEFAULT_SAMPLE_SIZE = 5


def format_type(t: Any) -> str:
    try:
        s = str(t)
        if s.startswith("typing."):
            return s[len("typing.") :]
        return s
    except Exception:
        return getattr(t, "__name__", repr(t))
