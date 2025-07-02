"""Registry of type-level validators (non-container) for the typecheck package.

Each validator consists of a predicate and a handler:
- predicate(expected_type) -> bool  (decides if handler applies)
- handler(value, expected_type, param_name, func_name, recurse, sample_override, deep) -> bool
  The handler should raise TypeCheckError with a helpful message on failure, or
  return True/False (False triggers a generic mismatch message from caller if
  desired). Handlers are expected to raise for richer context.

The main _check_type function will iterate validators in registration order
until one matches.
"""

from __future__ import annotations

import inspect
import threading
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Final,
    Literal,
    NoReturn,
    Protocol,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

# Optional typing constructs (Python 3.11 additions kept conditional)
try:  # Python >=3.11
    from typing import Never  # type: ignore
except Exception:  # pragma: no cover
    Never = None  # type: ignore
try:  # Python >=3.11
    from typing import LiteralString  # type: ignore
except Exception:  # pragma: no cover
    LiteralString = None  # type: ignore

from . import TypeCheckError  # type: ignore  # circular-safe during runtime import
from .error_utils import fmt_type

# (format_type imported previously was unused; removed to satisfy linter)

RecurseFunc = Callable[[Any, Any, str, str, int | None, bool], bool]

ValidatorPredicate = Callable[[Any], bool]
ValidatorHandler = Callable[[Any, Any, str, str, RecurseFunc, int | None, bool], bool]

_type_validators: list[tuple[ValidatorPredicate, ValidatorHandler]] = []


def register_type_validator(predicate: ValidatorPredicate):
    def _decorator(handler: ValidatorHandler):
        _type_validators.append((predicate, handler))
        return handler

    return _decorator


def iter_type_validators():  # iterator for consumers
    return list(_type_validators)


# ------------------ Built-in validators -------------------------------------------------------


# Any
@register_type_validator(lambda t: t is Any or getattr(t, "_name", None) == "Any")
def _validate_any(value, expected_type, *_args):  # Always passes
    return True


# Optional / None handling is subsumed by Union validator; direct NoneType case
@register_type_validator(lambda t: t is type(None))
def _validate_none(value, expected_type, param_name, func_name, recurse, *_):
    return value is None


