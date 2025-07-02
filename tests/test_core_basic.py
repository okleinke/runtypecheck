import os
from typing import Any, Callable, Optional, Type, Union

import pytest

from typecheck import TypeCheckError, typecheck

# Basic types and strict mode


def test_basic_types():
    @typecheck()
    def basic_func(x: int, y: str, z: float = 1.0) -> str:
        return f"{x}-{y}-{z}"

    assert basic_func(42, "hello", 3.14) == "42-hello-3.14"
    try:
        basic_func("42", "hello", 3.14)  # type: ignore[arg-type]
    except TypeCheckError as e:
        assert "expected int" in str(e)
    else:
        assert False
    try:
        basic_func(42, 123, 3.14)  # type: ignore[arg-type]
    except TypeCheckError as e:
        assert "expected str" in str(e)
    else:
        assert False
    try:
        basic_func(42, "hello", "3.14")  # type: ignore[arg-type]
    except TypeCheckError as e:
        assert "expected float" in str(e)
    else:
        assert False


def test_strict_mode():
    @typecheck(strict=True)
    def strict_func(x: int, y) -> None:
        pass

    try:
        strict_func(42, "hello")
    except TypeCheckError as e:
        assert "lacks type annotation" in str(e)
    else:
        assert False

    @typecheck(strict=False)
    def non_strict_func(x: int, y) -> None:
        pass

    non_strict_func(42, "hello")


def test_union_optional_types():
    @typecheck()
    def union_func(value: Union[int, str], optional: Optional[float] = None) -> str:
        return f"{value}-{optional}"

    assert union_func(42) == "42-None"
    assert union_func("hello", 3.14) == "hello-3.14"
    assert union_func(42, None) == "42-None"
    try:
        union_func([1, 2, 3])  # type: ignore[arg-type]
    except TypeCheckError as e:
        assert "did not match any Union option" in str(e)
    else:
        assert False


def test_any_type():
    @typecheck()
    def any_func(value: Any, other: int) -> str:
        return f"{value}-{other}"

    assert any_func("string", 42) == "string-42"
    assert any_func(123, 42) == "123-42"
    assert any_func([1, 2, 3], 42) == "[1, 2, 3]-42"
    assert any_func(None, 42) == "None-42"
    try:
        any_func("string", "not")  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False


def test_literal_type():
    from typing import Literal

    @typecheck()
    def literal_func(mode: Literal["read", "write", "append"], count: Literal[1, 2, 3]) -> str:
        return f"{mode}-{count}"

    assert literal_func("read", 1) == "read-1"
    assert literal_func("write", 2) == "write-2"
    assert literal_func("append", 3) == "append-3"
    for bad in [("invalid", 1), ("read", 4)]:
        try:
            literal_func(*bad)  # type: ignore
        except TypeCheckError:
            pass
        else:
            assert False


def test_callable_type():
    @typecheck()
    def callback_func(callback: Callable) -> str:
        return f"Got callback: {callback.__name__}"

    def my_func():
        pass

    assert "my_func" in callback_func(my_func)
    assert "len" in callback_func(len)
    assert "lambda" in callback_func(lambda x: x)
    try:
        callback_func("not callable")  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False


def test_type_annotation():
    class Person: ...

    @typecheck()
    def type_func(cls: Type[Person]) -> str:
        return f"Got class: {cls.__name__}"

    assert type_func(Person) == "Got class: Person"
    for bad in [Person(), "not a class"]:  # type: ignore[arg-type]
        try:
            type_func(bad)  # type: ignore[arg-type]
        except TypeCheckError:
            pass
        else:
            assert False


def test_runtime_disable(monkeypatch):
    monkeypatch.setenv("TYPECHECK_DISABLED", "1")

    @typecheck()
    def disabled_func(x: int) -> int:
        return x

    # Should not raise despite wrong type
    assert disabled_func("not an int") == "not an int"  # type: ignore[arg-type]


def test_env_disable_decorator(monkeypatch):
    monkeypatch.setenv("TYPECHECK_DISABLED", "1")

    @typecheck()
    def f(x: int):
        # intentionally wrong return type and accept wrong arg type
        return str(x)

    assert f("not_int") == "not_int"  # type: ignore[arg-type]  # wrong param & return ok when disabled
    monkeypatch.delenv("TYPECHECK_DISABLED")


def test_strict_return_requires_annotation():
    from typecheck import TypeCheckError as _TCE

    with pytest.raises(_TCE):  # type: ignore[name-defined]

        @typecheck(strict_return=True)
        def g(x: int):  # no return annotation
            return x

        g(1)


def test_type_annotation_mismatch_additional():
    class Base: ...

    class Other: ...

    @typecheck()
    def k3(x: type[Base]):  # noqa: F821
        return x

    with pytest.raises(TypeCheckError):
        k3(Other)  # type: ignore[arg-type]
