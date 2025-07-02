from __future__ import annotations

import functools
import inspect
import os
import sys
from collections import deque
from typing import get_args, get_origin, get_type_hints

__all__ = [
    "typecheck",
    "TypeCheckError",
    "register_validator",
    "config",
    "reset_typevar_context",
]


class TypeCheckError(Exception):
    """Exception raised when type checking fails."""

    pass


# Public API: config imported late to minimize circular import risk
try:
    from .config import config  # type: ignore
except Exception:  # pragma: no cover - fallback during partial initialization
    config = None  # type: ignore


# Internal weak LRU cache implementation avoids keeping strong refs to instances.
# Imported after defining TypeCheckError to avoid circular import issues with modules
# that import TypeCheckError during their import phase. E402 suppressed intentionally.
from . import weak_lru  # noqa: E402
from .error_utils import container_mismatch, mismatch, return_mismatch  # noqa: E402
from .type_validators import iter_type_validators, reset_typevar_context  # noqa: E402
from .utils import format_type  # noqa: E402
from .validators import (  # noqa: E402
    ORIGIN_VALIDATORS,
    get_custom_validator,
    register_validator,
)


# Caches (use weak_lru to reduce risk of memory leaks from long-lived caches)
@weak_lru.lru_cache(maxsize=1024)
def _cached_get_type_hints(func):
    """Return resolved type hints for a function, cached by function object."""
    try:
        return get_type_hints(func)
    except NameError:
        # Forward reference unresolved at decoration time; return raw annotations.
        return getattr(func, "__annotations__", {}) or {}


@weak_lru.lru_cache(maxsize=4096)
def _cached_origin_args(type_hint):
    """Return (origin, args) for a type hint; cached to avoid repeated parsing."""
    return (get_origin(type_hint), get_args(type_hint))


_UNSET = object()


def typecheck(
    strict: bool | object = _UNSET,
    strict_return: bool | object = _UNSET,
    sample: int | None | object = _UNSET,
    deep: bool | object = _UNSET,
    *,
    ignore: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
):
    """
    A decorator that performs runtime type checking on function/method arguments and return values.

    Args:
        strict (bool): If True, raises error when arguments lack type annotations.
                      If False, ignores arguments without type hints.
        sample (int|None): If set, overrides the module default sampling size used when
            inspecting collection/iterable elements. Use a small number for faster checks.
            If None, the module-level DEFAULT_SAMPLE_SIZE is used.
        deep (bool): If True, disable sampling and traverse entire collections/iterables
            for exhaustive checking. This may be expensive for large inputs.

    Can be applied to:
    - Functions
    - Methods
    - Classes (applies to all methods in the class)

    Features:
    - Validates function arguments against their type annotations
    - Validates return values against return type annotations
    - Supports complex types like List[int], Dict[str, float], Union, Optional, etc.
    - Supports custom classes and instances
    - Performance optimized for large collections (samples first few elements)

    Usage:
        @typecheck()
        def my_function(x: int, y: str) -> str:
            return f"{x}-{y}"

        @typecheck(strict=True)
        class MyClass:
            def method(self, value: float) -> int:
                return int(value)
    """

    # Basic runtime disable: if the environment variable TYPECHECK_DISABLED is set
    # to a truthy value (1, true, yes, on), return a no-op decorator that leaves
    # the target untouched. This provides a quick way to disable runtime checks
    # for production or benchmarking.
    disabled_val = os.getenv("TYPECHECK_DISABLED", "").lower()
    if disabled_val in ("1", "true", "yes", "on"):
        # Return a no-op decorator
        def _noop_decorator(target):
            return target

        return _noop_decorator

    # Apply global config defaults where arguments not explicitly provided
    if strict is _UNSET and config is not None:  # type: ignore[truthy-function]
        strict = config.strict_mode  # type: ignore[attr-defined]
    if strict_return is _UNSET and config is not None:
        strict_return = config.strict_return_mode  # type: ignore[attr-defined]
    if sample is _UNSET and config is not None:
        sample = config.sample_size  # type: ignore[attr-defined]
    if deep is _UNSET and config is not None:
        deep = config.deep_checking  # type: ignore[attr-defined]

    # Normalize sentinel/default values for static type checkers
    strict = False if strict is _UNSET else bool(strict)  # type: ignore[assignment]
    strict_return = False if strict_return is _UNSET else bool(strict_return)  # type: ignore[assignment]
    deep = False if deep is _UNSET else bool(deep)  # type: ignore[assignment]
    if sample is _UNSET:
        sample = None  # type: ignore[assignment]
    elif sample is not None:
        if isinstance(sample, int):
            # already correct type
            pass
        else:  # fall back to disabling sampling if not int-like
            sample = None  # type: ignore[assignment]

    def decorator(target):
        # Ignore flag short-circuits (acts as opt-out marker)
        if ignore:
            # Attach marker so class-level decoration can detect and skip
            setattr(target, "__typecheck_ignored__", True)
            return target
        if inspect.isclass(target):
            return _decorate_class(
                target,
                strict,
                strict_return,
                sample,
                deep,
                include=include,
                exclude=exclude,
            )
        return _decorate_function(target, strict, strict_return, sample, deep)

    return decorator


