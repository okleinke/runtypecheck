"""Class decoration showcasing include/exclude filters and ignored methods.

Demonstrates:
- Decorating a class once instead of each method.
- include= / exclude= filters.
- Opting a specific method out with @typecheck(ignore=True).
- Handling staticmethod and classmethod.
"""
from __future__ import annotations

from typecheck import typecheck, TypeCheckError


@typecheck(include=["area", "perimeter", "make_square"], exclude=["perimeter"])
class Rectangle:
    def __init__(self, w: float, h: float):
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h

    def perimeter(self) -> float:  # excluded by decorator arguments
        return 2 * (self.w + self.h)

    @staticmethod
    def make_square(side: float) -> "Rectangle":
        return Rectangle(side, side)

    @typecheck(ignore=True)  # opted out
    def debug(self, flag) -> None:  # no annotations, but ignored
        if flag:
            print(f"Rectangle({self.w},{self.h})")


@typecheck()
class Circle:
    def __init__(self, r: float):
        self.r = r

    def area(self) -> float:
        return 3.14159 * self.r * self.r

    @classmethod
    def unit(cls) -> "Circle":
        return cls(1.0)


if __name__ == "__main__":
    rect = Rectangle(3.0, 4.0)
    print("Area:", rect.area())
    rect.debug(True)  # ignored method
    c = Circle.unit()
    print("Circle area:", c.area())
    try:
        Rectangle.make_square("bad")  # type: ignore[arg-type]
    except TypeCheckError as e:
        print("Caught include-filtered staticmethod error:", e)
