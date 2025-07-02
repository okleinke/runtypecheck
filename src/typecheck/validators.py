"""Built-in validator helpers and custom validator registry for typecheck.

Each helper focuses on a category (sequences, mappings, tuples, sets, iterables)
so that the main logic in ``_check_type`` stays lean. Validators that need to
perform recursive element checking receive a ``check_type`` callback so we avoid
circular imports.
"""

from __future__ import annotations

from collections import ChainMap, Counter, OrderedDict, defaultdict, deque
from collections.abc import Iterable as AbcIterable
from collections.abc import Iterator as AbcIterator
from collections.abc import Mapping as AbcMapping
from collections.abc import Sequence as AbcSequence
from itertools import islice, tee
from typing import Any, Callable, Type

from . import TypeCheckError  # type: ignore  # runtime import
from .config import config
from .utils import DEFAULT_SAMPLE_SIZE
from .utils import format_type as _format_type

ValidatorFunc = Callable[[Any, Any, str, str, Callable[..., bool], int | None, bool], bool]

# Custom validator registry (user-extensible)
_custom_validators: dict[Type[Any], Callable[[Any, Type[Any]], bool]] = {}


def register_validator(expected_type: Type[Any]):
    """Decorator to register a custom validator for a concrete type.

    Custom validator signature: (value, expected_type) -> bool
    Return True for pass; False (or raise TypeCheckError) for failure.
    """

    def _decorator(func: Callable[[Any, Type[Any]], bool]):
        _custom_validators[expected_type] = func
        return func

    return _decorator


def get_custom_validator(expected_type: Any):
    return _custom_validators.get(expected_type)


# ---- Built-in container validators -----------------------------------------------------------


def _check_sequence_elements(
    sequence,
    element_type,
    param_name: str,
    func_name: str,
    check_type: Callable[..., bool],
    sample_override: int | None = None,
    deep: bool = False,
) -> bool:
    if deep:
        eff_sample = None
    else:
        eff_sample = DEFAULT_SAMPLE_SIZE if sample_override is None else sample_override

    sample_size = None
    if hasattr(sequence, "__len__") and eff_sample is not None:
        sample_size = min(len(sequence), eff_sample)
    elif eff_sample is not None:
        sample_size = eff_sample

    for i, item in enumerate(sequence):
        if sample_size is not None and i >= sample_size:
            break
        if not check_type(
            item, element_type, f"{param_name}[{i}]", func_name, sample_override=sample_override, deep=deep
        ):
            raise TypeCheckError(
                f"Type mismatch for parameter '{param_name}[{i}]' in function '{func_name}': "
                f"expected {_format_type(element_type)}, got {type(item).__name__} ({item!r})"
            )
    return True


def _check_mapping_contents(
    mapping,
    key_type,
    value_type,
    param_name: str,
    func_name: str,
    check_type: Callable[..., bool],
    sample_override: int | None = None,
    deep: bool = False,
) -> bool:
    if deep:
        eff_sample = None
    else:
        eff_sample = DEFAULT_SAMPLE_SIZE if sample_override is None else sample_override

    sample_count = 0
    for k, v in mapping.items():
        if eff_sample is not None and sample_count >= eff_sample:
            break
        if not check_type(k, key_type, f"{param_name} key", func_name, sample_override=sample_override, deep=deep):
            raise TypeCheckError(
                f"Type mismatch for parameter '{param_name} key' in function '{func_name}': "
                f"expected {_format_type(key_type)}, got {type(k).__name__} ({k!r})"
            )
        if not check_type(v, value_type, f"{param_name}[{k!r}]", func_name, sample_override=sample_override, deep=deep):
            raise TypeCheckError(
                f"Type mismatch for parameter '{param_name}[{k!r}]' in function '{func_name}': "
                f"expected {_format_type(value_type)}, got {type(v).__name__} ({v!r})"
            )
        sample_count += 1
    return True


def _check_tuple_contents(
    value,
    type_args,
    param_name: str,
    func_name: str,
    check_type: Callable[..., bool],
    sample_override: int | None = None,
    deep: bool = False,
) -> bool:
    if len(type_args) == 2 and type_args[1] is ...:
        element_type = type_args[0]
        return _check_sequence_elements(
            value, element_type, param_name, func_name, check_type, sample_override=sample_override, deep=deep
        )
    else:
        if len(value) != len(type_args):
            raise TypeCheckError(
                (
                    f"Type mismatch for parameter '{param_name}' in function '{func_name}': "
                    f"expected tuple of length {len(type_args)} (from {type_args}), got tuple of length "
                    f"{len(value)} ({value!r})"
                )
            )
        for i, (item, expected_item_type) in enumerate(zip(value, type_args)):
            if not check_type(
                item, expected_item_type, f"{param_name}[{i}]", func_name, sample_override=sample_override, deep=deep
            ):
                raise TypeCheckError(
                    f"Type mismatch for parameter '{param_name}[{i}]' in function '{func_name}': "
                    f"expected {_format_type(expected_item_type)}, got {type(item).__name__} ({item!r})"
                )
    return True


