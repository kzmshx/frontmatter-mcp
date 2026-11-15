"""Writing frontmatter back to files without disturbing their formatting."""

import io
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import frontmatter
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from frontmatter_mcp.markdown import split_frontmatter


def read_metadata(path: Path) -> dict[str, Any]:
    """Frontmatter of a file as python-frontmatter parses it (YAML 1.1)."""
    return dict(frontmatter.load(path).metadata)


def apply_update(
    metadata: Mapping[str, Any],
    set_values: Mapping[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
    """Metadata with set_values applied and unset keys removed (unset wins)."""
    result = dict(metadata)
    removed = set(unset or [])
    for key, value in (set_values or {}).items():
        if key not in removed:
            result[key] = value
    for key in removed:
        result.pop(key, None)
    return result


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


def render(original: str, metadata: Mapping[str, Any]) -> str:
    """Apply metadata to the original text, changing only the keys that differ.

    The lines of unchanged keys are copied verbatim, so their formatting
    (flow or block lists, quotes, comments, line wrapping) stays exactly as it
    was. A replaced list keeps the style of the list it replaces; a new list
    follows the style already used in the file. The body is untouched.
    """
    yaml = _round_trip_yaml()
    parts = split_frontmatter(original)
    block, body = parts.block, parts.body
    opening = parts.opening or "---\n"
    closing = parts.closing or "---\n"
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


def write_metadata(path: Path, metadata: Mapping[str, Any]) -> bool:
    """Write metadata to a file's frontmatter without risking data loss.

    Only the keys whose values change are rewritten; everything else in the
    file, including the body, stays byte for byte (see render). Nothing is
    written when the text would not change, so the mtime is not bumped. The
    new text goes to a temporary file in the same directory that is then
    renamed over the original, so a failure leaves the original untouched.

    Returns:
        True if the file was written.
    """
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    text = render(original, metadata)
    if text == original:
        return False
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
    return True
