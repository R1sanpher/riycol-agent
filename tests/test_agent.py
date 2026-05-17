"""
智能体单元测试 — plugins.agent
================================
测试: Agent 核心逻辑、统一Agent协作、边界条件
注意: API 调用被 mock，不依赖真实网络
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAgent:
    """单个智能体测试"""

    @pytest.fixture(autouse=True)
    def _isolate(self):
        """Isolate memory + force auto-routing to deepseek for tests."""
        from core.memory_store import memory_store
        for name in ("测试员", "Riycol"):
            memory_store.clear_agent(name)
        from unittest.mock import patch
        with patch('core.model_router.route', return_value="deepseek"):
            yield
        for name in ("测试员", "Riycol"):
            memory_store.clear_agent(name)

    @pytest.fixture
    def agent(self):
        from plugins.agent import Agent
        return Agent("测试员", "进行测试", model="mock")

    def test_agent_init(self, agent):
        """智能体初始化应设置名称和角色"""
        assert agent.name == "测试员"
        assert agent.role == "进行测试"
        assert agent.memory == []

    def test_agent_init_default_prompt(self):
        """不提供 system_prompt 时默认使用 prompt library 的 chat/default"""
        from plugins.agent import Agent
        a = Agent("Riycol", "全能助手")
        assert a._prompt_ref == ("chat", "default")
        assert "Riycol" in a.system_prompt
        assert "分析" in a.system_prompt

    def test_agent_init_custom_prompt(self):
        """提供 custom system_prompt 时应使用"""
        from plugins.agent import Agent
        custom = "你是专门的测试助手"
        a = Agent("测试员", "测试", system_prompt=custom)
        assert a.system_prompt == custom

    def test_agent_act_mock_model(self, agent):
        """mock 模型应返回占位符"""
        result = agent.act("测试任务")
        assert "[测试员]" in result
        assert "暂不支持" in result

    def test_agent_act_with_context(self, agent):
        """带有上下文的执行"""
        result = agent.act("测试任务", context="这是上下文")
        assert result is not None

    @patch('plugins.agent.Agent._call_deepseek')
    def test_agent_act_deepseek(self, mock_call):
        """deepseek 模型应调用 API"""
        from plugins.agent import Agent
        mock_call.return_value = "API 回复内容"
        a = Agent("测试员", "测试", model="deepseek")
        result = a.act("问题")
        assert result == "API 回复内容"
        mock_call.assert_called_once()

    def test_agent_memory(self):
        """智能体应记录对话历史"""
        from plugins.agent import Agent
        with patch.object(Agent, '_call_deepseek', return_value="回复"):
            a = Agent("测试员", "测试")
            a.act("问题1")
            a.act("问题2")
        assert len(a.memory) == 4
        assert a.memory[0]["role"] == "user"
        assert a.memory[1]["role"] == "assistant"

    def test_agent_memory_limit(self):
        """memory 超过 MAX_MEMORY 时自动裁剪"""
        from plugins.agent import Agent
        with patch.object(Agent, '_call_deepseek', return_value="回复"):
            a = Agent("测试员", "测试")
            for i in range(10):
                a.act(f"问题{i}")
        assert len(a.memory) <= Agent.MAX_MEMORY

    def test_call_deepseek_error(self):
        """API 调用失败时应返回错误信息"""
        from plugins.agent import Agent
        with patch.object(Agent, '_call_deepseek', side_effect=Exception("API 超时")):
            a = Agent("测试员", "测试")
            result = a.act("问题")
            assert "处理出错" in result
            assert "API 超时" in result


class TestAgentSwarm:
    """统一智能体测试（5角色融合为单一Agent）"""

    @pytest.fixture(autouse=True)
    def _isolate(self):
        """Force model routing to deepseek for tests (no real Ollama calls)."""
        from unittest.mock import patch
        with patch('plugins.agent.Agent._resolve_model', return_value="deepseek"):
            yield

    @pytest.fixture
    def swarm(self):
        from plugins.agent import AgentSwarm
        s = AgentSwarm()
        return s

    def test_swarm_init(self, swarm):
        """初始化应有1个统一智能体"""
        assert len(swarm.agents) == 1
        assert "Riycol" in swarm.agents

    def test_swarm_add_custom_agent(self, swarm):
        """添加自定义智能体"""
        from plugins.agent import Agent
        extra = Agent("审核员", "审核回复质量")
        swarm.add_agent(extra)
        assert len(swarm.agents) == 2
        assert "审核员" in swarm.agents

    def test_swarm_add_override(self, swarm):
        """添加同名智能体应覆盖"""
        from plugins.agent import Agent
        new_main = Agent("Riycol", "新的角色定义")
        swarm.add_agent(new_main)
        assert swarm.agents["Riycol"].role == "新的角色定义"

    @patch('plugins.agent.Agent._call_deepseek')
    def test_swarm_run(self, mock_call, swarm):
        """统一智能体直接处理任务"""
        mock_call.return_value = "模拟回复内容"
        result = swarm.run("测试问题")
        assert mock_call.call_count == 1
        assert "模拟回复内容" in result

    def test_swarm_simple_run_no_key(self, swarm):
        """无 API Key 时 simple_run 应返回提示"""
        import os
        old_key = os.environ.get("DEEPSEEK_API_KEY", "")
        try:
            if "DEEPSEEK_API_KEY" in os.environ:
                del os.environ["DEEPSEEK_API_KEY"]
            result = swarm.simple_run("测试")
            assert "[Swarm]" in result
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    def test_swarm_simple_run_with_key(self, swarm):
        """有 API Key 时 simple_run 应调用 Riycol"""
        import os
        from plugins.agent import Agent
        old_key = os.environ.get("DEEPSEEK_API_KEY", "")
        try:
            os.environ["DEEPSEEK_API_KEY"] = "sk-test-key"
            with patch.object(Agent, '_call_deepseek', return_value="Riycol回复") as mock_call:
                result = swarm.simple_run("测试")
                assert result == "Riycol回复"
                mock_call.assert_called_once()
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key
            else:
                os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_swarm_run_no_agents(self):
        """无智能体时返回 fallback 而非崩溃"""
        from plugins.agent import AgentSwarm
        s = AgentSwarm()
        s.agents.clear()
        result = s.run("测试")
        assert "[Swarm]" in result

    @patch('plugins.agent.Agent._call_deepseek')
    def test_swarm_run_with_review(self, mock_call, swarm):
        """带自审的完整流程（Reflection 因低分触发 2 轮 refine）"""
        mock_call.return_value = "模拟回复"
        result = swarm.run_with_review("审查测试")
        assert "模拟回复" in result
        # 1 initial act + 2 refine rounds (both fail with score=0.10) = 3
        assert mock_call.call_count == 3

    @patch('plugins.agent.Agent._call_deepseek')
    def test_swarm_run_with_review_memory_context(self, mock_call, swarm):
        """传递 memory_context 时作为上下文传入（Reflection 触发 2 轮 refine）"""
        mock_call.return_value = "带记忆的回复"
        result = swarm.run_with_review("测试", memory_context="用户偏好：简洁回答")
        assert result == "带记忆的回复"
        assert mock_call.call_count == 3

    def test_swarm_run_with_review_no_agents(self):
        """无Agent时返回 fallback"""
        from plugins.agent import AgentSwarm
        s = AgentSwarm()
        s.agents.clear()
        result = s.run_with_review("测试")
        assert "[Swarm]" in result

    def test_plugin_register(self):
        """插件注册应返回正确信息"""
        from plugins.agent import register
        info = register()
        assert info.name == "agent"
        assert info.version == "2.0"
        assert "swarm" in info.description.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
