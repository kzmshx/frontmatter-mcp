"""Query schema extension for semantic search."""

from frontmatter_mcp.query_schema import ColumnInfo, Schema
from frontmatter_mcp.semantic.context import SemanticContext


def add_semantic_schema(schema: Schema, ctx: SemanticContext) -> None:
    """Add semantic search columns to schema.

    Args:
        schema: Schema dict to extend (mutated in place).
        ctx: Semantic context with model for dimension info.
    """
    dim = ctx.model.get_dimension()
    schema["embedding"] = ColumnInfo(
        type=f"FLOAT[{dim}]",
        nullable=False,
    )
