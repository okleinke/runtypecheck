"""Showcases advanced typing constructs supported: TypedDict, NewType, Annotated, Protocol, TypeVar.

Combines several features into one concise demo.
"""
from __future__ import annotations

from typing import Annotated, NewType, Protocol, TypeVar, TypedDict

from typecheck import typecheck, TypeCheckError


# TypedDict example
class Person(TypedDict):
    name: str
    age: int


# NewType example
UserId = NewType("UserId", int)


# Protocol example
class Greeter(Protocol):
    def greet(self, person: Person) -> str: ...


@typecheck()
class FriendlyGreeter:
    def greet(self, person: Person) -> str:
        return f"Hello {person['name']} ({person['age']})"


T = TypeVar("T", int, str)


@typecheck()
def echo_first(x: T, y: T) -> T:  # demonstrates consistent TypeVar binding across params
    return x


@typecheck()
def show(uid: Annotated[UserId, "db id"], greeter: Greeter, data: Person) -> str:
    return f"{uid}:{greeter.greet(data)}"


if __name__ == "__main__":
    g = FriendlyGreeter()
    person: Person = {"name": "Alice", "age": 30}
    print(show(UserId(5), g, person))
    print(echo_first(1, 2))
    print(echo_first("a", "b"))
    try:
        echo_first(1, "mixed")  # type: ignore[arg-type]
    except TypeCheckError as e:
        print("TypeVar mismatch caught:", e)
    try:
        show(UserId(7), g, {"name": "Bob"})  # type: ignore[arg-type]
    except TypeCheckError as e:
        print("TypedDict missing key caught:", e)
