"""Frontmatter read/write module."""

import os
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import frontmatter

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


def write_post(path: Path, post: frontmatter.Post) -> None:
    """Write a post back to its file without risking data loss.

    The new content is written to a temporary file in the same directory and
    then atomically renamed over the original, so a failure while serializing
    or writing leaves the original file untouched. Key order is preserved and
    the file ends with a newline.

    Args:
        path: Absolute path to the file.
        post: Post to write.
    """
    text = frontmatter.dumps(post, sort_keys=False) + "\n"
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
