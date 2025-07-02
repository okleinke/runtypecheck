import pytest

from typecheck import TypeCheckError, register_validator, typecheck


# Consistent type name formatting for parameter mismatch
@typecheck()
def takes_int(x: int):
    return x


# Custom validator that raises an unexpected exception to test traceback propagation
class Boom:
    pass


@register_validator(Boom)
def _boom_validator(value, expected_type):
    raise RuntimeError("boom failure inner")


@typecheck()
def needs_boom(x: Boom):
    return x


def test_parameter_mismatch_format():
    with pytest.raises(TypeCheckError) as exc:
        takes_int("abc")  # type: ignore[arg-type]
    msg = str(exc.value)
    assert "expected int" in msg and "got str" in msg


def test_custom_validator_traceback_preserved():
    with pytest.raises(RuntimeError) as exc:  # should not be wrapped in TypeCheckError
        needs_boom(Boom())
    assert "boom failure inner" in str(exc.value)


def test_fmt_type_angle_bracket_representation():
    """Integrated: ensure angle bracket <class 'pkg.Name'> style repr reduces to final component."""
    from typecheck.error_utils import fmt_type

    class _FakeAngle:
        def __str__(self):
            return "<class 'some.module.Funky'>"

    assert fmt_type(_FakeAngle()) == "Funky"
