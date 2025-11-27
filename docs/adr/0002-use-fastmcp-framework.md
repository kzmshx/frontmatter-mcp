# 2. Use FastMCP framework

Date: 2025-11-28

## Status

Accepted

## Context

MCP サーバーを Python で実装するにあたり、ツール定義の方法を選択する必要があった。

初期実装では手動でツールスキーマを定義していた:

```python
TOOLS = [
    Tool(
        name="inspect_frontmatter",
        description="...",
        inputSchema={
            "type": "object",
            "properties": {
                "glob": {"type": "string", "description": "..."}
            },
            "required": ["glob"]
        }
    )
]
```

## Decision

FastMCP を採用し、デコレータベースのツール定義に移行した。

```python
@mcp.tool()
def inspect_frontmatter(glob: str) -> str:
    """Get frontmatter schema from files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory.
    """
```

## Consequences

- コード量が約 50% 削減された
- 関数定義がそのままツール定義になり、docstring から説明が自動生成される
- 型ヒントからスキーマが自動生成される
- FastMCP への依存が追加された
