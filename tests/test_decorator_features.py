from typing import List

from typecheck import TypeCheckError, typecheck


def test_class_and_method_decoration():
    @typecheck()
    class Calculator:
        def add(self, a: int, b: int) -> int:
            return a + b

        def divide(self, a: float, b: float) -> float:
            if b == 0:
                raise ValueError("div0")
            return a / b

        def process_list(self, items: List[str]) -> int:
            return len(items)

    c = Calculator()
    assert c.add(1, 2) == 3
    assert c.divide(4.0, 2.0) == 2.0
    assert c.process_list(["a"]) == 1
    for bad in [lambda: c.add("1", 2), lambda: c.process_list([1, 2, 3])]:  # type: ignore[arg-type]
        try:
            bad()
        except TypeCheckError:
            pass
        else:
            assert False

    # Descriptor preservation (static, class, instance methods)
    @typecheck()
    class WithDescriptors:
        @staticmethod
        def static_add(a: int, b: int) -> int:
            return a + b

        @classmethod
        def cls_name(cls) -> str:
            return cls.__name__

        def inst(self, x: int) -> int:
            return x * 2

    assert WithDescriptors.static_add(1, 2) == 3
    assert WithDescriptors.cls_name() == "WithDescriptors"
    assert WithDescriptors().inst(3) == 6


def test_method_only_decoration():
    class T:
        @typecheck()
        def typed(self, x: int, y: str) -> str:
            return f"{x}-{y}"

        def untyped(self, x, y):
            return f"{x}-{y}"

    t = T()
    assert t.typed(1, "a") == "1-a"
    try:
        t.typed("1", "a")  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False


def test_sampling_and_deep():
    @typecheck(sample=2)
    def sampled(items: List[int]) -> int:
        return len(items)

    assert sampled([1, 2, 3, "bad"]) == 4  # type: ignore[list-item]

    @typecheck(deep=True)
    def deep(items: List[int]) -> int:
        return len(items)

    try:
        deep([1, 2, 3, "bad"])  # type: ignore[list-item]
    except TypeCheckError:
        pass
    else:
        assert False

    from typing import Dict

    @typecheck(deep=True)
    def mapping(m: Dict[int, str]):
        return 1

    for bad in [{"a": "x"}, {1: 2}]:  # type: ignore[arg-type]
        try:
            mapping(bad)  # type: ignore[arg-type]
        except TypeCheckError:
            pass
        else:
            assert False

    from typecheck import config

    config.lazy_iterable_validation = False

    @typecheck(deep=False)
    def consume(it: List[int]):
        return 1

    try:
        consume([1, "bad", 3])  # type: ignore[list-item]
    except TypeCheckError:
        pass
    else:
        assert False
