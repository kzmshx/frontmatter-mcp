"""Locating Markdown files under the base directory."""

import glob
from pathlib import Path

from fastmcp.exceptions import ToolError


def collect_files(base_dir: Path, pattern: str) -> list[Path]:
    """Files matching a glob pattern relative to base_dir, sorted.

    Matches that resolve outside base_dir (through "..", an absolute pattern,
    or a symlink) are dropped. The pattern is matched with base_dir as the
    root, so glob characters in base_dir itself are not interpreted.
    """
    matches = glob.glob(pattern, root_dir=base_dir, recursive=True)
    files = [base_dir / m for m in matches]
    return sorted(
        p for p in files if p.is_file() and p.resolve().is_relative_to(base_dir)
    )


def list_markdown_files(base_dir: Path) -> list[Path]:
    """All Markdown files, skipping dot directories (.obsidian, .git, caches)."""
    return [
        p
        for p in base_dir.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(base_dir).parts)
    ]


def resolve_file(base_dir: Path, rel_path: str) -> Path:
    """Resolve a path given by the client to an existing file inside base_dir.

    Raises:
        ToolError: If the path leaves base_dir or the file does not exist.
    """
    abs_path = (base_dir / rel_path).resolve()
    if not abs_path.is_relative_to(base_dir):
        raise ToolError(f"Path must be within the base directory: {rel_path}")
    if not abs_path.is_file():
        raise ToolError(f"File not found: {rel_path}")
    return abs_path


def relative(base_dir: Path, path: Path) -> str:
    """Path relative to base_dir, as reported to the client."""
    return str(path.relative_to(base_dir))
