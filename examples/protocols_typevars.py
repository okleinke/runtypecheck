"""Protocol structural typing and constrained TypeVar validation example."""

from typing import Protocol, TypeVar

from typecheck import TypeCheckError, typecheck


class SupportsClose(Protocol):
    def close(self) -> None: ...


class Resource:
    def close(self) -> None:
        print("closed")


@typecheck()
def shutdown(res: SupportsClose) -> None:
    res.close()


T = TypeVar("T", int, str)


@typecheck()
def echo(x: T) -> T:
    return x


if __name__ == "__main__":
    shutdown(Resource())
    try:

        class NoClose:
            pass

        shutdown(NoClose())
    except TypeCheckError as e:
        print("Caught:", e)
    print(echo(5))
    print(echo("hi"))
    try:
        echo(3.14)  # type: ignore
    except TypeCheckError as e:
        print("Constraint caught:", e)
