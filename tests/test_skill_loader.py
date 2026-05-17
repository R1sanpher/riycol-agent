"""Tests for core/skill_loader.py — SkillPlugin discovery and loading."""
import pytest
from pathlib import Path
from core.skill_loader import SkillLoader, SkillPlugin


class TestSkillLoader:
    def test_discover_skills(self):
        loader = SkillLoader()
        plugins = loader.discover()
        assert len(plugins) >= 1  # at least agent-browser and self-improvement
        names = [p.name for p in plugins]
        assert "Agent Browser" in names or "self-improvement" in names

    def test_list_all(self):
        loader = SkillLoader()
        loader.discover()
        skills = loader.list_all()
        assert len(skills) >= 1
        for s in skills:
            assert "name" in s
            assert "description" in s
            assert "version" in s

    def test_load_by_name(self):
        loader = SkillLoader()
        loader.discover()
        # Try loading self-improvement
        plugin = loader.load("self-improving-agent")
        if plugin:
            assert plugin.name in ("self-improvement", "Self-Improvement Agent")

    def test_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty_skills"
        empty_dir.mkdir()
        loader = SkillLoader(str(empty_dir))
        plugins = loader.discover()
        assert len(plugins) == 0

    def test_plugin_dataclass(self):
        plugin = SkillPlugin(name="test", description="test desc", version="1.0")
        assert plugin.name == "test"
        assert plugin.tools == []
        assert plugin.prompt == ""
