"""Basic usage of @typecheck: validates simple parameter and return types."""

from typecheck import typecheck


@typecheck()
def greet(name: str, times: int) -> str:
    return " ".join([f"Hello {name}!"] * times)


if __name__ == "__main__":
    print(greet("Alice", 2))
