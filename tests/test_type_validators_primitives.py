from typing import Any, Literal, Type, TypeVar, Union

import pytest

from typecheck import TypeCheckError, typecheck


@typecheck()
def takes_any(x: Any):
    return x


@typecheck()
def takes_none(x: None):  # type: ignore[valid-type]
    return x


@typecheck()
def takes_union(x: Union[int, str]):  # type: ignore[type-arg]
    return x


@typecheck()
def takes_literal(x: Literal[1, "a"]):  # type: ignore[type-arg]
    return x


@typecheck()
def wants_type(x: Type[int]):  # type: ignore[type-arg]
    return x


T = TypeVar("T")


@typecheck()
def two_params(a: T, b: T):
    return a, b


def test_any_and_none():
    assert takes_any(object()) is not None
    assert takes_none(None) is None


def test_union_success():
    assert takes_union(5) == 5
    assert takes_union("hi") == "hi"


def test_literal_success():
    assert takes_literal(1) == 1
    assert takes_literal("a") == "a"


def test_type_annotation_non_class():
    with pytest.raises(TypeCheckError):
        wants_type(123)  # type: ignore[arg-type]


def test_typevar_prior_binding_branch():
    # Bind T to int via first param; second param bool (subclass of int) triggers prior branch line 147
    assert two_params(1, True) == (1, True)
    assert two_params(2, 3) == (2, 3)


# Reuse of TypeVar binding across parameters (pair) and permissive mismatches
U = TypeVar("U")


@typecheck()
def pair(a: U, b: U):
    return a, b


def test_typevar_binding_reuse_and_mismatch():
    assert pair(1, 2) == (1, 2)
    assert pair(True, 3) == (True, 3)  # bool subclass of int
    with pytest.raises(TypeCheckError):
        pair(1, "x")  # type: ignore[arg-type]


from typing import ClassVar as _ClassVar
from typing import Final as _Final  # local aliases to avoid reordering top imports


@typecheck()
def use_final(x: _Final[int]):  # type: ignore[type-arg]
    return x


@typecheck()
def use_classvar(x: _ClassVar[int]):  # type: ignore[type-arg]
    return x


def test_final_and_classvar_recursion():
    assert use_final(5) == 5  # type: ignore[arg-type]
    assert use_classvar(7) == 7
    # float should fail (bool allowed as int subclass)
    with pytest.raises(TypeCheckError):
        use_final(5.2)  # type: ignore[arg-type]


class _Base: ...


class _Sub(_Base): ...


class _Other: ...


@typecheck()
def takes_type_base(x: Type[_Base]):  # type: ignore[type-arg]
    return x


def test_type_annotation_negative():
    takes_type_base(_Base)
    takes_type_base(_Sub)
    with pytest.raises(TypeCheckError):
        takes_type_base(_Other)  # type: ignore[arg-type]


@typecheck()
def needs_union_false(x: Union[int, str]):  # type: ignore[type-arg]
    return x


def test_union_false_branch():
    with pytest.raises(TypeCheckError):
        needs_union_false(3.14)  # type: ignore[arg-type]


TConstr = TypeVar("TConstr", int, str)
TBound = TypeVar("TBound", bound=list)
TAny = TypeVar("TAny")


@typecheck()
def t_constrained(x: TConstr):
    return x


@typecheck()
def t_bound(x: TBound):  # type: ignore[type-var]
    return x


@typecheck()
def t_inconsistent(a: TAny, b: TAny):
    return a, b


def test_additional_typevar_constraints_and_bound_and_inconsistent():
    t_constrained(3)
    with pytest.raises(TypeCheckError):
        t_constrained(3.14)  # type: ignore[arg-type]
    t_bound([])
    with pytest.raises(TypeCheckError):
        t_bound(())  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        t_inconsistent(1, "x")  # type: ignore[arg-type]
