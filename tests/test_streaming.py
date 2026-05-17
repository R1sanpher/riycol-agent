"""Tests for Agent streaming (act_stream)."""
import pytest
from unittest.mock import patch, MagicMock
from plugins.agent import Agent


class TestAgentStreaming:
    def test_act_stream_mock_model(self):
        agent = Agent("streamer", "test", model="mock")
        result = list(agent.act_stream("hello"))
        assert len(result) >= 1
        assert isinstance(result[0], str)

    def test_act_stream_local_fallback(self):
        agent = Agent("streamer", "test", model="local")
        result = list(agent.act_stream("hello"))
        assert len(result) >= 1

    def test_stream_error_handling(self):
        agent = Agent("streamer", "test", model="mock")

        @patch.object(Agent, '_resolve_model', return_value="deepseek")
        @patch.object(Agent, '_call_deepseek_stream', side_effect=ConnectionError("fail"))
        def test(mock_stream, mock_model):
            result = list(agent.act_stream("hello"))
            assert any("出错" in r or "不可用" in r for r in result)

        test()

    def test_stream_methods_exist(self):
        agent = Agent("s", "test", model="mock")
        assert hasattr(agent, "act_stream")
        assert hasattr(agent, "_call_deepseek_stream")
        assert hasattr(agent, "_call_ollama_stream")
