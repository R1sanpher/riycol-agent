"""
Reflection module unit tests — core.reflection
================================================
Tests: CritiqueResult dataclass, parse_critique JSON/keyword fallback,
       critique with mocked LLM, reflect_and_refine loop.
"""
import pytest
from unittest.mock import patch


class TestCritiqueResult:
    def test_defaults(self):
        from core.reflection import CritiqueResult
        r = CritiqueResult(passes=True, score=0.9)
        assert r.passes is True
        assert r.score == 0.9
        assert r.issues == []
        assert r.suggestions == []
        assert r.gaps == []
        assert r.raw_critique == ""


class TestParseCritique:
    def test_parse_valid_json(self):
        from core.reflection import Reflection
        r = Reflection()
        raw = '{"passes": false, "score": 0.3, "issues": ["wrong output"], "suggestions": ["fix it"], "gaps": ["missing context"]}'
        result = r._parse_critique(raw)
        assert result.passes is False
        assert result.score == 0.3
        assert "wrong output" in result.issues
        assert "fix it" in result.suggestions
        assert "missing context" in result.gaps

    def test_parse_json_with_extra_text(self):
        from core.reflection import Reflection
        r = Reflection()
        raw = 'Here is my critique:\n{"passes": true, "score": 0.95, "issues": [], "suggestions": [], "gaps": []}\n---end'
        result = r._parse_critique(raw)
        assert result.passes is True
        assert result.score == 0.95

    def test_parse_invalid_json_fallback_fail(self):
        from core.reflection import Reflection
        r = Reflection()
        raw = "This output has issues and fails to meet requirements"
        result = r._parse_critique(raw)
        assert result.passes is False  # fallback detects "fail"/"issue"
        assert result.score == 0.5

    def test_parse_invalid_json_fallback_pass(self):
        from core.reflection import Reflection
        r = Reflection()
        raw = "The output is correct and complete"
        result = r._parse_critique(raw)
        assert result.passes is True
        assert result.score == 0.5

    def test_nested_brackets_in_json(self):
        from core.reflection import Reflection
        r = Reflection()
        raw = '{"passes": true, "score": 0.8, "issues": ["nested {brace}"], "suggestions": [], "gaps": []}'
        result = r._parse_critique(raw)
        assert result.passes is True
        assert "nested {brace}" in result.issues


class TestCritique:
    def test_critique_calls_llm_and_parses(self):
        from core.reflection import Reflection
        r = Reflection()
        with patch("core.llm_client.llm_call") as mock_llm:
            mock_llm.return_value = '{"passes": true, "score": 0.95, "issues": [], "suggestions": [], "gaps": []}'
            result = r.critique("test task", "test output")
            assert result.passes is True
            assert result.score == 0.95
            mock_llm.assert_called_once()

    def test_critique_llm_failure_returns_graceful(self):
        from core.reflection import Reflection
        r = Reflection()
        with patch("core.llm_client.llm_call") as mock_llm:
            mock_llm.side_effect = ConnectionError("API unavailable")
            result = r.critique("test task", "test output")
            assert result.passes is True  # graceful: default to pass
            assert result.score == 0.7
            assert "critique unavailable" in result.raw_critique


class TestReflectAndRefine:
    def test_refine_passes_first_round(self):
        from core.reflection import Reflection
        r = Reflection()

        def mock_execute(prompt):
            return "refined output"

        with patch.object(r, "critique") as mock_critique:
            from core.reflection import CritiqueResult
            mock_critique.return_value = CritiqueResult(passes=True, score=0.95, raw_critique="ok")
            result = r.reflect_and_refine("task", "initial output", mock_execute, max_rounds=2)
            assert result == "initial output"  # returned immediately on pass
            mock_critique.assert_called_once()

    def test_refine_loops_until_pass(self):
        from core.reflection import Reflection
        r = Reflection()
        calls = 0

        def mock_execute(prompt):
            return "refined output"

        with patch.object(r, "critique") as mock_critique:
            from core.reflection import CritiqueResult
            mock_critique.side_effect = [
                CritiqueResult(passes=False, score=0.3, issues=["wrong"], raw_critique="fail"),
                CritiqueResult(passes=True, score=0.9, raw_critique="ok"),
            ]
            result = r.reflect_and_refine("task", "initial", mock_execute, max_rounds=3)
            assert result == "refined output"
            assert mock_critique.call_count == 2

    def test_refine_max_rounds_exhausted(self):
        from core.reflection import Reflection
        r = Reflection()

        def mock_execute(prompt):
            return "refined output"

        with patch.object(r, "critique") as mock_critique:
            from core.reflection import CritiqueResult
            mock_critique.return_value = CritiqueResult(passes=False, score=0.2, issues=["bad"])
            result = r.reflect_and_refine("task", "initial", mock_execute, max_rounds=2)
            assert result == "refined output"  # returns last result after exhausting rounds
            assert mock_critique.call_count == 2
