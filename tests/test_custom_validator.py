from typecheck import TypeCheckError, register_validator, typecheck


class PositiveInt:
    def __init__(self, value: int):
        self.value = value

    def is_valid(self) -> bool:
        return isinstance(self.value, int) and self.value >= 0


@register_validator(PositiveInt)
def _validate_positive_int(value, expected_type):
    return isinstance(value, PositiveInt) and value.is_valid()


@typecheck()
def use_positive(x: PositiveInt) -> int:
    return x.value * 2


def test_custom_validator_success():
    assert use_positive(PositiveInt(3)) == 6


def test_custom_validator_failure():
    try:
        use_positive(PositiveInt(-5))
    except TypeCheckError:
        pass
    else:
        assert False, "Expected TypeCheckError for invalid PositiveInt"
