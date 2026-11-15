"""Split Markdown into chunks for semantic search."""

import re
from dataclasses import dataclass

from frontmatter_mcp.markdown import split_frontmatter

# Target chunk size in characters. A single line longer than this becomes its
# own chunk rather than being cut in the middle of a sentence.
MAX_CHUNK_CHARS = 400
# Chunks shorter than this (after the heading) carry too little to match on
MIN_CHUNK_CHARS = 20
# ATX heading. "#tag" (Obsidian tags) has no space after the hashes
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    """A piece of a document.

    Attributes:
        line: 1-based line number in the file where the chunk starts.
        heading: Nearest heading above the chunk ("" if none).
        text: Chunk text, prefixed with the heading so it stands on its own.
    """

    line: int
    heading: str
    text: str


def split_body(text: str) -> tuple[str, int]:
    """Return (body, 1-based line number where the body starts)."""
    parts = split_frontmatter(text)
    return parts.body, parts.body_line


def chunk_markdown(text: str) -> list[Chunk]:
    """Split a Markdown file (frontmatter included) into chunks.

    Chunks break at headings and otherwise collect whole lines up to
    MAX_CHUNK_CHARS. Each chunk's text starts with its heading.
    """
    body, first_line = split_body(text)
    chunks: list[Chunk] = []
    heading = ""
    current: list[str] = []
    start = first_line

    def flush() -> None:
        content = "\n".join(current).strip()
        if len(content) >= MIN_CHUNK_CHARS:
            text_ = f"{heading}\n{content}" if heading else content
            chunks.append(Chunk(line=start, heading=heading, text=text_))
        current.clear()

    in_fence = False
    for offset, line in enumerate(body.splitlines()):
        lineno = first_line + offset
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (match := _HEADING.match(line)):
            flush()
            heading = match.group(1)
            start = lineno + 1
            continue
        if current and sum(len(x) for x in current) + len(line) > MAX_CHUNK_CHARS:
            flush()
        if not current:
            if not line.strip():
                start = lineno + 1
                continue
            start = lineno
        current.append(line)
    flush()
    return chunks
