import asyncio

import pytest

from typecheck import TypeCheckError, typecheck


@typecheck()
async def add_async(x: int, y: int) -> int:
    await asyncio.sleep(0)
    return x + y


@typecheck(strict=True, strict_return=True)
async def bad_args_async(x: int, y: int) -> int:
    await asyncio.sleep(0)
    return x + y


@typecheck()
async def returns_str(x: int) -> int:
    await asyncio.sleep(0)
    return "not an int"  # type: ignore


def test_async_basic_success():
    assert asyncio.run(add_async(1, 2)) == 3


def test_async_argument_type_error():
    with pytest.raises(TypeCheckError):
        asyncio.run(add_async("a", 2))  # type: ignore


def test_async_return_type_error():
    with pytest.raises(TypeCheckError):
        asyncio.run(returns_str(1))
