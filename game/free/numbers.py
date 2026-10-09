"""Numbers in the free assets' JSON: an integer, or a string in any base
Python reads ("0x8C", "140")."""

from typing import Any


def num(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def nums(values: Any) -> tuple[int, ...]:
    return tuple(num(v) for v in values)


def pairs(values: Any) -> tuple[tuple[int, int], ...]:
    return tuple((num(a), num(b)) for a, b in values)
