from collections.abc import Iterable

from typecheck import TypeCheckError, config, typecheck


def make_generator(values):
    for v in values:
        yield v


def test_lazy_validation_generator_pass():
    config.reset()
    config.lazy_iterable_validation = True

    @typecheck()
    def consume(gen: Iterable[int], nums: list[int]):
        return sum(nums)

    # baseline simple list usage (unrelated)
    assert consume([], [1, 2, 3]) == 6


def test_lazy_validation_generator_failure_on_iteration():
    config.reset()
    config.lazy_iterable_validation = True

    @typecheck()
    def sum_gen(gen: Iterable[int]):  # expecting ints
        return sum(gen)

    # Third element invalid; should raise during iteration not decoration
    g = make_generator([1, 2, "bad"])  # type: ignore[arg-type]
    raised = False
    try:
        sum_gen(g)  # will iterate and should trigger validation lazily on third element
    except TypeCheckError:
        raised = True
    assert raised, "Expected TypeCheckError from lazy generator element"


def test_iterator_sampling_negative_case():

    @typecheck(sample=2)
    def takes_iter(it: Iterable[int]) -> int:
        return 1

    def bad_iter():
        yield 1
        yield "x"  # type: ignore
        yield 3

    raised = False
    try:
        takes_iter(bad_iter())  # type: ignore[arg-type]
    except TypeCheckError:
        raised = True
    assert raised
