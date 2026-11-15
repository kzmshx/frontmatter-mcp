"""Tests for Markdown chunking."""

from frontmatter_mcp.semantic.chunking import (
    MAX_CHUNK_CHARS,
    chunk_markdown,
    split_body,
)

LONG = "This line is long enough to be kept as a chunk."


def test_split_body_skips_frontmatter() -> None:
    body, line = split_body("---\na: 1\n---\nBody\n")
    assert body == "Body\n"
    assert line == 4


def test_split_body_without_frontmatter() -> None:
    assert split_body("Body\n") == ("Body\n", 1)


def test_chunks_break_at_headings() -> None:
    text = f"---\nt: x\n---\n# One\n\n{LONG}\n\n## Two\n{LONG}\n"
    chunks = chunk_markdown(text)
    assert [c.heading for c in chunks] == ["One", "Two"]
    assert chunks[0].text == f"One\n{LONG}"
    assert [c.line for c in chunks] == [6, 9]


def test_long_sections_split_by_size() -> None:
    lines = "\n".join(f"- {i:03d} " + "x" * 50 for i in range(30))
    chunks = chunk_markdown(lines)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS + 60 for c in chunks)
    assert chunks[1].line > chunks[0].line


def test_short_fragments_dropped() -> None:
    assert chunk_markdown("# Heading\n\nok\n") == []


def test_text_without_heading() -> None:
    chunks = chunk_markdown(LONG)
    assert chunks[0].heading == ""
    assert chunks[0].text == LONG
    assert chunks[0].line == 1


def test_tag_lines_are_not_headings() -> None:
    chunks = chunk_markdown(f"#darts #mood\n{LONG}\n")
    assert chunks[0].heading == ""
    assert chunks[0].text.startswith("#darts #mood")


def test_hashes_inside_code_fences_are_not_headings() -> None:
    text = f"# Real\n\n```sh\n# not a heading\necho hi\n```\n{LONG}\n"
    chunks = chunk_markdown(text)
    assert [c.heading for c in chunks] == ["Real"]
    assert "# not a heading" in chunks[0].text


def test_closing_hashes_are_stripped() -> None:
    assert chunk_markdown(f"## Title ##\n{LONG}")[0].heading == "Title"


def test_section_is_the_heading_path() -> None:
    text = f"# Day\n## Notes\n### Sleep\n{LONG}\n## Log\n{LONG}\n"
    chunks = chunk_markdown(text)
    assert [c.section for c in chunks] == [("Day", "Notes", "Sleep"), ("Day", "Log")]
    assert [c.heading for c in chunks] == ["Sleep", "Log"]


def test_chunk_without_heading_has_empty_section() -> None:
    assert chunk_markdown(f"{LONG}\n")[0].section == ()


def test_chunks_of_only_embeds_or_links_are_dropped() -> None:
    text = (
        "## Pinned\n![[TASKS_WORK#^todo]]\n"
        "## Links\n- [[notes/2026-09-06]]\n- [x] [[a/b/laundry]]\n"
        "## Alias\n[[x|an alias long enough to count as text]]\n"
        "## Url\nhttps://example.com/a/very/long/path/that/is/not/text ^block-id\n"
    )
    assert [c.heading for c in chunk_markdown(text)] == ["Alias"]