def _decorate_class(
    cls,
    strict: bool,
    strict_return: bool,
    sample: int | None,
    deep: bool,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
):
    """Apply type checking to selected methods in a class.

    Selection rules:
      - If include list provided: only those names (plus __init__/__call__) are wrapped.
      - Else: all public (non-leading underscore) plus __init__/__call__ considered.
      - Exclude list removes methods from consideration.
      - Methods marked with attribute __typecheck_ignored__ are skipped.
    """
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        # Inclusion filtering
        essential = name in ("__init__", "__call__")
        if include is not None:
            if not (name in include or essential):
                continue
        else:
            if name.startswith("_") and not essential:
                continue
        if exclude and name in exclude:
            continue
        if getattr(method, "__typecheck_ignored__", False):
            continue
        original_attr = cls.__dict__.get(name)
        dec_func = _decorate_function(method, strict, strict_return, sample, deep)
        if isinstance(original_attr, staticmethod):
            setattr(cls, name, staticmethod(dec_func))
        elif isinstance(original_attr, classmethod):
            setattr(cls, name, classmethod(dec_func))
        else:
            setattr(cls, name, dec_func)
    return cls


def _decorate_function(func, strict: bool, strict_return: bool, sample: int | None, deep: bool):
    """Apply type checking to a single function/method."""
    # Cache signature and resolved type hints at decoration time to avoid
    # recomputing them on every call. This significantly reduces overhead for
    # hot functions.
    sig = inspect.signature(func)
    type_hints = _cached_get_type_hints(func)

    # Detect coroutine (async def) early so we can return an async wrapper.
    is_async = inspect.iscoroutinefunction(func)

    # Parameter names and method-bound detection can also be determined once.
    param_names = list(sig.parameters.keys())
    is_bound_method = hasattr(func, "__self__") or (
        len(param_names) > 0
        and param_names[0] in ("self", "cls")
        and "." in getattr(func, "__qualname__", "")
        and "<locals>" not in getattr(func, "__qualname__", "")
    )

    def _validate_arguments(*_args, **_kwargs):
        # Reset TypeVar context once per function call for consistent multi-parameter binding
        try:
            from .type_validators import (
                reset_typevar_context,  # local import to avoid cycle at module import
            )

            reset_typevar_context()
        except Exception:  # pragma: no cover
            pass
        try:
            bound_args = sig.bind(*_args, **_kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            raise TypeCheckError(f"Argument binding failed for {func.__name__}: {e}")

        for param_name, value in bound_args.arguments.items():
            if param_name in ("self", "cls") and is_bound_method and param_names and param_names[0] == param_name:
                continue
            if param_name not in type_hints:
                if strict:
                    raise TypeCheckError(
                        f"Parameter '{param_name}' in function '{func.__name__}' "
                        f"lacks type annotation (strict mode enabled)"
                    )
                continue
            expected_type = type_hints[param_name]
            if not _check_type(value, expected_type, param_name, func.__name__, sample_override=sample, deep=deep):
                raise mismatch(param_name, func.__name__, expected_type, value)

    def _validate_return(result):
        return_annotation = type_hints.get("return")
        # strict_return alone should enforce presence (no longer requires strict)
        if return_annotation is None and strict_return:
            raise TypeCheckError(
                f"Function '{func.__name__}' is missing a return type annotation (strict_return enabled)"
            )
        if return_annotation is not None:
            try:
                if not _check_type(
                    result, return_annotation, "return value", func.__name__, sample_override=sample, deep=deep
                ):
                    raise return_mismatch(func.__name__, return_annotation, result)
            except TypeCheckError as e:
                raise return_mismatch(func.__name__, return_annotation, result) from e
        return result

    if is_async:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            _validate_arguments(*args, **kwargs)
            result = await func(*args, **kwargs)
            return _validate_return(result)

        return async_wrapper
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _validate_arguments(*args, **kwargs)
            result = func(*args, **kwargs)
            return _validate_return(result)

        return wrapper


def _check_type(
    value, expected_type, param_name: str, func_name: str, sample_override: int | None = None, deep: bool = False
) -> bool:
    """
    Check if a value matches the expected type.
    Handles basic types, Union types, generic types, typing.List, typing.Dict,
    class instances, Any, Callable, Literal, and many other typing constructs.
    """

    # NOTE: Fallback behavior
    # -----------------------
    # This function currently takes a permissive stance for unknown or unsupported
    # typing constructs: when a specific construct isn't recognized, the function
    # typically returns True (accepts the value) rather than raising. This is a
    # deliberate compatibility/fallback decision to avoid surprising failures for
    # newer or exotic typing features. Future work (see Improvements.md item 15)
    # may introduce a stricter policy (raise or warn) behind a configuration flag
    # or decorator option. The README documents this behavior under "Type Support".

    # NOTE: TypeVar context reset now occurs once per function call in _validate_arguments
    # (and not per-parameter) to ensure consistent multi-argument binding; do not reset here.

    # Custom validator hook (only for concrete expected_type keys)
    custom_validator = get_custom_validator(expected_type)
    if custom_validator is not None:
        result = custom_validator(value, expected_type)
        return bool(result)

    # Iterate registered non-container validators first
    for predicate, handler in iter_type_validators():
        try:
            if predicate(expected_type):
                return handler(value, expected_type, param_name, func_name, _check_type, sample_override, deep)
        except TypeCheckError:
            raise
        except Exception as e:
            raise TypeCheckError(f"Validator error for {expected_type}: {e}") from e

    # Handle generic types (like List[int], Dict[str, int], typing.List[int], etc.)
    origin, type_args = _cached_origin_args(expected_type)
    if origin is not None:
        # Check the origin type (e.g., list for List[int] or typing.List[int])
        if not isinstance(value, origin):
            # Friendly container name for messages
            container_name = origin.__name__
            raise container_mismatch(param_name, func_name, expected_type, container_name, value)

        # Get type arguments for more detailed checking
        # type_args already retrieved above

        # Check List/list contents
        # Use centralized origin validator mapping if available
        validator = ORIGIN_VALIDATORS.get(origin)
        if validator:
            try:
                return validator(value, type_args, param_name, func_name, _check_type, sample_override, deep)
            except TypeCheckError:
                raise
            except Exception as e:
                raise TypeCheckError(
                    f"Validator failure for parameter '{param_name}' in function '{func_name}': {e}"
                ) from e
        # Fallback to generic success if origin unrecognized
        return True

    # Handle typing module types directly (for older Python versions or edge cases)
    if hasattr(expected_type, "__module__") and expected_type.__module__ == "typing":
        # Handle typing.List, typing.Dict, etc. that might not have proper origins
        type_name = getattr(expected_type, "_name", None) or str(expected_type)
        if "List" in type_name:
            return isinstance(value, list)
        elif "Dict" in type_name:
            return isinstance(value, dict)
        elif "Tuple" in type_name:
            return isinstance(value, tuple)
        elif "Set" in type_name:
            return isinstance(value, set)
        elif "FrozenSet" in type_name:
            return isinstance(value, frozenset)
        elif "Deque" in type_name:
            return isinstance(value, deque)
        elif "Callable" in type_name:
            return callable(value)
        elif "Any" in type_name:
            return True

    # Handle basic type checking for built-in types and classes
    if inspect.isclass(expected_type):
        return isinstance(value, expected_type)

    # Handle string type annotations (for forward references)
    if isinstance(expected_type, str):
        try:
            frame_globals = sys._getframe(1).f_globals  # pragma: no cover (best effort)
        except ValueError:  # stack not available
            frame_globals = {}
        resolved = frame_globals.get(expected_type, None)
        if resolved is None:
            # Apply forward ref policy
            policy = getattr(config, "forward_ref_policy", "permissive") if config else "permissive"
            if policy == "strict":
                raise TypeCheckError(
                    (
                        "Unresolved forward reference '"
                        f"{expected_type}' for parameter '{param_name}' "
                        f"in function '{func_name}'"
                    )
                )
            return True
        return _check_type(value, resolved, param_name, func_name, sample_override, deep)

    # Handle special cases for Python version compatibility
    if sys.version_info >= (3, 7):
        # Handle typing._GenericAlias and similar internal types
        if hasattr(expected_type, "__origin__"):
            origin = expected_type.__origin__
            if origin and isinstance(value, origin):
                return True

    # Unsupported construct fallback handling
    policy = getattr(config, "fallback_policy", "silent") if config else "silent"
    if policy == "error":
        raise TypeCheckError(
            f"Unsupported type construct {expected_type!r} for parameter '{param_name}' in function '{func_name}'"
        )
    elif policy == "warn":  # pragma: no cover (warnings are side-effects)
        try:
            import warnings

            warnings.warn(
                (
                    "typecheck: accepting unsupported type construct "
                    f"{expected_type!r} for '{param_name}' in {func_name}()"
                ),
                RuntimeWarning,
                stacklevel=2,
            )
        except Exception:
            pass
    return True


_format_type = format_type  # retained for any external references

# (Legacy internal predicate helpers removed; logic is now handled via
# registry-driven validators in `type_validators.py`.)