# Union (including Optional)
@register_type_validator(lambda t: get_origin(t) is Union or ("UnionType" in str(type(t))))
def _validate_union(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    mismatches = []
    for arg in get_args(expected_type):
        try:
            if recurse(value, arg, param_name, func_name, sample_override, deep):
                return True
        except TypeCheckError as e:  # collect richer mismatch context
            mismatches.append(str(e))
    # Deterministic failure
    expected_options = " | ".join([fmt_type(a) for a in get_args(expected_type)])
    raise TypeCheckError(
        "Type mismatch for parameter "
        f"'{param_name}' in function '{func_name}': value {value!r} (type {type(value).__name__}) "
        f"did not match any Union option ({expected_options})."
    )


# Literal
@register_type_validator(lambda t: get_origin(t) is Literal)
def _validate_literal(value, expected_type, *_):
    return value in get_args(expected_type)


# Callable (structural check)
@register_type_validator(
    lambda t: (
        (get_origin(t) is not None and getattr(get_origin(t), "__name__", None) == "Callable")
        or (hasattr(t, "__module__") and t.__module__ == "typing" and "Callable" in str(t))
    )
)
def _validate_callable(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    if not callable(value):
        return False
    args = get_args(expected_type)
    if not args:  # Callable without specification
        return True
    # Expected args: ([arg_types...], return_type)
    if len(args) != 2:
        return True  # malformed; permissive
    param_specs, return_spec = args
    if param_specs is Ellipsis:
        return True
    try:
        actual_hints = get_type_hints(value)
    except Exception:
        return True  # Can't introspect; permissive
    # Compare parameter count (positional-only simple heuristic)
    expected_arity = len(param_specs) if isinstance(param_specs, (list, tuple)) else 0
    # Use signature for actual arity
    import inspect

    try:
        sig = inspect.signature(value)
    except (ValueError, TypeError):  # builtins etc.
        return True
    actual_params = [p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if expected_arity and len(actual_params) != expected_arity:
        raise TypeCheckError(
            f"Type mismatch for parameter '{param_name}' in function '{func_name}': Callable arity mismatch; "
            f"expected {expected_arity}, got {len(actual_params)}"
        )

    # Structural parameter type comparison (lightweight): compare annotations positionally.
    # We only enforce if param specs are concrete (not Any) and function provides an annotation.
    def _compatible(actual_ann, expected_ann):
        if expected_ann is Any:
            return True
        if actual_ann is Any:
            return True
        if actual_ann is inspect._empty:  # unannotated implementation accepted
            return True
        if actual_ann is expected_ann:
            return True
        if inspect.isclass(actual_ann) and inspect.isclass(expected_ann):
            return issubclass(actual_ann, expected_ann)  # covariant-ish acceptance
        return False

    if isinstance(param_specs, (list, tuple)):
        for spec, param in zip(param_specs, actual_params):
            actual_ann = actual_hints.get(param.name, param.annotation)
            if not _compatible(actual_ann, spec):
                raise TypeCheckError(
                    (
                        f"Type mismatch for parameter '{param_name}' in function "
                        f"'{func_name}': Callable parameter type mismatch for arg "
                        f"'{param.name}'; expected {getattr(spec, '__name__', spec)}, "
                        f"got {getattr(actual_ann, '__name__', actual_ann)}"
                    )
                )
    # Return type structural comparison
    actual_return = actual_hints.get("return", inspect._empty)
    if return_spec is not Any and actual_return is not inspect._empty:
        if actual_return is not return_spec:
            if (
                inspect.isclass(actual_return)
                and inspect.isclass(return_spec)
                and issubclass(actual_return, return_spec)
            ):
                pass
            else:
                raise TypeCheckError(
                    (
                        f"Type mismatch for parameter '{param_name}' in function "
                        f"'{func_name}': Callable return type mismatch; expected "
                        f"{getattr(return_spec, '__name__', return_spec)}, got "
                        f"{getattr(actual_return, '__name__', actual_return)}"
                    )
                )
    return True


# Type[Cls]
@register_type_validator(lambda t: get_origin(t) is type)
def _validate_type_annotation(value, expected_type, param_name, func_name, recurse, *_):
    args = get_args(expected_type)
    if not inspect.isclass(value):
        raise TypeCheckError(
            (
                "Type mismatch for parameter "
                f"'{param_name}' in function '{func_name}': expected a class, "
                f"got {type(value).__name__}"
            )
        )
    if args:
        expected_cls = args[0]
        if not (
            value is expected_cls
            or (
                inspect.isclass(expected_cls)
                and inspect.isclass(value)
                and issubclass(value, expected_cls)  # type: ignore[arg-type]
            )
        ):
            raise TypeCheckError(
                (
                    "Type mismatch for parameter "
                    f"'{param_name}' in function '{func_name}': expected Type["
                    f"{expected_cls.__name__}], got {value.__name__}"
                )
            )
    return True


_typevar_state = threading.local()


def _get_ctx() -> dict[int, Any]:
    ctx = getattr(_typevar_state, "ctx", None)
    if ctx is None:
        ctx = {}
        _typevar_state.ctx = ctx
    return ctx


def reset_typevar_context():  # used per validation cycle
    _get_ctx().clear()


@register_type_validator(lambda t: isinstance(t, TypeVar))
def _validate_typevar(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    # Track by id of TypeVar to allow consistent binding within a single validation pass
    tv: TypeVar = expected_type  # type: ignore
    tv_id = id(tv)
    # Constraints
    constraints = getattr(tv, "__constraints__", ()) or ()
    bound = getattr(tv, "__bound__", None)
    # If previously bound in this call, enforce consistency
    _TYPEVAR_CONTEXT = _get_ctx()
    prior = _TYPEVAR_CONTEXT.get(tv_id, None)
    if prior is not None:
        prior_type = prior if isinstance(prior, type) else type(prior)
        current_type = type(value)
        # Accept identical type or subclass relationship either direction (covariant-ish)
        if not (
            prior_type is current_type or issubclass(current_type, prior_type) or issubclass(prior_type, current_type)
        ):
            raise TypeCheckError(
                (
                    f"Type mismatch for parameter '{param_name}' in function "
                    f"'{func_name}': inconsistent binding for TypeVar {tv}; "
                    f"previously {prior_type.__name__}, now {current_type.__name__}"
                )
            )
    # Validate constraints first if present
    if constraints:
        if not any(isinstance(value, c) for c in constraints if inspect.isclass(c)):
            raise TypeCheckError(
                (
                    "Type mismatch for parameter "
                    f"'{param_name}' in function '{func_name}': value {value!r} "
                    f"does not satisfy constraints {constraints} of TypeVar {tv}"
                )
            )
    if bound is not None and inspect.isclass(bound):
        if not isinstance(value, bound):
            raise TypeCheckError(
                (
                    "Type mismatch for parameter "
                    f"'{param_name}' in function '{func_name}': value {value!r} "
                    f"not within bound {bound}"
                )
            )
    # Store canonical representative: the first encountered type (class) for comparison
    if prior is None:
        _TYPEVAR_CONTEXT[tv_id] = type(value)
    return True


# Final / ClassVar
@register_type_validator(lambda t: (get_origin(t) in (Final, ClassVar)) or (t in (Final, ClassVar)))
def _validate_final_classvar(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    args = get_args(expected_type) if get_origin(expected_type) else ()
    if not args:
        raise TypeCheckError(
            (
                f"Type mismatch for parameter '{param_name}' in function "
                f"'{func_name}': empty Final/ClassVar has no inner type"
            )
        )
    return recurse(value, args[0], param_name, func_name, sample_override, deep)


# Protocol structural checking
def _is_protocol_type(t: Any) -> bool:
    """Return True if *t* is a ``Protocol`` subclass definition.

    Implementation detail: On Python 3.10+ ``issubclass(<any class>, Protocol)``
    tends to return True broadly, so we instead rely on the private marker
    attribute ``_is_protocol`` that real protocol classes possess. Parameterized
    generics (``list[int]`` etc.) are excluded via ``get_origin``.
    """
    if get_origin(t) is not None:  # typing constructs like list[int]
        return False
    if not isinstance(t, type):
        return False
    if t is Protocol:
        return False
    return bool(getattr(t, "_is_protocol", False))


@register_type_validator(_is_protocol_type)
def _validate_protocol(
    value: Any,
    expected_type: Any,
    param_name: str,
    func_name: str,
    *_: Any,
) -> bool:
    import inspect as _inspect

    # Cache structure per protocol class id
    _CACHE = getattr(_validate_protocol, "_cache", None)
    if _CACHE is None:
        _CACHE = {}
        setattr(_validate_protocol, "_cache", _CACHE)
    cached = _CACHE.get(id(expected_type))
    if cached is None:
        defined = set(expected_type.__dict__.keys())
        ann = set(getattr(expected_type, "__annotations__", {}).keys())
        required = set()
        method_objs: dict[str, Any] = {}
        for name in defined | ann:
            if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
                continue
            obj = expected_type.__dict__.get(name, None)
            if callable(obj) or name in ann or isinstance(obj, (property, classmethod, staticmethod)):
                required.add(name)
            if callable(obj) and _inspect.isfunction(obj):  # only functions for signature comparison
                method_objs[name] = obj
        cached = (required, method_objs)
        _CACHE[id(expected_type)] = cached
    required, method_objs = cached
    missing = [attr for attr in required if not hasattr(value, attr)]
    signature_mismatches: list[str] = []
    # Signature compatibility (light heuristic): positional parameter count & annotations.
    for name, proto_func in method_objs.items():
        if name in missing:
            continue
        impl_attr = getattr(value, name)
        if not callable(impl_attr):
            signature_mismatches.append(f"{name}: not callable")
            continue
        try:
            proto_sig = _inspect.signature(proto_func)
            impl_sig = _inspect.signature(impl_attr)
        except (TypeError, ValueError):  # builtins or C functions; skip
            continue
        # Strip self/cls from start if present in protocol
        proto_params = [
            p for p in proto_sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        impl_params = [
            p for p in impl_sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if proto_params and proto_params[0].name in ("self", "cls"):
            proto_params_no_self = proto_params[1:]
        else:
            proto_params_no_self = proto_params
        if impl_params and impl_params[0].name in ("self", "cls"):
            impl_params_no_self = impl_params[1:]
        else:
            impl_params_no_self = impl_params
        if len(impl_params_no_self) < len(proto_params_no_self):
            signature_mismatches.append(
                f"{name}: expected >= {len(proto_params_no_self)} params, got {len(impl_params_no_self)}"
            )
            continue
        # Annotation compatibility for leading parameters
        proto_hints = get_type_hints(proto_func)
        impl_hints = get_type_hints(impl_attr)
        for p_proto, p_impl in zip(proto_params_no_self, impl_params_no_self):
            expected_ann = proto_hints.get(p_proto.name, p_proto.annotation)
            actual_ann = impl_hints.get(p_impl.name, p_impl.annotation)
            if expected_ann is _inspect._empty or expected_ann is Any:
                continue
            if actual_ann is _inspect._empty or actual_ann is Any:
                continue
            if expected_ann is actual_ann:
                continue
            if _inspect.isclass(expected_ann) and _inspect.isclass(actual_ann) and issubclass(actual_ann, expected_ann):
                continue
            signature_mismatches.append(
                (
                    f"{name}: param '{p_proto.name}' expected "
                    f"{getattr(expected_ann,'__name__', expected_ann)}, got "
                    f"{getattr(actual_ann,'__name__', actual_ann)}"
                )
            )
        # Return type compatibility
        proto_ret = proto_hints.get("return", proto_sig.return_annotation)
        impl_ret = impl_hints.get("return", impl_sig.return_annotation)
        if proto_ret is not _inspect._empty and proto_ret is not Any and impl_ret is not _inspect._empty:
            if impl_ret is not proto_ret:
                if not (_inspect.isclass(impl_ret) and _inspect.isclass(proto_ret) and issubclass(impl_ret, proto_ret)):
                    signature_mismatches.append(
                        (
                            f"{name}: return expected {getattr(proto_ret,'__name__', proto_ret)}, "
                            f"got {getattr(impl_ret,'__name__', impl_ret)}"
                        )
                    )
    if missing or signature_mismatches:
        parts = []
        if missing:
            parts.append(f"missing attributes {missing}")
        if signature_mismatches:
            parts.append("signature mismatches: " + "; ".join(signature_mismatches))
        raise TypeCheckError(
            (
                f"Type mismatch for parameter '{param_name}' in function "
                f"'{func_name}': object {value!r} does not satisfy Protocol "
                f"{expected_type.__name__}: "
            )
            + ", ".join(parts)
        )
    return True


@register_type_validator(lambda t: getattr(get_origin(t), "__name__", None) == "TypeGuard")
def _validate_typeguard(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    # TypeGuard[T] behaves like bool at runtime; we just ensure value is bool
    if not isinstance(value, bool):
        raise TypeCheckError(
            "Type mismatch for parameter "
            f"'{param_name}' in function '{func_name}': expected bool (TypeGuard), "
            f"got {type(value).__name__}"
        )
    return True


@register_type_validator(lambda t: get_origin(t) is Annotated)
def _validate_annotated(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    # Unwrap first arg as the runtime type; metadata ignored
    inner, *_meta = get_args(expected_type)
    return recurse(value, inner, param_name, func_name, sample_override, deep)


def _is_typed_dict_type(t: Any) -> bool:
    return (
        isinstance(t, type)
        and issubclass(t, dict)
        and hasattr(t, "__required_keys__")
        and hasattr(t, "__optional_keys__")
    )


@register_type_validator(_is_typed_dict_type)
def _validate_typed_dict(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    if not isinstance(value, dict):
        raise TypeCheckError(
            (
                f"Type mismatch for parameter '{param_name}' in function "
                f"'{func_name}': expected TypedDict, got {type(value).__name__}"
            )
        )
    annotations = getattr(expected_type, "__annotations__", {})
    required = getattr(expected_type, "__required_keys__", set())
    # Optional keys set retrieved but unused at runtime (accepting extra keys per PEP 589)
    # optional = getattr(expected_type, "__optional_keys__", set())  # intentionally unused
    # Required key presence
    for key in required:
        if key not in value:
            raise TypeCheckError(
                (
                    f"Type mismatch for parameter '{param_name}' in function "
                    f"'{func_name}': missing required key '{key}' for TypedDict "
                    f"{expected_type.__name__}"
                )
            )
    # Type check present keys (sample all; could add sampling later)
    for key, annot in annotations.items():
        if key in value:
            if not recurse(value[key], annot, f"{param_name}['{key}']", func_name, sample_override, deep):
                raise TypeCheckError(
                    (
                        f"Type mismatch for parameter '{param_name}['{key}']' in "
                        f"function '{func_name}': expected {annot}, got "
                        f"{type(value[key]).__name__}"
                    )
                )
    # Extra keys accepted (per PEP 589 unless total=False specifics) – could tighten later
    return True


@register_type_validator(lambda t: Never is not None and (t is Never or getattr(t, "__name__", None) == "Never"))
def _validate_never(value, expected_type, param_name, func_name, *_):
    raise TypeCheckError(
        (
            f"Type mismatch for parameter '{param_name}' in function "
            f"'{func_name}': 'Never' type cannot have a runtime value"
        )
    )


@register_type_validator(
    lambda t: LiteralString is not None and (t is LiteralString or getattr(t, "__name__", None) == "LiteralString")
)
def _validate_literal_string(value, expected_type, param_name, func_name, *_):
    # Best-effort: treat as str; deeper literal tracking unavailable at runtime
    return isinstance(value, str)


def _is_newtype(t: Any) -> bool:
    return callable(t) and hasattr(t, "__supertype__")


@register_type_validator(_is_newtype)
def _validate_newtype(value, expected_type, param_name, func_name, recurse, sample_override, deep):
    underlying = getattr(expected_type, "__supertype__", Any)
    return recurse(value, underlying, param_name, func_name, sample_override, deep)


# NoReturn handled in return validation; we register minimal predicate to avoid other validators
@register_type_validator(lambda t: (t is NoReturn or getattr(t, "__name__", None) == "NoReturn"))
def _validate_noreturn(value, expected_type, param_name, func_name, *_):  # pragma: no cover - enforced elsewhere
    return True


__all__ = ["register_type_validator", "iter_type_validators"]
__all__.append("reset_typevar_context")
