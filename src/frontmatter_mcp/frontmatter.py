"""Frontmatter read/write module."""

from pathlib import Path
from typing import Any

import frontmatter


def parse_file(path: Path, base_dir: Path) -> dict[str, Any]:
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
    paths: list[Path], base_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Parse frontmatter from multiple files.

    Args:
        paths: List of absolute paths to files.
        base_dir: Base directory for relative path calculation.

    Returns:
        Tuple of (parsed records, warnings for failed files).
    """
    records: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for path in paths:
        try:
            record = parse_file(path, base_dir)
            records.append(record)
        except Exception as e:
            warnings.append(
                {
                    "path": str(path.relative_to(base_dir)),
                    "error": str(e),
                }
            )

    return records, warnings


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
        with open(path, "wb") as f:
            frontmatter.dump(post, f)

    return {
        "path": str(path.relative_to(base_dir)),
        "frontmatter": dict(post.metadata),
    }
