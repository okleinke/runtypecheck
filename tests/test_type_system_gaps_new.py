from typing import Annotated, ClassVar, Final, NewType, TypedDict

import pytest

from typecheck import TypeCheckError, typecheck


# Annotated unwrap
@typecheck()
def takes_annotated(x: Annotated[int, "meta"]) -> int:
    return x


# NewType underlying
UserId = NewType("UserId", int)


@typecheck()
def takes_user_id(uid: UserId) -> int:
    return int(uid)


# TypedDict
class Person(TypedDict):
    name: str
    age: int


@typecheck()
def takes_person(p: Person) -> str:
    return p["name"]


# Zero-arg Final / ClassVar rejection
@typecheck()
def takes_bad_final(x: Final):  # type: ignore[type-arg]
    return x


@typecheck()
def takes_bad_classvar(x: ClassVar):  # type: ignore[type-arg]
    return x


def test_annotated_and_newtype_and_typed_dict():
    assert takes_annotated(5) == 5
    assert takes_user_id(UserId(7)) == 7
    assert takes_person({"name": "a", "age": 3}) == "a"
    # Missing key
    with pytest.raises(TypeCheckError):
        takes_person({"name": "a"})  # type: ignore[arg-type]
    # Wrong type
    with pytest.raises(TypeCheckError):
        takes_person({"name": "a", "age": "x"})  # type: ignore[arg-type]


def test_zero_arg_final_classvar():
    with pytest.raises(TypeCheckError):
        takes_bad_final(1)  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        takes_bad_classvar(1)  # type: ignore[arg-type]


def test_newtype_underlying_acceptance_additional():
    MyStr2 = NewType("MyStr2", str)

    @typecheck()
    def nt(x: MyStr2):  # type: ignore[valid-type]
        return x

    nt(MyStr2("hi"))
    nt("hi")  # type: ignore[arg-type]
