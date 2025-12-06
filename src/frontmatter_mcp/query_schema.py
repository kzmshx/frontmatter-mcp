"""Query schema module for DuckDB table column information."""

from collections import defaultdict
from typing import Any, NotRequired, TypedDict


class ColumnInfo(TypedDict):
    """Column information for a single field."""

    type: str
    nullable: bool
    examples: NotRequired[list[Any]]


# Type alias for table schema
Schema = dict[str, ColumnInfo]


def add_frontmatter_columns(
    schema: Schema,
    records: list[dict[str, Any]],
    max_samples: int = 5,
) -> None:
    """Add frontmatter columns to schema.

    Extracts column information from parsed frontmatter records.
    All values are treated as strings or arrays in DuckDB queries.

    Args:
        schema: Schema dict to extend (mutated in place).
        records: List of parsed frontmatter records.
        max_samples: Maximum number of sample values to include.
    """
    property_values: dict[str, list[Any]] = defaultdict(list)
    for record in records:
        for key, value in record.items():
            if key != "path":
                property_values[key].append(value)

    total_files = len(records)

    for prop, values in property_values.items():
        non_null_values = [v for v in values if v is not None]
        count = len(non_null_values)

        # Detect if values are arrays
        is_array = any(isinstance(v, list) for v in non_null_values)

        # Collect unique sample values
        seen: set[str] = set()
        samples: list[Any] = []
        for v in non_null_values:
            key = str(v)
            if key not in seen and len(samples) < max_samples:
                seen.add(key)
                samples.append(v)

        schema[prop] = ColumnInfo(
            type="array" if is_array else "string",
            nullable=count < total_files,
            examples=samples,
        )
