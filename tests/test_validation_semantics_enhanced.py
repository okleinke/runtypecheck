from typing import Callable, Protocol, TypeVar, Union

import pytest

from typecheck import TypeCheckError, typecheck


# Union deterministic failure
@typecheck()
def takes_union(u: Union[int, str]):
    return u


# Callable signature shape
@typecheck()
def needs_callable(cb: Callable[[int, int], int]):
    return cb(1, 2)


# Protocol aggregate
class P(Protocol):
    def a(self) -> int: ...
    def b(self) -> int: ...


@typecheck()
def needs_protocol(x: P) -> int:
    return x.a() + x.b()


# TypeVar consistent binding
T = TypeVar("T")


@typecheck()
def pair(a: T, b: T):
    return a, b


def test_union_failure_message():
    with pytest.raises(TypeCheckError) as exc:
        takes_union(3.14)  # type: ignore[arg-type]
    assert "did not match any Union option" in str(exc.value)


def test_callable_signature_shape():
    def good(x: int, y: int) -> int:
        return x + y

    assert needs_callable(good) == 3

    def bad(x: int) -> int:
        return x

    with pytest.raises(TypeCheckError):
        needs_callable(bad)  # type: ignore[arg-type]

    def wrong_param_types(x: str, y: int) -> int:
        return y

    with pytest.raises(TypeCheckError):
        needs_callable(wrong_param_types)  # type: ignore[arg-type]

    def wrong_return(x: int, y: int) -> str:
        return "no"

    with pytest.raises(TypeCheckError):
        needs_callable(wrong_return)  # type: ignore[arg-type]


def test_protocol_aggregate_missing():
    class Impl:
        def a(self) -> int:
            return 1

        # missing b

    with pytest.raises(TypeCheckError) as exc:
        needs_protocol(Impl())  # type: ignore[arg-type]
    assert "missing attributes" in str(exc.value)


def test_protocol_signature_mismatch():
    class ImplBad:
        def a(self, extra: int) -> int:
            return 1  # extra param reduces compatibility

        def b(self) -> str:
            return "x"  # wrong return

    with pytest.raises(TypeCheckError) as exc:
        needs_protocol(ImplBad())  # type: ignore[arg-type]
    msg = str(exc.value)
    assert "signature mismatches" in msg and "return expected" in msg


def test_typevar_consistent_binding():
    assert pair(1, 2) == (1, 2)
    with pytest.raises(TypeCheckError):
        pair(1, 3.14)  # float vs int should conflict


# Nested composite TypeVar binding inside containers
TList = TypeVar("TList")


@typecheck()
def pair_lists(a: list[TList], b: list[TList]):
    return a, b


def test_typevar_nested_binding_conflict():
    assert pair_lists([1, 2], [3, 4]) == ([1, 2], [3, 4])
    with pytest.raises(TypeCheckError):
        pair_lists([1], ["a"])  # type: ignore[list-item]
