"""Adjusts global config (sample size, strict mode) and demonstrates effects."""

from typecheck import typecheck, config, TypeCheckError

# Adjust global defaults
config.sample_size = 2
config.strict_mode = True


@typecheck()
def combine(a: int, b: int, note: str) -> str:
    return f"{a + b} ({note})"


if __name__ == "__main__":
    print(combine(2, 3, "ok"))
    try:
        print(combine(2, "x", "fail"))  # type: ignore
    except TypeCheckError as e:
        print("Caught:", e)
