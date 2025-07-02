"""Registers and uses a custom validator for a user-defined PositiveInt type."""

from typecheck import typecheck, register_validator, TypeCheckError


class PositiveInt(int):
    pass


@register_validator(PositiveInt)
def _validate_positive(value, expected_type):
    return isinstance(value, int) and value >= 0


@typecheck()
def square(x: PositiveInt) -> int:
    return x * x


if __name__ == "__main__":
    print(square(PositiveInt(4)))
    try:
        print(square(PositiveInt(-2)))
    except TypeCheckError as e:
        print("Caught:", e)
