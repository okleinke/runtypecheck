from collections import ChainMap, Counter, OrderedDict, defaultdict, deque
from typing import Dict, List, Optional, Tuple

from typecheck import TypeCheckError, typecheck

# Containers and nested generics


def test_list_and_set_and_tuple():
    @typecheck()
    def list_func(numbers: List[int], strings: List[str]) -> int:
        return len(numbers) + len(strings)

    assert list_func([1, 2, 3], ["a", "b"]) == 5
    try:
        list_func([1, 2, "3"], ["a", "b"])  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def needs_list(x: list[int]):
        return x

    from typecheck import TypeCheckError as _TCE  # local to avoid top import churn

    try:
        needs_list((1, 2))  # type: ignore[arg-type]
    except _TCE:
        pass
    else:
        assert False

    @typecheck()
    def tuple_func(coord: Tuple[int, int], data: Tuple[str, ...]) -> str:
        return f"{coord}-{data}"

    assert tuple_func((1, 2), ("a", "b"))
    try:
        tuple_func((1, 2, 3), ("a", "b"))  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck(deep=True)
    def set_func(s: set[int]) -> int:
        return len(s)

    try:
        set_func({1, 2, "x"})  # type: ignore[set-item]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def tuple_variadic(t: Tuple[int, ...]) -> int:
        return len(t)

    try:
        tuple_variadic(("x",))  # type: ignore[tuple-item]
    except TypeCheckError:
        pass
    else:
        assert False


def test_dict_and_mapping_and_ordered():
    @typecheck()
    def dict_func(mapping: Dict[str, int]) -> int:
        return sum(mapping.values())

    assert dict_func({"a": 1, "b": 2}) == 3
    try:
        dict_func({1: 1, "b": 2})  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    try:
        dict_func({"a": "bad"})  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def ordered_func(od: OrderedDict[str, int]) -> int:
        return len(od)

    assert ordered_func(OrderedDict([("a", 1)])) == 1
    try:
        ordered_func({"a": 1})  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False


def test_nested_generics_and_complex():
    @typecheck()
    def nested_func(data: List[Dict[str, int]]) -> int:
        return sum(sum(d.values()) for d in data)

    assert nested_func([{"a": 1}, {"b": 2}]) == 3
    try:
        nested_func([{"a": "bad"}])  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def complex_func(data: Dict[str, List[Tuple[int, Optional[str]]]]) -> str:
        return str(len(data))

    assert complex_func({"g": [(1, None)]}) == "1"
    try:
        complex_func({"g": [("bad", None)]})  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def tuple_index(t: Tuple[int, str, float]):
        return 1

    try:
        tuple_index((1, 2, 3.0))  # type: ignore[arg-type]
    except TypeCheckError as e:
        assert "t[1]" in str(e)
    else:
        assert False


def test_counter_chainmap_defaultdict():
    @typecheck()
    def counter_func(c: Counter[str]) -> int:
        return sum(c.values())

    assert counter_func(Counter(["a", "a", "b"])) == 3
    try:
        counter_func(Counter([1, 2]))  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    # Deque and frozenset
    @typecheck()
    def deque_func(d: deque[int]) -> int:  # type: ignore[type-arg]
        return len(d)

    assert deque_func(deque([1, 2])) == 2
    try:
        deque_func(deque(["x"]))  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def frozenset_func(s: frozenset[int]) -> int:  # type: ignore[type-arg]
        return sum(s)

    assert frozenset_func(frozenset({1, 2})) == 3
    try:
        frozenset_func(frozenset({"a"}))  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def chainmap_func(cm: ChainMap[str, int]) -> int:
        return sum(cm.values())

    assert chainmap_func(ChainMap({"x": 1}, {"y": 2})) == 3
    try:
        chainmap_func(ChainMap({1: 1}))  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False

    @typecheck()
    def dd_func(d: defaultdict[str, int]) -> int:
        return sum(d.values())

    dd = defaultdict(int)
    dd["a"] = 1
    assert dd_func(dd) == 1
    bad = defaultdict(int)
    bad[1] = 1  # type: ignore[index]
    try:
        dd_func(bad)  # type: ignore[arg-type]
    except TypeCheckError:
        pass
    else:
        assert False
