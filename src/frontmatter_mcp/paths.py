"""Locating Markdown files under the base directory."""

import glob
from collections.abc import Sequence
from fnmatch import fnmatchcase
from pathlib import Path

from fastmcp.exceptions import ToolError


def _match_parts(parts: Sequence[str], pattern: Sequence[str]) -> bool:
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(_match_parts(parts[i:], pattern[1:]) for i in range(len(parts) + 1))
    return (
        bool(parts)
        and fnmatchcase(parts[0], pattern[0])
        and _match_parts(parts[1:], pattern[1:])
    )


def is_excluded(rel_path: str, exclude: Sequence[str]) -> bool:
    """Whether a path relative to base_dir matches an exclude pattern.

    Patterns are globs relative to base_dir, like the tools' glob argument
    ("IDENTITY.md", "_templates", "**/drafts/*.md"). A pattern that matches a
    directory excludes everything under it.
    """
    parts = Path(rel_path).parts
    for pattern in exclude:
        pattern_parts = [p for p in pattern.split("/") if p]
        if any(
            _match_parts(parts[:k], pattern_parts) for k in range(1, len(parts) + 1)
        ):
            return True
    return False


def collect_files(
    base_dir: Path, pattern: str, exclude: Sequence[str] = ()
) -> list[Path]:
    """Files matching a glob pattern relative to base_dir, sorted.

    Matches that resolve outside base_dir (through "..", an absolute pattern,
    or a symlink) are dropped, as are excluded files. The pattern is matched
    with base_dir as the root, so glob characters in base_dir itself are not
    interpreted.
    """
    matches = glob.glob(pattern, root_dir=base_dir, recursive=True)
    files = [base_dir / m for m in matches if not is_excluded(m, exclude)]
    return sorted(
        p for p in files if p.is_file() and p.resolve().is_relative_to(base_dir)
    )


def list_markdown_files(base_dir: Path, exclude: Sequence[str] = ()) -> list[Path]:
    """All Markdown files to index.

    Skips dot directories (.obsidian, .git, caches) and excluded files.
    """
    files = []
    for p in base_dir.rglob("*.md"):
        rel = p.relative_to(base_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if not is_excluded(rel.as_posix(), exclude):
            files.append(p)
    return files


def resolve_file(base_dir: Path, rel_path: str, exclude: Sequence[str] = ()) -> Path:
    """Resolve a path given by the client to an existing file inside base_dir.

    Raises:
        ToolError: If the path leaves base_dir, is excluded, or the file does
            not exist.
    """
    abs_path = (base_dir / rel_path).resolve()
    if not abs_path.is_relative_to(base_dir):
        raise ToolError(f"Path must be within the base directory: {rel_path}")
    if is_excluded(abs_path.relative_to(base_dir).as_posix(), exclude):
        raise ToolError(f"Path is excluded by FRONTMATTER_EXCLUDE: {rel_path}")
    if not abs_path.is_file():
        raise ToolError(f"File not found: {rel_path}")
    return abs_path


def relative(base_dir: Path, path: Path) -> str:
    """Path relative to base_dir, as reported to the client."""
    return str(path.relative_to(base_dir))
