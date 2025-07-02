"""Illustrates lazy iterable validation: generator elements checked on demand."""

from typecheck import typecheck, config, TypeCheckError
from collections.abc import Iterable


def make_numbers():
    for x in [1, 2, 3, "bad", 5]:  # type: ignore
        yield x


config.lazy_iterable_validation = True


@typecheck()
def consume(seq: Iterable[int]) -> int:
    return sum(x for x in seq if isinstance(x, int))


if __name__ == "__main__":
    try:
        consume(make_numbers())
    except TypeCheckError as e:
        print("Caught during lazy iteration:", e)
