import pytest

from typecheck import TypeCheckError, typecheck


def test_class_include_exclude_and_ignore():
    @typecheck(include=["a", "b"], exclude=["b"])
    class Demo:
        def a(self, x: int) -> int:
            return x

        def b(self, x: int) -> int:  # excluded
            return x

        def c(self, x: int) -> int:  # not in include list
            return x

    d = Demo()
    d.a(1)
    d.b("x")  # type: ignore[arg-type]  # not wrapped
    d.c("x")  # type: ignore[arg-type]  # not wrapped
    with pytest.raises(TypeCheckError):
        d.a("x")  # type: ignore[arg-type]


def test_method_level_ignore():
    @typecheck()
    class Demo2:
        @typecheck(ignore=True)
        def a(self, x: int) -> int:
            return x

        def b(self, x: int) -> int:
            return x

    obj = Demo2()
    obj.a("x")  # type: ignore[arg-type]  # ignored
    with pytest.raises(TypeCheckError):
        obj.b("x")  # type: ignore[arg-type]


def test_class_include_exclude_and_ignore_additional():
    calls = {}

    @typecheck()
    def ignored(self, x):  # will be attached after marking ignore
        calls["ignored"] = x

    ignored.__typecheck_ignored__ = True  # type: ignore[attr-defined]  # simulate @typecheck(ignore=True)

    class C:
        @typecheck()
        def a(self, x: int):
            return x

        def _hidden(self, x: int):
            return x

        def b(self, y: str):  # param name mismatch; not included
            return y

        c = ignored

    C = typecheck(include=["a", "c"])(C)
    inst = C()
    assert inst.a(3) == 3
    inst.c(1.23)  # ignored -> accepts any
    inst._hidden(10)  # not wrapped
    inst.b("x")  # not wrapped
