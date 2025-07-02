"""Demonstrates config forward_ref_policy and fallback_policy behaviors."""
from __future__ import annotations

from typecheck import typecheck, config, TypeCheckError


@typecheck()
def permissive(x: "UnknownType") -> int:  # forward ref unresolved but permissive
    return 1


def demo_permissive():
    print("Permissive forward ref accepted:", permissive(123))


def demo_strict():
    config.set_forward_ref_policy("strict")
    try:
        @typecheck()
        def f(y: "NotDeclared") -> int:  # strict policy now active
            return 2
        f(1)  # noqa
    except TypeCheckError as e:
        print("Strict forward ref error:", e)
    finally:
        config.set_forward_ref_policy("permissive")


def demo_fallback_error():
    class FakeType:
        __module__ = "typing"  # pretend typing construct to trigger fallback path

    config.set_fallback_policy("error")
    try:
        @typecheck()
        def g(z: FakeType) -> None:  # type: ignore[valid-type]
            return None
        g(5)  # should raise
    except TypeCheckError as e:
        print("Fallback policy error:", e)
    finally:
        config.set_fallback_policy("silent")


if __name__ == "__main__":
    demo_permissive()
    demo_strict()
    demo_fallback_error()
