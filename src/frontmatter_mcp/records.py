"""Reading frontmatter into records for querying."""

from pathlib import Path
from typing import Any, NamedTuple

import frontmatter
from typing_extensions import TypedDict

from frontmatter_mcp.paths import relative

# A parsed file: "path" (relative to the base directory) plus its frontmatter
FileRecord = dict[str, Any]

# Columns the server adds itself; frontmatter keys with these names are ignored
RESERVED_KEYS = frozenset({"path"})


class FileWarning(TypedDict):
    """A file that was skipped or only partly used, and why."""

    path: str
    error: str


class _CacheEntry(NamedTuple):
    mtime: float
    record: FileRecord
    warning: FileWarning | None


class FileRecordCache:
    """Parsed records keyed by absolute path, valid while the mtime matches."""

    def __init__(self) -> None:
        self._entries: dict[Path, _CacheEntry] = {}

    def get(self, path: Path, mtime: float) -> _CacheEntry | None:
        entry = self._entries.get(path)
        return entry if entry is not None and entry.mtime == mtime else None

    def set(self, path: Path, entry: _CacheEntry) -> None:
        self._entries[path] = entry


def parse_file(path: Path, base_dir: Path) -> tuple[FileRecord, FileWarning | None]:
    """Parse one file's frontmatter into a record.

    Returns:
        The record, and a warning if a reserved key had to be ignored.
    """
    rel_path = relative(base_dir, path)
    metadata = frontmatter.load(path).metadata
    record: FileRecord = {"path": rel_path}
    ignored = sorted(k for k in metadata if k in RESERVED_KEYS)
    record.update((k, v) for k, v in metadata.items() if k not in RESERVED_KEYS)
    warning = None
    if ignored:
        warning = FileWarning(
            path=rel_path,
            error=f"frontmatter key(s) {', '.join(ignored)} are reserved and ignored",
        )
    return record, warning


def parse_files(
    paths: list[Path],
    base_dir: Path,
    cache: FileRecordCache,
) -> tuple[list[FileRecord], list[FileWarning]]:
    """Parse frontmatter from multiple files, reusing cached results.

    Returns:
        Records for the files that could be parsed, and warnings for the rest.
    """
    records: list[FileRecord] = []
    warnings: list[FileWarning] = []
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError as e:
            warnings.append(FileWarning(path=relative(base_dir, path), error=str(e)))
            continue
        entry = cache.get(path, mtime)
        if entry is None:
            try:
                record, warning = parse_file(path, base_dir)
            except Exception as e:
                warnings.append(
                    FileWarning(path=relative(base_dir, path), error=str(e))
                )
                continue
            entry = _CacheEntry(mtime, record, warning)
            cache.set(path, entry)
        records.append(entry.record)
        if entry.warning is not None:
            warnings.append(entry.warning)
    return records, warnings
