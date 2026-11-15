"""Split Markdown into chunks for semantic search."""

import re
from dataclasses import dataclass

from frontmatter_mcp.markdown import split_frontmatter

# Target chunk size in characters. A single line longer than this becomes its
# own chunk rather than being cut in the middle of a sentence.
MAX_CHUNK_CHARS = 400
# Chunks with less text than this carry too little to match on. Counted
# without the heading, links, list markers and whitespace (see _text_length)
MIN_CHUNK_CHARS = 20
# ATX heading. "#tag" (Obsidian tags) has no space after the hashes
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")

# Markup that is not text a query can match: embeds, link targets, URLs,
# block ids, list and checkbox markers
_EMBED = re.compile(r"!\[\[[^\]]*\]\]")
_WIKILINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
_MDLINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_BLOCK_ID = re.compile(r"\s\^[\w-]+$|^\^[\w-]+$", re.MULTILINE)
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[.\]\s*)?", re.MULTILINE)


def _link_label(match: re.Match[str]) -> str:
    """What Obsidian shows for a wiki link: the alias, or the note name."""
    if match.group(2):
        return match.group(2)
    target = match.group(1).split("#", 1)[0]
    return target.rsplit("/", 1)[-1]


def _text_length(content: str) -> int:
    """Characters of readable text, without markup and whitespace.

    A chunk that is only an embed (``![[TASKS#^todo]]``) or a list of links
    has nothing of its own to match a query on.
    """
    text = _EMBED.sub("", content)
    text = _WIKILINK.sub(_link_label, text)
    text = _MDLINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _BLOCK_ID.sub("", text)
    text = _LIST_MARKER.sub("", text)
    return len("".join(text.split()))


@dataclass(frozen=True)
class Chunk:
    """A piece of a document.

    Attributes:
        line: 1-based line number in the file where the chunk starts.
        heading: Nearest heading above the chunk ("" if none).
        text: Chunk text, prefixed with the heading so it stands on its own.
        section: Headings from the top level down to the nearest one, e.g.
            ("Daily", "AI comments", "Sleep"). Empty if there is no heading.
    """

    line: int
    heading: str
    text: str
    section: tuple[str, ...] = ()


def split_body(text: str) -> tuple[str, int]:
    """Return (body, 1-based line number where the body starts)."""
    parts = split_frontmatter(text)
    return parts.body, parts.body_line


def chunk_markdown(text: str) -> list[Chunk]:
    """Split a Markdown file (frontmatter included) into chunks.

    Chunks break at headings and otherwise collect whole lines up to
    MAX_CHUNK_CHARS. Each chunk's text starts with its heading. Chunks with
    little text of their own (MIN_CHUNK_CHARS) are dropped.
    """
    body, first_line = split_body(text)
    chunks: list[Chunk] = []
    # (level, title) of the headings enclosing the current line
    stack: list[tuple[int, str]] = []
    current: list[str] = []
    start = first_line

    def flush() -> None:
        content = "\n".join(current).strip()
        if _text_length(content) >= MIN_CHUNK_CHARS:
            section = tuple(title for _, title in stack)
            heading = section[-1] if section else ""
            text_ = f"{heading}\n{content}" if heading else content
            chunks.append(
                Chunk(line=start, heading=heading, text=text_, section=section)
            )
        current.clear()

    in_fence = False
    for offset, line in enumerate(body.splitlines()):
        lineno = first_line + offset
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (match := _HEADING.match(line)):
            flush()
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
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
