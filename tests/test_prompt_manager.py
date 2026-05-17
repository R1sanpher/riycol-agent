"""Prompt Manager unit tests — 15 tests"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest


class TestPromptTemplate:
    def test_render_simple(self):
        from core.prompt_manager import PromptTemplate
        t = PromptTemplate("test", "Hello {{name}}", version=1)
        assert t.render(name="World") == "Hello World"

    def test_render_multi_var(self):
        from core.prompt_manager import PromptTemplate
        t = PromptTemplate("test", "{{greeting}} {{target}}", version=1)
        result = t.render(greeting="Hi", target="Riycol")
        assert result == "Hi Riycol"

    def test_render_missing_var(self):
        from core.prompt_manager import PromptTemplate
        t = PromptTemplate("test", "Hello {{name}}", version=1)
        result = t.render()
        assert "Hello" in result  # missing var becomes empty string

    def test_extract_vars_dedup(self):
        from core.prompt_manager import _extract_vars
        vars_ = _extract_vars("{{a}} {{b}} {{a}}")
        assert vars_ == ["a", "b"]  # dedup, preserve order

    def test_to_dict(self):
        from core.prompt_manager import PromptTemplate
        t = PromptTemplate("test", "content", version=3, description="desc")
        d = t.to_dict()
        assert d["name"] == "test"
        assert d["version"] == 3
        assert d["description"] == "desc"
        assert d["template"] == "content"

    def test_from_dict(self):
        from core.prompt_manager import PromptTemplate
        d = {"name": "t", "template": "body", "version": 2, "description": "d"}
        t = PromptTemplate.from_dict(d)
        assert t.name == "t"
        assert t.template == "body"
        assert t.version == 2


class TestPromptLibrary:
    def test_builtins_loaded(self):
        from core.prompt_manager import prompts
        assert prompts.template_count >= 7
        assert "chat" in prompts.list_categories()

    def test_get_valid(self):
        from core.prompt_manager import prompts
        t = prompts.get("chat", "default")
        assert t is not None
        assert t.version == 3
        assert "Riycol" in t.template

    def test_get_missing(self):
        from core.prompt_manager import prompts
        assert prompts.get("nonexistent", "foo") is None

    def test_render_valid(self):
        from core.prompt_manager import prompts
        text = prompts.render("chat", "code_review")
        assert "安全" in text
        assert "代码审查" in text

    def test_render_missing_raises(self):
        from core.prompt_manager import prompts
        with pytest.raises(KeyError):
            prompts.render("bad", "cat")

    def test_snapshot_no_templates(self):
        from core.prompt_manager import prompts
        snap = prompts.snapshot()
        assert "chat" in snap
        for item in snap["chat"]:
            assert "template" not in item  # snapshot is metadata-only
            assert "chars" in item

    def test_upgrade_bumps_version(self):
        from core.prompt_manager import PromptLibrary, PromptTemplate
        lib = PromptLibrary()
        t = PromptTemplate("up", "v1", version=1, description="test")
        lib.register("test", t)
        result = lib.upgrade_template("test", "up", "v2 enhanced", reason="test")
        assert result is not None
        assert result.version == 2
        assert result.template == "v2 enhanced"

    def test_upgrade_missing_returns_none(self):
        from core.prompt_manager import PromptLibrary
        lib = PromptLibrary()
        assert lib.upgrade_template("no", "cat", "x") is None

    def test_load_file(self, tmp_path):
        from core.prompt_manager import PromptLibrary
        data = {"test": [{"name": "x", "template": "y", "version": 1}]}
        fp = tmp_path / "prompts.json"
        fp.write_text(json.dumps(data), encoding="utf-8")
        lib = PromptLibrary()
        lib.load_file(str(fp))
        t = lib.get("test", "x")
        assert t is not None
        assert t.template == "y"

    def test_export_file(self, tmp_path):
        from core.prompt_manager import PromptLibrary
        lib = PromptLibrary()
        fp = tmp_path / "out.json"
        lib.export_file(str(fp))
        assert fp.exists()
        data = json.loads(fp.read_text(encoding="utf-8"))
        assert "chat" in data
        assert len(data["chat"]) >= 4


class TestBuildMessages:
    def test_basic(self):
        from core.prompt_manager import build_messages
        msgs = build_messages("sys", "hello")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": "sys"}
        assert msgs[1] == {"role": "user", "content": "hello"}

    def test_with_history(self):
        from core.prompt_manager import build_messages
        hist = [{"role": "assistant", "content": "hi"}]
        msgs = build_messages("sys", "hello", history=hist)
        assert len(msgs) == 3
        assert msgs[1] == hist[0]

    def test_with_kb(self):
        from core.prompt_manager import build_messages
        msgs = build_messages("sys", "hello", kb_context="kb stuff")
        assert len(msgs) == 3
        assert "kb stuff" in msgs[1]["content"]

    def test_with_extra_context(self):
        from core.prompt_manager import build_messages
        msgs = build_messages("sys", "hello", extra_context="extra")
        assert len(msgs) == 3
        assert msgs[1]["content"] == "extra"

    def test_build_chatml(self):
        from core.prompt_manager import build_chatml
        result = build_chatml("sys", "hi")
        assert result.startswith("<|im_start|>system")
        assert result.endswith("<|im_start|>assistant\n")
        assert "<|im_end|>" in result
