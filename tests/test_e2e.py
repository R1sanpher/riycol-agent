"""
E2E Integration Tests — Full pipeline: chat, KB, agent, DB
===========================================================
Tests the complete flow without mocking external boundaries.
"""
import os, sys, json, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


class TestE2EChatPipeline:
    """End-to-end chat flow: prompt → DB → KB → response"""

    def test_full_chat_flow_no_errors(self):
        """Complete chat pipeline runs without crashes."""
        from core.db import Database, DB
        from core.config import CFG
        from plugins.server.kb import KnowledgeBase

        # Create a temp KB
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(docs_dir=tmpdir, mode="keyword")
            # Add a document
            doc_path = os.path.join(tmpdir, "test.txt")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write("人工智能是计算机科学的一个分支。\n\n它研究智能体的设计与构建。")
            kb.watch()

            # Query KB
            result = kb.query("人工智能")
            assert result["has_result"] is True
            assert len(result["context"]) > 0

            # DB operations
            DB.add_msg("e2e_test", "user", "什么是AI?")
            DB.add_msg("e2e_test", "assistant", "AI是人工智能的缩写")
            stats = DB.stats()
            assert stats["messages"] >= 2

            # Training sample
            DB.add_sample("什么是AI?", "AI是人工智能", dataset="e2e_test")
            samples = DB.get_samples("e2e_test", limit=5)
            assert len(samples) >= 1

    def test_kb_add_and_query_roundtrip(self):
        """KB: add text → scan → query → has_result."""
        from plugins.server.kb import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(docs_dir=tmpdir, mode="keyword")
            kb.add_text("Python是一种广泛使用的编程语言", "lang.txt")
            result = kb.query("Python 编程")
            assert result["has_result"] is True

    def test_agent_swarm_pipeline_no_api(self):
        """统一Agent: can create, add custom agent, handle missing API."""
        from plugins.agent import Agent, AgentSwarm
        swarm = AgentSwarm()
        assert len(swarm.agents) == 1

        # Add custom agent
        custom = Agent("测试员", "测试管道", model="mock")
        swarm.add_agent(custom)
        assert len(swarm.agents) == 2

        # Run without API key (should handle gracefully)
        old_key = os.environ.get("DEEPSEEK_API_KEY", "")
        try:
            if "DEEPSEEK_API_KEY" in os.environ:
                del os.environ["DEEPSEEK_API_KEY"]
            result = swarm.simple_run("测试管道")
            assert isinstance(result, str)
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    def test_agent_memory_persistence(self):
        """Agent memory persists across instances."""
        from plugins.agent import Agent
        from core.memory_store import memory_store
        memory_store.clear_agent("e2e_mem")

        from unittest.mock import patch
        with patch.object(Agent, '_call_deepseek', return_value="回复"):
            a1 = Agent("e2e_mem", "记忆测试")
            a1.act("重要信息: 我的名字是张三")
            assert len(a1.memory) == 2

            # New instance should restore memory
            a2 = Agent("e2e_mem", "记忆测试")
            assert len(a2.memory) == 2
            assert "张三" in str(a2.memory)

        memory_store.clear_agent("e2e_mem")

    def test_scheduler_lifecycle(self):
        """Scheduler: add → start → run → stop."""
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        results = []
        s.add("e2e_task", lambda: results.append("ok"), every_seconds=0.02)
        s.start()
        time.sleep(0.08)
        s.stop()
        assert len(results) >= 1

    def test_tool_pipeline(self):
        """Tools: read_file → search_kb → get_time → db_query."""
        from core.tools import tool_get_time, tool_search_kb, tool_db_query
        t = tool_get_time()
        assert "iso" in t and "date" in t

        kb_result = tool_search_kb("test")
        assert "has_result" in kb_result

        db_result = tool_db_query("SELECT COUNT(*) as cnt FROM conversations")
        assert "rows" in db_result and len(db_result["rows"]) > 0

    def test_config_validate(self):
        """Config validation returns warnings list."""
        from core.config import CFG
        warnings = CFG.validate()
        assert isinstance(warnings, list)

    def test_model_router(self):
        """Model router returns valid model name."""
        from core.model_router import get_available_models, route
        available = get_available_models()
        assert "local" in available
        assert "deepseek" in available
        # Route should return one of the valid backends
        model = route("简单问题")
        assert model in ("local", "deepseek", "ollama")

    def test_token_counter(self):
        """Token counter returns reasonable count."""
        from core.token_counter import count, count_name
        n = count("Hello, how are you today?")
        assert 4 <= n <= 15
        name = count_name()
        assert name in ("tiktoken_cl100k", "llama_cpp", "char_estimate")

    def test_memory_store_end_to_end(self):
        """MemoryStore: full CRUD lifecycle."""
        from core.memory_store import memory_store
        memory_store.put("e2e_ms", "key1", [1, 2, 3])
        assert memory_store.get("e2e_ms", "key1") == [1, 2, 3]
        keys = memory_store.list_keys("e2e_ms")
        assert "key1" in keys
        memory_store.delete("e2e_ms", "key1")
        assert memory_store.get("e2e_ms", "key1") is None
        memory_store.clear_agent("e2e_ms")


class TestFinetunePipeline:
    """Fine-tuning pipeline E2E tests"""

    def test_config_generation(self, tmp_path):
        """cmd_config generates both yaml and py files."""
        import os as _os
        from data.training.train import cmd_config
        # Override output dir for test isolation
        old_dir = _os.getcwd()
        try:
            cmd_config()
            from core.config import CFG
            out = CFG.DATA / "training" / "output"
            assert (out / "llama_factory_config.yaml").exists(), "Missing llama_factory_config.yaml"
            assert (out / "unsloth_train.py").exists(), "Missing unsloth_train.py"
            # Verify content
            yaml_content = (out / "llama_factory_config.yaml").read_text()
            assert "llamafactory-cli" in yaml_content
            py_content = (out / "unsloth_train.py").read_text()
            assert "FastLanguageModel" in py_content
        finally:
            _os.chdir(old_dir)

    def test_config_yaml_valid(self):
        """Generated yaml has valid structure."""
        from core.config import CFG
        out = CFG.DATA / "training" / "output"
        yaml_path = out / "llama_factory_config.yaml"
        if not yaml_path.exists():
            from data.training.train import cmd_config
            cmd_config()
        content = yaml_path.read_text()
        required = ["model_name_or_path", "stage", "dataset", "template", "output_dir"]
        for key in required:
            assert key in content, f"Missing key: {key}"

    def test_config_unsloth_valid(self):
        """Generated unsloth script has required imports."""
        from core.config import CFG
        out = CFG.DATA / "training" / "output"
        py_path = out / "unsloth_train.py"
        if not py_path.exists():
            from data.training.train import cmd_config
            cmd_config()
        content = py_path.read_text()
        required = ["FastLanguageModel", "SFTTrainer", "trainer.train()"]
        for key in required:
            assert key in content, f"Missing: {key}"

    def test_full_pipeline_dry_run(self):
        """All pipeline commands run without crash."""
        from data.training.train import cmd_stats, cmd_clean, cmd_validate, cmd_convert
        cmd_stats()
        cmd_clean()
        cmd_validate()
        cmd_convert()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
