import asyncio
import typing
from typing import Generic, Iterable, Optional, Protocol, TypeVar

import pytest

from typecheck import TypeCheckError, typecheck


# Protocol support tests
class SupportsLen(Protocol):
    def __len__(self) -> int: ...


class RichProtocol(Protocol):
    @property
    def value(self) -> int: ...
    @classmethod
    def build(cls) -> "RichProtocol": ...  # forward ref in protocol
    def method(self) -> str: ...


@typecheck()
def use_len(x: SupportsLen) -> int:
    return len(x)


# TypeVar with constraints / bound tests
T_constrained = TypeVar("T_constrained", int, str)
T_bound = TypeVar("T_bound", bound=int)


@typecheck()
def echo_constrained(x: T_constrained) -> T_constrained:
    return x


@typecheck()
def echo_bound(x: T_bound) -> int:  # type: ignore[type-arg]
    return x


# Narrowing via simple TypeGuard-like pattern (simulated)
from typing import TypeGuard


@typecheck()
def is_all_ints(seq: Iterable[object]) -> bool:  # placeholder for TypeGuard test
    return all(isinstance(i, int) for i in seq)


# Basic runtime tests


def test_protocol_accepts_builtin():
    assert use_len("hello") == 5


class CustomLen:
    def __len__(self):
        return 42


def test_protocol_custom():
    c = CustomLen()
    assert use_len(c) == 42


def test_protocol_reject_missing():
    class NoLen:
        pass

    with pytest.raises(TypeCheckError):
        use_len(NoLen())  # type: ignore[arg-type]


def test_rich_protocol_attributes():
    @typecheck()
    def use_rich(x: RichProtocol) -> int:
        return x.value

    class Impl:
        value = 5

        @classmethod
        def build(cls):
            return cls()

        def method(self):
            return "ok"

    assert use_rich(Impl()) == 5

    class MissingOne:
        value = 1

        def method(self):
            return "x"

    # Missing build classmethod
    with pytest.raises(TypeCheckError):
        use_rich(MissingOne())  # type: ignore[arg-type]


def test_full_protocol_success_and_missing():
    """Merged from former test_type_validators_additional FullProtocol test."""

    class FullProtocol(Protocol):
        @property
        def value(self) -> int: ...
        @classmethod
        def build(cls) -> "FullProtocol": ...
        def action(self) -> str: ...

    @typecheck()
    def use(p: FullProtocol) -> int:
        return p.value

    class Impl:
        value = 5

        @classmethod
        def build(cls):
            return cls()

        def action(self):
            return "ok"

    assert use(Impl()) == 5

    class Missing:
        value = 1

        @classmethod
        def build(cls):
            return cls()

        # action missing

    with pytest.raises(TypeCheckError):
        use(Missing())  # type: ignore[arg-type]


def test_typevar_constrained_accept():
    assert echo_constrained(3) == 3
    assert echo_constrained("a") == "a"


def test_typevar_constrained_reject():
    with pytest.raises(TypeCheckError):
        echo_constrained(3.14)  # type: ignore[arg-type]


def test_typevar_bound_accept():
    assert echo_bound(5) == 5


def test_typevar_bound_reject():
    # bool (subclass of int) should be allowed
    echo_bound(True)  # bool acceptable
    with pytest.raises(TypeCheckError):
        echo_bound(3.2)  # type: ignore[arg-type]


class _P(Protocol):  # local to avoid naming clash
    def foo(self, a: int) -> int: ...


class _ImplGood:
    def foo(self, a: int) -> int:
        return a


class _ImplMissing:
    pass


class _ImplBadSig:
    def foo(self, a: str) -> int:
        return 0


@typecheck()
def _proto_func(x: _P):
    return x


def test_protocol_validation_branches_additional():
    _proto_func(_ImplGood())
    with pytest.raises(TypeCheckError):
        _proto_func(_ImplMissing())  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        _proto_func(_ImplBadSig())  # type: ignore[arg-type]
