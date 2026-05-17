"""Tests for core/eval.py — AgentEval framework."""
import pytest
from core.eval import AgentEval, EvalCase, EvalResult, EvalReport, BUILTIN_SUITES


class TestEvalFramework:
    def test_builtin_suites_exist(self):
        assert "basic" in BUILTIN_SUITES
        assert "tool_use" in BUILTIN_SUITES
        assert "reasoning" in BUILTIN_SUITES
        assert "safety" in BUILTIN_SUITES
        assert "code" in BUILTIN_SUITES
        assert len(BUILTIN_SUITES["basic"]) >= 3

    def test_eval_case_defaults(self):
        c = EvalCase(id="test", task="hello")
        assert c.id == "test"
        assert c.expected_keywords == []
        assert c.expected_tools == []
        assert c.max_rounds == 3
        assert c.category == "general"

    def test_eval_result_dataclass(self):
        r = EvalResult(case_id="x", passed=True, output="ok", keywords_matched=[], keywords_missed=[], tools_called=[], tools_expected=[], rounds_used=1, duration_s=0.5)
        assert r.passed is True

    def test_eval_report_aggregation(self):
        r = EvalReport(suite_name="test", total=3, passed=2, failed=1, avg_duration_s=1.5, avg_rounds=2.0)
        assert r.passed == 2
        assert r.failed == 1

    def test_run_suite_with_mock(self):
        ev = AgentEval(model="mock")
        r = ev.run_suite("basic")
        assert r.total == 3
        assert r.suite_name == "basic"
        # With mock model, keywords may not match — that's expected for real evaluation

    def test_all_suites_iterable(self):
        ev = AgentEval(model="mock")
        suites = list(ev.suites.keys())
        assert len(suites) >= 5

    def test_compare_returns_dict(self):
        ev = AgentEval(model="mock")
        result = ev.compare("basic")
        assert "suite" in result
        assert "pass_rate" in result
        assert "per_case" in result
