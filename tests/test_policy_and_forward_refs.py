import pytest

from typecheck import TypeCheckError, config, typecheck


def test_forward_ref_permissive_default():
    @typecheck()
    def f(x: "UnknownType"):  # type: ignore[valid-type]
        return x

    assert f(1) == 1  # accepted


def test_forward_ref_strict_error():
    config.set_forward_ref_policy("strict")

    @typecheck()
    def g(x: "NotDeclared"):  # type: ignore[valid-type]
        return x

    with pytest.raises(TypeCheckError):
        g(1)
    config.set_forward_ref_policy("permissive")  # reset


def test_fallback_policy_error():
    class Exotic: ...

    # Build an object unlikely to be recognized: use a custom descriptor container
    config.set_fallback_policy("error")

    @typecheck()
    def h(x: "UnresolvedAlso"):  # type: ignore[valid-type]  # forward ref permissive path
        return x

    # Fallback policy error triggers on unsupported construct path; simulate by passing a made-up typing-like object
    class FakeType:
        __module__ = "typing"

    @typecheck()
    def k(x: FakeType):  # type: ignore[valid-type]
        return x

    with pytest.raises(TypeCheckError):
        k(1)
    config.set_fallback_policy("silent")


def test_forward_ref_annotation_mutation_after_decoration():
    @typecheck()
    def mutate_annot(x):
        return x

    mutate_annot.__annotations__["x"] = "NonExistentType"  # type: ignore[index]
    assert mutate_annot(123) == 123
