"""
Skill Plugin Loader — auto-discovers and registers Agent skills from skills/*/ directory.

Each skill directory contains:
  SKILL.md  — YAML frontmatter (name, description) + prompt template
  tools.py  — optional: Tool definitions to register

Skills extend the Agent's capabilities without modifying core code.
"""
import json, re, importlib.util
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from core.logger import log
from core.config import CFG


@dataclass
class SkillPlugin:
    name: str
    description: str = ""
    version: str = "1.0"
    tools: list[Any] = field(default_factory=list)  # list[Tool]
    prompt: str = ""
    path: str = ""


class SkillLoader:
    """Auto-discovers skills from the skills/ directory."""

    def __init__(self, skills_dir: str | None = None):
        self._dir = Path(skills_dir or CFG.ROOT / "skills")
        self._loaded: dict[str, SkillPlugin] = {}

    def discover(self) -> list[SkillPlugin]:
        """Scan skills/ directory and return discovered plugins."""
        if not self._dir.exists():
            return []
        discovered = []
        for skill_dir in self._dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            plugin = self._parse_skill(skill_dir)
            if plugin:
                discovered.append(plugin)
                self._loaded[plugin.name] = plugin
        log.info(f"SkillLoader: discovered {len(discovered)} skills")
        return discovered

    def load(self, name: str) -> SkillPlugin | None:
        """Load a specific skill by name."""
        if name in self._loaded:
            return self._loaded[name]
        for skill_dir in self._dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name == name:
                plugin = self._parse_skill(skill_dir)
                if plugin:
                    self._loaded[name] = plugin
                    return plugin
        return None

    def list_all(self) -> list[dict]:
        """Return metadata for all discovered skills."""
        result = []
        for plugin in self._loaded.values():
            result.append({
                "name": plugin.name,
                "description": plugin.description,
                "version": plugin.version,
                "tools": len(plugin.tools),
                "path": plugin.path,
            })
        return result

    def register_tools(self, plugin_name: str, tool_registry) -> int:
        """Register a skill's tools into the given ToolRegistry. Returns count."""
        plugin = self._loaded.get(plugin_name) or self.load(plugin_name)
        if not plugin:
            return 0
        count = 0
        for tool in plugin.tools:
            tool_registry.register(tool)
            count += 1
        log.info(f"SkillLoader: registered {count} tools from '{plugin_name}'")
        return count

    # ---- internal ----

    def _parse_skill(self, skill_dir: Path) -> SkillPlugin | None:
        skill_md = skill_dir / "SKILL.md"
        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception:
            return None

        # Parse YAML frontmatter
        fm = {}
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                for line in text[3:end].splitlines():
                    line = line.strip()
                    if ":" in line:
                        k, v = line.split(":", 1)
                        fm[k.strip()] = v.strip()

        name = fm.get("name", skill_dir.name)
        desc = fm.get("description", "")
        version = fm.get("version", "1.0")

        # Extract prompt from markdown (after frontmatter, before first code block)
        body_start = text.find("---", 3) + 3 if text.startswith("---") else 0
        body = text[body_start:].strip()
        # Remove code blocks for prompt
        prompt = re.sub(r"```[\s\S]*?```", "", body).strip()[:2000]

        # Load tools if present
        tools = []
        tools_py = skill_dir / "tools.py"
        if tools_py.exists():
            tools = self._load_tools(tools_py)

        return SkillPlugin(
            name=name, description=desc, version=version,
            tools=tools, prompt=prompt, path=str(skill_dir),
        )

    def _load_tools(self, tools_py: Path) -> list:
        """Dynamically import tools from a skill's tools.py."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"skill_{tools_py.parent.name}_tools", str(tools_py))
            if spec is None or spec.loader is None:
                return []
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return getattr(mod, "skill_tools", [])
        except Exception as e:
            log.warn(f"SkillLoader: failed to load tools from {tools_py}: {e}")
            return []


# Global singleton
skill_loader = SkillLoader()
