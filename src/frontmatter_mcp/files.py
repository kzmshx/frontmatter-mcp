"""Frontmatter read/write module."""

import io
import os
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import frontmatter
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

# Type alias for frontmatter parse result
FileRecord = dict[str, Any]


class FileRecordCacheEntry(NamedTuple):
    """Cache entry storing mtime and parsed record."""

    mtime: float
    record: FileRecord


class FileRecordCache:
    """mtime-based in-memory frontmatter cache."""

    def __init__(self) -> None:
        self._cache: dict[str, FileRecordCacheEntry] = {}

    def get(self, path: Path, base_dir: Path) -> FileRecord | None:
        """Return cached record if valid, None otherwise."""
        rel_path = str(path.relative_to(base_dir))
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return None
        if (entry := self._cache.get(rel_path)) and entry.mtime == mtime:
            return entry.record
        return None

    def set(self, path: Path, base_dir: Path, record: FileRecord) -> None:
        """Add or update cache entry."""
        rel_path = str(path.relative_to(base_dir))
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return
        self._cache[rel_path] = FileRecordCacheEntry(mtime, record)

    def invalidate(self, paths: list[Path], base_dir: Path) -> None:
        """Remove cache entries for specified paths."""
        for path in paths:
            rel_path = str(path.relative_to(base_dir))
            self._cache.pop(rel_path, None)


def parse_file(path: Path, base_dir: Path) -> FileRecord:
    """Parse frontmatter from a single file.

    Args:
        path: Absolute path to the file.
        base_dir: Base directory for relative path calculation.

    Returns:
        Dictionary with 'path' (relative) and frontmatter properties.
    """
    post = frontmatter.load(path)
    result: dict[str, Any] = {
        "path": str(path.relative_to(base_dir)),
    }
    result.update(post.metadata)
    return result


def parse_files(
    paths: list[Path],
    base_dir: Path,
    cache: FileRecordCache,
) -> tuple[list[FileRecord], list[dict[str, str]]]:
    """Parse frontmatter from multiple files with caching.

    Args:
        paths: List of absolute paths to files.
        base_dir: Base directory for relative path calculation.
        cache: Cache instance for mtime-based caching.

    Returns:
        Tuple of (parsed records, warnings for failed files).
    """
    records: list[FileRecord] = []
    warnings: list[dict[str, str]] = []

    for path in paths:
        # Check cache first
        if (record := cache.get(path, base_dir)) is not None:
            records.append(record)
            continue

        # Cache miss: parse and store
        try:
            record = parse_file(path, base_dir)
            records.append(record)
            cache.set(path, base_dir, record)
        except Exception as e:
            warnings.append(
                {
                    "path": str(path.relative_to(base_dir)),
                    "error": str(e),
                }
            )

    return records, warnings


