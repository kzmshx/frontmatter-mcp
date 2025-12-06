"""Fixtures for benchmark tests."""

import random
import string
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pytest


def _random_string(length: int = 10) -> str:
    """Generate a random lowercase string."""
    return "".join(random.choices(string.ascii_lowercase, k=length))


def _random_date() -> date:
    """Generate a random date in 2024."""
    base = date(2024, 1, 1)
    return base + timedelta(days=random.randint(0, 365))


def _random_tags(count: int = 3) -> list[str]:
    """Select random tags from a pool."""
    pool = ["python", "mcp", "duckdb", "markdown", "obsidian", "notes", "api", "cli"]
    return random.sample(pool, min(count, len(pool)))


def generate_markdown(prop_count: int = 5) -> str:
    """Generate synthetic Markdown with frontmatter.

    Args:
        prop_count: Number of frontmatter properties to generate.

    Returns:
        Markdown content with YAML frontmatter.
    """
    props: dict[str, str | list[str] | bool | int] = {
        "title": _random_string(20),
        "date": _random_date().isoformat(),
        "tags": _random_tags(),
        "draft": random.choice([True, False]),
        "priority": random.randint(1, 5),
    }
    # Add extra properties if needed
    for i in range(max(0, prop_count - 5)):
        props[f"prop_{i}"] = _random_string(15)

    lines = ["---"]
    for k, v in props.items():
        if isinstance(v, list):
            lines.append(f"{k}: {v}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append(f"# {props['title']}")
    lines.append("")
    lines.append(_random_string(200))

    return "\n".join(lines)


@pytest.fixture(scope="module")
def benchmark_dir_factory(
    tmp_path_factory: pytest.TempPathFactory,
) -> Callable[[int], Path]:
    """Factory fixture to create benchmark directories with synthetic files.

    Returns a function that creates directories with the specified number of files.
    Results are cached within the module scope.
    """
    cache: dict[tuple[int, int], Path] = {}

    def _create(file_count: int, prop_count: int = 5) -> Path:
        key = (file_count, prop_count)
        if key in cache:
            return cache[key]

        base = tmp_path_factory.mktemp(f"bench_{file_count}_{prop_count}")
        for i in range(file_count):
            content = generate_markdown(prop_count)
            (base / f"file_{i:04d}.md").write_text(content)

        cache[key] = base
        return base

    return _create
