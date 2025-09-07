"""Shows async function validation with awaited return type checking."""

import asyncio

from typecheck import TypeCheckError, typecheck


@typecheck()
async def fetch_data(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


async def main():
    print(await fetch_data(5))
    try:
        await fetch_data("bad")  # type: ignore
    except TypeCheckError as e:
        print("Caught:", e)


if __name__ == "__main__":
    asyncio.run(main())
