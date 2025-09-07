"""Enforces strict return annotation presence and return value type checking."""

from typecheck import TypeCheckError, config, typecheck

config.strict_return_mode = True
config.strict_mode = True


@typecheck()
def make_label(x: int) -> str:
    return f"Label:{x}"


@typecheck()
def bad_label(x: int):  # missing return annotation
    return f"Bad:{x}"


if __name__ == "__main__":
    print(make_label(5))
    try:
        bad_label(5)
    except TypeCheckError as e:
        print("Caught strict return:", e)
