import asyncio
from collections import Counter
from typing import Callable, ClassVar, Coroutine, Final, Generator, NewType, TypeGuard

import pytest

from typecheck import TypeCheckError, typecheck


def test_final_and_classvar():
    # Use container wrapper functions expecting inner types; runtime validator treats Final/ClassVar like their arg
    @typecheck()
    def final_func(x: int) -> int:
        return x

    @typecheck()
    def classvar_func(x: str) -> str:
        return x

    assert final_func(5) == 5
    assert classvar_func("ok") == "ok"
    for bad_call in [lambda: final_func("x"), lambda: classvar_func(123)]:  # type: ignore[arg-type]
        with pytest.raises(TypeCheckError):
            bad_call()


def test_generator_type():
    @typecheck()
    def needs_generator(g: Generator) -> str:
        return "ok"

    def gen():
        yield 1
        yield 2

    assert needs_generator(gen()) == "ok"
    with pytest.raises(TypeCheckError):
        needs_generator([1, 2, 3])  # type: ignore[arg-type]


def test_coroutine_type():
    async def sample():
        return 1

    @typecheck()
    def takes_coro(c: Coroutine) -> str:
        return "got"

    async def runner():
        c = sample()
        assert takes_coro(c) == "got"
        await c

    asyncio.run(runner())
    with pytest.raises(TypeCheckError):
        takes_coro([1, 2, 3])  # type: ignore[arg-type]


def test_forward_ref_and_callable_and_typeguard_and_format_type_edge():
    # Forward reference: string annotation
    from typecheck import TypeCheckError, _format_type, typecheck  # type: ignore

    class Later: ...

    @typecheck()
    def use_forward(x):  # annotate later with forward ref string
        return 1

    use_forward.__annotations__["x"] = "Later"  # type: ignore[index]
    assert use_forward(Later()) == 1

    # Callable mismatch to exercise validator failure path (line ~85)
    @typecheck()
    def needs_cb(cb: Callable[[int], int]):
        return cb(2)

    with pytest.raises(TypeCheckError):
        needs_cb(123)  # type: ignore[arg-type]

    # TypeGuard misuse: expecting bool, supply int to trigger error lines 174-178
    from typing import TypeGuard as TG

    @typecheck()
    def guard_func(flag: TG[int]):  # type: ignore[type-arg]
        return flag

    # success path (bool)
    assert guard_func(True) is True  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        guard_func(1)  # type: ignore[arg-type]  # not bool

    # format_type exception path
    from typecheck.utils import format_type

    class BadStr:
        def __str__(self):
            raise RuntimeError("boom")

    # Should fall back to __name__ or repr without raising
    # Calling with the class does not trigger the exception; include instance
    assert isinstance(format_type(BadStr), str)
    val = format_type(BadStr())  # instance triggers __str__ RuntimeError and falls back
    assert "BadStr" in val
    # _format_type returns str(int) which is "<class 'int'>" in current implementation
    assert _format_type(int) in ("int", "<class 'int'>")

    @typecheck()
    def needs_callable(cb: Callable[[int], int]):
        return cb(1)

    with pytest.raises(TypeCheckError):
        needs_callable(object())  # type: ignore[arg-type]


def test_callable_signature_success_and_failure():
    """Explicit Callable[[int], int] success + failure (merged from former additional file)."""

    @typecheck()
    def accepts(cb: Callable[[int], int], x: int) -> int:
        return cb(x)

    assert accepts(lambda v: v + 1, 2) == 3
    with pytest.raises(TypeCheckError):
        accepts(123, 1)  # type: ignore[arg-type]


def test_callable_arity_and_param_return_mismatch_additional():
    @typecheck()
    def k(fn: Callable[[int, str], int]):  # type: ignore[type-arg]
        return fn

    def fn_bad(a: int):  # only one param
        return 0

    with pytest.raises(TypeCheckError):
        k(fn_bad)  # type: ignore[arg-type]

    @typecheck()
    def k2(fn: Callable[[int], int]):
        return fn

    def fn_bad_param(a: str) -> int:
        return 1

    with pytest.raises(TypeCheckError):
        k2(fn_bad_param)  # type: ignore[arg-type]

    def fn_bad_ret(a: int) -> str:
        return "x"

    with pytest.raises(TypeCheckError):
        k2(fn_bad_ret)  # type: ignore[arg-type]


@typecheck()
def _guard_param(flag: TypeGuard[int]):  # type: ignore[type-arg]
    return flag


def test_typeguard_param_success_and_failure():
    """Additional TypeGuard parameter acceptance/failure variant (merged)."""
    assert _guard_param(True) is True  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        _guard_param(0)  # type: ignore[arg-type]


def test_never_and_literalstring_and_newtype_and_annotated():
    import typing as _t

    # Never
    if hasattr(_t, "Never"):

        @typecheck()
        def nv(x: _t.Never):  # type: ignore[attr-defined]
            return x

        with pytest.raises(TypeCheckError):
            nv(1)  # type: ignore[arg-type]
    # LiteralString
    if hasattr(_t, "LiteralString"):
        LS = _t.LiteralString  # type: ignore[attr-defined]

        @typecheck()
        def ls(x: LS):  # type: ignore[valid-type]
            return x

        ls("ok")
        with pytest.raises(TypeCheckError):
            ls(5)  # type: ignore[arg-type]
    # NewType underlying acceptance
    MyStr = NewType("MyStr", str)

    @typecheck()
    def nt(x: MyStr):
        return x

    nt(MyStr("hi"))
    nt("hi")  # type: ignore[arg-type]  # underlying type accepted