def _split_frontmatter(text: str) -> tuple[str, str | None, str, str]:
    """Split text into (opening line, YAML block, closing line, body).

    The block is None when the text has no frontmatter. Delimiter lines and the
    body are returned verbatim so they can be written back byte for byte.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return "---\n", None, "---\n", text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return lines[0], "".join(lines[1:i]), lines[i], "".join(lines[i + 1 :])
    return "---\n", None, "---\n", text


def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # never wrap long values
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


def _has_flow_sequence(node: Any) -> bool:
    if isinstance(node, CommentedSeq):
        return bool(node.fa.flow_style()) or any(_has_flow_sequence(v) for v in node)
    if isinstance(node, CommentedMap):
        return any(_has_flow_sequence(v) for v in node.values())
    return False


def _styled(value: Any, old: Any, flow_default: bool, old_text: str = "") -> Any:
    """Wrap a new list so it keeps the style of the value it replaces."""
    if not isinstance(value, list):
        return value
    seq = CommentedSeq(value)
    if isinstance(old, CommentedSeq):
        # ruamel does not mark an empty `[]` as flow, so also look at the source
        value_text = old_text.split(":", 1)[-1].strip()
        flow = bool(old.fa.flow_style()) or value_text.startswith("[")
    else:
        flow = flow_default
    if flow:
        seq.fa.set_flow_style()
    else:
        seq.fa.set_block_style()
    return seq


def _is_filler(line: str) -> bool:
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _seq_offset(lines: list[str]) -> int | None:
    """Indentation of the first block-list item ("- a" is 0, "  - a" is 2)."""
    for line in lines:
        stripped = line.lstrip(" ")
        if stripped.startswith("- ") or stripped.rstrip() == "-":
            return len(line) - len(stripped)
    return None


def _dump_key(key: str, value: Any, seq_offset: int) -> str:
    yaml = _round_trip_yaml()
    yaml.indent(mapping=2, sequence=seq_offset + 2, offset=seq_offset)
    out = io.StringIO()
    yaml.dump(CommentedMap([(key, value)]), out)
    return out.getvalue()


def _render(original: str, metadata: dict[str, Any]) -> str:
    """Apply metadata to the original text, changing only the keys that differ.

    The lines of unchanged keys are copied verbatim, so their formatting
    (flow or block lists, quotes, comments, line wrapping) stays exactly as it
    was. A replaced list keeps the style of the list it replaces; a new list
    follows the style already used in the file. The body is untouched.
    """
    yaml = _round_trip_yaml()
    opening, block, closing, body = _split_frontmatter(original)
    # Compare against the values callers saw (python-frontmatter parses YAML 1.1,
    # ruamel parses 1.2, and they disagree on scalars such as `On` or `yes`)
    try:
        before = frontmatter.loads(original).metadata if block is not None else {}
    except Exception:
        before = {}
    doc = yaml.load(block) if block and block.strip() else None
    if not isinstance(doc, CommentedMap):
        doc = CommentedMap()
        block_lines: list[str] = []
    else:
        block_lines = (block or "").splitlines(keepends=True)
    flow_default = _has_flow_sequence(doc)
    offset_default = _seq_offset(block_lines) or 0

    keys = list(doc.keys())
    starts = [doc.lc.key(k)[0] for k in keys]
    head = block_lines[: starts[0]] if keys else block_lines
    pieces: list[str] = list(head)
    for i, key in enumerate(keys):
        seg_end = starts[i + 1] if i + 1 < len(keys) else len(block_lines)
        segment = block_lines[starts[i] : seg_end]
        # Blank and comment lines after the value stay even if the value changes
        value_end = len(segment)
        while value_end > 1 and _is_filler(segment[value_end - 1]):
            value_end -= 1
        trailing = segment[value_end:]
        if key not in metadata:
            pieces.extend(trailing)
            continue
        old, value = doc[key], metadata[key]
        if key in before and before[key] == value:
            pieces.extend(segment)
            continue
        offset = None
        if isinstance(old, CommentedSeq):
            offset = _seq_offset(segment[:value_end])
        if offset is None:
            offset = offset_default
        styled = _styled(value, old, flow_default, segment[0])
        pieces.append(_dump_key(key, styled, offset))
        pieces.extend(trailing)
    for key, value in metadata.items():
        if key not in doc:
            if pieces and not pieces[-1].endswith("\n"):
                pieces[-1] += "\n"
            styled = _styled(value, None, flow_default)
            pieces.append(_dump_key(key, styled, offset_default))

    new_block = "".join(pieces)
    if not metadata:
        return body
    if new_block and not new_block.endswith("\n"):
        new_block += "\n"
    return f"{opening}{new_block}{closing}{body}"


def write_post(path: Path, post: frontmatter.Post) -> None:
    """Write a post's metadata back to its file without risking data loss.

    Only the frontmatter keys that changed are rewritten; everything else in
    the file, including the body, stays as it was (see _render). The new
    content is written to a temporary file in the same directory and then
    atomically renamed over the original, so a failure leaves the original
    file untouched.

    Args:
        path: Absolute path to the file.
        post: Post whose metadata should be written. Its content is ignored;
            the body is taken from the file on disk.
    """
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    text = _render(original, dict(post.metadata))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def update_file(
    path: Path,
    base_dir: Path,
    set_values: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
    """Update frontmatter in a single file.

    Args:
        path: Absolute path to the file.
        base_dir: Base directory for relative path calculation.
        set_values: Properties to add or overwrite.
        unset: Property names to remove.

    Returns:
        Dictionary with 'path' (relative) and 'frontmatter' (updated metadata).
    """
    post = frontmatter.load(path)

    # Apply set values
    if set_values:
        for key, value in set_values.items():
            # Skip if key is in unset (unset takes priority)
            if unset and key in unset:
                continue
            post.metadata[key] = value

    # Apply unset
    if unset:
        for key in unset:
            post.metadata.pop(key, None)

    # Only write if there were changes
    if set_values or unset:
        write_post(path, post)

    return {
        "path": str(path.relative_to(base_dir)),
        "frontmatter": dict(post.metadata),
    }
