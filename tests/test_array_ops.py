"""Tests for the array operations behind the batch_array_* tools."""

import pytest

from frontmatter_mcp import array_ops


def test_add() -> None:
    assert array_ops.add(None, "a") == ["a"]
    assert array_ops.add(["a"], "b") == ["a", "b"]
    assert array_ops.add(["a"], "a") is None
    assert array_ops.add(["a"], "a", allow_duplicates=True) == ["a", "a"]


def test_remove_every_occurrence() -> None:
    assert array_ops.remove(["a", "b", "a"], "a") == ["b"]
    assert array_ops.remove(["b"], "a") is None
    assert array_ops.remove(None, "a") is None


def test_replace_every_occurrence() -> None:
    assert array_ops.replace(["a", "b", "a"], "a", "c") == ["c", "b", "c"]
    assert array_ops.replace(["b"], "a", "c") is None


def test_sort() -> None:
    assert array_ops.sort(["b", "a"]) == ["a", "b"]
    assert array_ops.sort(["a", "b"]) is None
    assert array_ops.sort(["a", "b"], reverse=True) == ["b", "a"]
    assert array_ops.sort([]) is None
    with pytest.raises(TypeError):
        array_ops.sort(["a", 1])


def test_unique_keeps_first_occurrence() -> None:
    assert array_ops.unique(["b", "a", "b"]) == ["b", "a"]
    assert array_ops.unique(["a", "b"]) is None


@pytest.mark.parametrize(
    "call",
    [
        lambda: array_ops.add("x", "a"),
        lambda: array_ops.remove("x", "a"),
        lambda: array_ops.replace("x", "a", "b"),
        lambda: array_ops.sort("x"),
        lambda: array_ops.unique("x"),
    ],
)
def test_not_an_array(call: object) -> None:
    with pytest.raises(array_ops.NotAnArrayError):
        call()  # type: ignore[operator]
