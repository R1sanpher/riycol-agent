"""
Shared fixtures and configuration for all tests.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path (backup for when pyproject.toml pythonpath
# doesn't apply, e.g. some IDE runners or direct pytest invocations)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture
def mock_env_deepseek_key(monkeypatch):
    """Set a fake DEEPSEEK_API_KEY for tests that need model routing."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-fake-key-000000000000")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


@pytest.fixture
def mock_env_notion_key(monkeypatch):
    """Set a fake NOTION_API_KEY for tests that need Notion sync."""
    monkeypatch.setenv("NOTION_API_KEY", "ntn_test_fake_key_00000000000000000")


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database file path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def temp_kb_dir(tmp_path):
    """Provide a temporary knowledge base directory."""
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    return str(kb_dir)
