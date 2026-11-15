"""Tests for settings read from the environment."""

from pathlib import Path

import pytest

from frontmatter_mcp.settings import Settings


def test_exclude_defaults_to_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTMATTER_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("FRONTMATTER_EXCLUDE", raising=False)
    assert Settings().exclude == []  # type: ignore[call-arg]


def test_exclude_is_comma_separated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTMATTER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("FRONTMATTER_EXCLUDE", " IDENTITY.md, _templates/** ,,")
    assert Settings().exclude == ["IDENTITY.md", "_templates/**"]  # type: ignore[call-arg]
