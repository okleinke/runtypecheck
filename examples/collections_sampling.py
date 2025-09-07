"""Demonstrates collection element sampling vs deep vs default sampling behavior."""

from typecheck import TypeCheckError, typecheck


# Demonstrates sampling vs deep checking
@typecheck(sample=3)
def average_first(values: list[int]) -> float:
    # Only first 3 elements validated (sampling)
    return sum(values[:3]) / 3


@typecheck(deep=True)
def average_all(values: list[int]) -> float:
    # All elements validated (deep)
    return sum(values) / len(values)


if __name__ == "__main__":
    # In sampling mode only the first 3 elements are validated, so the stray "x" is not seen.
    print("Sampling mode (only first 3 validated):", average_first([1, 2, 3, "x", 5]))  # type: ignore
    try:
        # In deep mode every element is validated so the "x" will trigger an error.
        print("Deep mode (will raise):", average_all([1, 2, 3, "x", 5]))  # type: ignore
    except TypeCheckError as e:
        print("Deep check caught:", e)
