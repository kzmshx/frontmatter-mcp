"""Pure operations on array (list) frontmatter values.

Each function takes the current value of a property and returns the new
list, or None when the file should be left unchanged.
"""

from typing import Any


class NotAnArrayError(ValueError):
    """The property exists but is not an array."""


def _require_list(current: Any) -> list[Any]:
    if not isinstance(current, list):
        raise NotAnArrayError("not an array")
    return current


def add(current: Any, value: Any, allow_duplicates: bool = False) -> list[Any] | None:
    """Append value; create [value] when the property is missing."""
    if current is None:
        return [value]
    items = _require_list(current)
    if not allow_duplicates and value in items:
        return None
    return [*items, value]


def remove(current: Any, value: Any) -> list[Any] | None:
    """Remove every occurrence of value."""
    if current is None:
        return None
    items = _require_list(current)
    if value not in items:
        return None
    return [x for x in items if x != value]


def replace(current: Any, old_value: Any, new_value: Any) -> list[Any] | None:
    """Replace every occurrence of old_value with new_value."""
    if current is None:
        return None
    items = _require_list(current)
    if old_value not in items:
        return None
    return [new_value if x == old_value else x for x in items]


def sort(current: Any, reverse: bool = False) -> list[Any] | None:
    """Sort the array; values must be mutually comparable."""
    if current is None:
        return None
    items = _require_list(current)
    result = sorted(items, reverse=reverse)
    return None if result == items else result


def unique(current: Any) -> list[Any] | None:
    """Drop duplicates, keeping the first occurrence of each value."""
    if current is None:
        return None
    items = _require_list(current)
    result: list[Any] = []
    for x in items:
        if x not in result:
            result.append(x)
    return None if len(result) == len(items) else result
