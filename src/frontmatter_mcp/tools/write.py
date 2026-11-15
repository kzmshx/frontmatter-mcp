"""Tools that change frontmatter: update, batch_update, batch_array_*."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends

from frontmatter_mcp import array_ops
from frontmatter_mcp.app import mcp
from frontmatter_mcp.dependencies import get_settings
from frontmatter_mcp.paths import collect_files, relative, resolve_file
from frontmatter_mcp.records import FileWarning
from frontmatter_mcp.settings import Settings
from frontmatter_mcp.tools.results import BatchResult, UpdateResult
from frontmatter_mcp.writer import apply_update, read_metadata, write_metadata

# Takes a file's frontmatter, returns the new frontmatter or None to leave the
# file alone
Transform = Callable[[dict[str, Any]], dict[str, Any] | None]


def _update_files(base_dir: Path, glob: str, transform: Transform) -> BatchResult:
    """Apply transform to every matching file; errors become warnings."""
    updated: list[str] = []
    warnings: list[FileWarning] = []
    for path in collect_files(base_dir, glob):
        rel_path = relative(base_dir, path)
        try:
            new = transform(read_metadata(path))
            if new is not None and write_metadata(path, new):
                updated.append(rel_path)
        except array_ops.NotAnArrayError as e:
            warnings.append(FileWarning(path=rel_path, error=f"skipped: {e}"))
        except Exception as e:
            warnings.append(FileWarning(path=rel_path, error=str(e)))
    result = BatchResult(updated_count=len(updated), updated_files=updated)
    if warnings:
        result["warnings"] = warnings
    return result


def _on_array(prop: str, op: Callable[[Any], list[Any] | None]) -> Transform:
    """Transform that applies a list operation to one array property."""

    def transform(metadata: dict[str, Any]) -> dict[str, Any] | None:
        try:
            new_value = op(metadata.get(prop))
        except array_ops.NotAnArrayError as e:
            raise array_ops.NotAnArrayError(f"'{prop}' is {e}") from None
        if new_value is None:
            return None
        return {**metadata, prop: new_value}

    return transform


@mcp.tool()
def update(
    path: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
    settings: Settings = Depends(get_settings),
) -> UpdateResult:
    """Update frontmatter properties in a single file.

    Only the changed keys are rewritten; other keys, comments, quoting, list
    style, and the body stay as they are.

    Args:
        path: File path relative to base directory.
        set: Properties to add or overwrite. Values are applied as-is (null becomes
            YAML null, empty string becomes empty value).
        unset: Property names to remove completely.

    Returns:
        Dict with path, the resulting frontmatter, and updated (false when the
        values were already as requested and the file was not touched).

    Notes:
        - If same key appears in both set and unset, unset takes priority.
        - If file has no frontmatter, it will be created.
    """
    base_dir = settings.base_dir
    abs_path = resolve_file(base_dir, path)
    metadata = apply_update(read_metadata(abs_path), set, unset)
    updated = write_metadata(abs_path, metadata) if (set or unset) else False
    return UpdateResult(
        path=relative(base_dir, abs_path), frontmatter=metadata, updated=updated
    )


@mcp.tool()
def batch_update(
    glob: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Update frontmatter properties in multiple files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        set: Properties to add or overwrite in all matched files.
        unset: Property names to remove from all matched files.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If same key appears in both set and unset, unset takes priority.
        - If a file has no frontmatter, it will be created.
        - Files whose values are already as requested are not written and
          not listed in updated_files.
        - Errors in individual files are recorded in warnings, not raised.
    """
    return _update_files(
        settings.base_dir, glob, lambda metadata: apply_update(metadata, set, unset)
    )


@mcp.tool()
def batch_array_add(
    glob: str,
    property: str,
    value: Any,
    allow_duplicates: bool = False,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Add a value to an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        value: Value to add. If value is an array, it's added as a single element.
        allow_duplicates: If False (default), skip files where value already exists.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, it will be created with [value].
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    return _update_files(
        settings.base_dir,
        glob,
        _on_array(property, lambda cur: array_ops.add(cur, value, allow_duplicates)),
    )


@mcp.tool()
def batch_array_remove(
    glob: str,
    property: str,
    value: Any,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Remove a value from an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        value: Value to remove. Every occurrence is removed.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If value doesn't exist in array, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    return _update_files(
        settings.base_dir,
        glob,
        _on_array(property, lambda cur: array_ops.remove(cur, value)),
    )


@mcp.tool()
def batch_array_replace(
    glob: str,
    property: str,
    old_value: Any,
    new_value: Any,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Replace a value in an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        old_value: Value to replace. Every occurrence is replaced.
        new_value: New value.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If old_value doesn't exist in array, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    return _update_files(
        settings.base_dir,
        glob,
        _on_array(property, lambda cur: array_ops.replace(cur, old_value, new_value)),
    )


@mcp.tool()
def batch_array_sort(
    glob: str,
    property: str,
    reverse: bool = False,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Sort an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        reverse: If True, sort in descending order. Default is ascending.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If array is already sorted (including empty), file is skipped.
        - If property is not an array, or its values can't be compared, file
          is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    return _update_files(
        settings.base_dir,
        glob,
        _on_array(property, lambda cur: array_ops.sort(cur, reverse)),
    )


@mcp.tool()
def batch_array_unique(
    glob: str,
    property: str,
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    """Remove duplicate values from an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - Preserves the order of first occurrence.
        - If property doesn't exist, file is skipped.
        - If array has no duplicates, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    return _update_files(settings.base_dir, glob, _on_array(property, array_ops.unique))