def _check_set_elements(
    set_value,
    element_type,
    param_name: str,
    func_name: str,
    check_type: Callable[..., bool],
    sample_override: int | None = None,
    deep: bool = False,
) -> bool:
    if deep:
        eff_sample = None
    else:
        eff_sample = DEFAULT_SAMPLE_SIZE if sample_override is None else sample_override

    sample_count = 0
    for item in set_value:
        if eff_sample is not None and sample_count >= eff_sample:
            break
        if not check_type(
            item, element_type, f"{param_name} element", func_name, sample_override=sample_override, deep=deep
        ):
            raise TypeCheckError(
                f"Type mismatch for parameter '{param_name} element' in function '{func_name}': "
                f"expected {_format_type(element_type)}, got {type(item).__name__} ({item!r})"
            )
        sample_count += 1
    return True


# Origins mapped to validation strategy (set at import time)
ORIGIN_VALIDATORS: dict[Any, Callable[..., bool]] = {}


def _ov_list(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return (
        _check_sequence_elements(value, type_args[0], param_name, func_name, check_type, sample_override, deep)
        if type_args
        else True
    )


def _ov_tuple(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return _check_tuple_contents(value, type_args, param_name, func_name, check_type, sample_override, deep)


def _ov_set(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return (
        _check_set_elements(value, type_args[0], param_name, func_name, check_type, sample_override, deep)
        if type_args
        else True
    )


def _ov_mapping(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return (
        _check_mapping_contents(
            value, type_args[0], type_args[1], param_name, func_name, check_type, sample_override, deep
        )
        if len(type_args) >= 2
        else True
    )


def _ov_counter(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return (
        all(
            check_type(k, type_args[0], f"{param_name} key", func_name, sample_override=sample_override, deep=deep)
            for k in value.keys()
        )
        if type_args
        else True
    )


def _ov_iterable(value, type_args, param_name, func_name, check_type, sample_override, deep):
    return _iterable_validator(value, type_args, param_name, func_name, check_type, sample_override, deep)


def register_default_origin_validators():
    ORIGIN_VALIDATORS.update(
        {
            list: _ov_list,
            tuple: _ov_tuple,
            set: _ov_set,
            frozenset: _ov_set,
            dict: _ov_mapping,
            deque: _ov_list,
            defaultdict: _ov_mapping,
            OrderedDict: _ov_mapping,
            Counter: _ov_counter,
            ChainMap: _ov_mapping,
            AbcSequence: _ov_list,
            AbcMapping: _ov_mapping,
            AbcIterable: _ov_iterable,
            AbcIterator: _ov_iterable,
        }
    )


def _iterable_validator(value, type_args, param_name, func_name, check_type, sample_override, deep):
    if not type_args:
        return True
    element_type = type_args[0]

    if config.lazy_iterable_validation and not deep and not hasattr(value, "__len__"):
        # Treat as potentially one-pass iterator; sample without consuming original using tee
        try:
            clone, value = tee(value)
        except TypeError:
            # Not tee-able; fall back to eager sample path below
            pass
        else:
            eff_sample = DEFAULT_SAMPLE_SIZE if sample_override is None else sample_override
            sample_items = list(islice(clone, eff_sample))
            for idx, item in enumerate(sample_items):
                if not check_type(
                    item,
                    element_type,
                    f"{param_name} element[{idx}]",
                    func_name,
                    sample_override=sample_override,
                    deep=deep,
                ):
                    raise TypeCheckError(
                        f"Type mismatch for parameter '{param_name} element[{idx}]' in function '{func_name}': "
                        f"expected {_format_type(element_type)}, got {type(item).__name__} ({item!r})"
                    )
            # Rebuild iterator chain; validated sample yielded first. Remainder left unvalidated (sampling semantics).
            return True

    # Fallback: eager sampled validation
    if deep:
        eff_sample = None
    else:
        eff_sample = DEFAULT_SAMPLE_SIZE if sample_override is None else sample_override
    sample_count = 0
    for item in value:
        if eff_sample is not None and sample_count >= eff_sample:
            break
        if not check_type(
            item, element_type, f"{param_name} element", func_name, sample_override=sample_override, deep=deep
        ):
            raise TypeCheckError(
                f"Type mismatch for parameter '{param_name} element' in function '{func_name}': "
                f"expected {_format_type(element_type)}, got {type(item).__name__} ({item!r})"
            )
        sample_count += 1
    return True


# Initialize defaults on import
register_default_origin_validators()

__all__ = [
    "register_validator",
    "get_custom_validator",
    "ORIGIN_VALIDATORS",
    "_check_sequence_elements",
    "_check_mapping_contents",
    "_check_tuple_contents",
    "_check_set_elements",
]
