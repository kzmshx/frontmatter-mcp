"""Tests for splitting frontmatter from the body."""

from frontmatter_mcp.markdown import split_frontmatter


def test_split_with_frontmatter() -> None:
    parts = split_frontmatter("---\na: 1\n---\nBody\n")
    assert (parts.opening, parts.block, parts.closing, parts.body) == (
        "---\n",
        "a: 1\n",
        "---\n",
        "Body\n",
    )
    assert parts.body_line == 4


def test_split_without_frontmatter() -> None:
    parts = split_frontmatter("# Title\n")
    assert parts.block is None
    assert parts.body == "# Title\n"
    assert parts.body_line == 1


def test_unclosed_frontmatter_is_body() -> None:
    assert split_frontmatter("---\na: 1\n").block is None


def test_parts_join_back_to_original() -> None:
    text = "---  \nx: y\n---\n\n\nno trailing newline"
    p = split_frontmatter(text)
    assert p.opening + (p.block or "") + p.closing + p.body == text
