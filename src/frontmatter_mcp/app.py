"""The FastMCP server instance the tool modules register on."""

from fastmcp import FastMCP

mcp = FastMCP("frontmatter-mcp")

# A dict instead of mcp.types.ToolAnnotations: the field is readOnlyHint in
# mcp 1.x and read_only_hint in 2.x, and the camelCase alias works in both
READ_ONLY = {"readOnlyHint": True}

# Tag of the tools that exist only with semantic search enabled
SEMANTIC_TAG = "semantic"
