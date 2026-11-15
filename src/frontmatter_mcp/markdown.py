"""Splitting Markdown text into frontmatter and body."""

from dataclasses import dataclass

DELIMITER = "---"


@dataclass(frozen=True)
class MarkdownParts:
    """A Markdown file split at its frontmatter delimiters.

    All parts are verbatim, so joining them gives back the original text.

    Attributes:
        opening: The opening delimiter line ("---\\n"), or "" without frontmatter.
        block: The YAML between the delimiters, or None without frontmatter.
        closing: The closing delimiter line, or "" without frontmatter.
        body: Everything after the closing delimiter (the whole text without
            frontmatter).
        body_line: 1-based line number where the body starts.
    """

    opening: str
    block: str | None
    closing: str
    body: str
    body_line: int


def split_frontmatter(text: str) -> MarkdownParts:
    """Split text at its frontmatter delimiters ("---" lines)."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].rstrip() == DELIMITER:
        for i in range(1, len(lines)):
            if lines[i].rstrip() == DELIMITER:
                return MarkdownParts(
                    opening=lines[0],
                    block="".join(lines[1:i]),
                    closing=lines[i],
                    body="".join(lines[i + 1 :]),
                    body_line=i + 2,
                )
    return MarkdownParts(opening="", block=None, closing="", body=text, body_line=1)
