from typing import Dict, List, Optional, Union

import pytest

from typecheck import TypeCheckError, typecheck


def test_return_value_simple():
    @typecheck()
    def return_int(x: int) -> int:
        return x * 2

    @typecheck()
    def return_str(x: str) -> str:
        return x.upper()

    @typecheck()
    def return_list(items: List[str]) -> List[str]:
        return [i.upper() for i in items]

    assert return_int(5) == 10
    assert return_str("a") == "A"
    assert return_list(["a", "b"]) == ["A", "B"]

    @typecheck()
    def bad_return_int(x: int) -> int:
        return str(x)  # type: ignore[return-value]

    with pytest.raises(TypeCheckError):
        bad_return_int(5)


def test_return_value_union_optional():
    @typecheck()
    def return_union(flag: bool) -> Union[int, str]:
        return 42 if flag else "x"

    assert isinstance(return_union(True), int)
    assert isinstance(return_union(False), str)

    @typecheck()
    def bad_return_union(flag: bool) -> Union[int, str]:
        return [1, 2, 3]  # type: ignore[return-value]

    with pytest.raises(TypeCheckError):
        bad_return_union(True)

    @typecheck()
    def return_optional(flag: bool) -> Optional[str]:
        return "hi" if flag else None

    assert return_optional(True) == "hi"
    assert return_optional(False) is None

    @typecheck()
    def bad_return_optional(flag: bool) -> Optional[str]:
        return 1  # type: ignore[return-value]

    with pytest.raises(TypeCheckError):
        bad_return_optional(True)


def test_return_value_complex():
    @typecheck()
    def return_complex() -> Dict[str, List[int]]:
        return {"n": [1, 2, 3]}

    assert return_complex() == {"n": [1, 2, 3]}

    @typecheck()
    def bad_return_complex() -> Dict[str, List[int]]:
        return {"n": [1, 2, "3"]}  # type: ignore[list-item]

    with pytest.raises(TypeCheckError):
        bad_return_complex()


def test_return_value_none_and_explicit():
    @typecheck()
    def no_return_annotation(x: int):
        return "anything"

    assert no_return_annotation(1) == "anything"

    @typecheck()
    def explicit_none(x: int) -> None:
        return "oops"  # type: ignore[return-value]

    with pytest.raises(TypeCheckError):
        explicit_none(1)


def test_return_value_error_message_rewrite_and_strict_missing():
    # Trigger return value mismatch inside container to exercise rewrite branch (lines ~196-201)
    @typecheck()
    def bad_ret() -> list[int]:  # expecting list[int]
        return {"a": 1}  # type: ignore[return-value]

    raised = False
    try:
        bad_ret()
    except TypeCheckError as e:
        raised = True
        assert "Return value type mismatch" in str(e)
    assert raised

    # Missing return annotation with strict + strict_return
    @typecheck(strict=True, strict_return=True)
    def no_ret_annot(x: int):  # no return annotation
        return 1

    with pytest.raises(TypeCheckError):
        no_ret_annot(5)


def test_typecheck_sample_and_nonint_coercion_and_return_message_normalization():
    """Merged from former test_typecheck_extra file: sample arg non-int and return mismatch normalization."""
    from typecheck import TypeCheckError, typecheck

    @typecheck(sample="x")  # type: ignore[arg-type]
    def f(a: int) -> int:
        return a

    assert f(1) == 1

    @typecheck()
    def g() -> int:
        return "s"  # type: ignore[return-value]

    with pytest.raises(TypeCheckError) as exc:
        g()
    assert "Return value type mismatch" in str(exc.value)
