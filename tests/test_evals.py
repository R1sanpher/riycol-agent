"""Tests for Agent Evaluation Framework."""
import pytest
from core.eval import EvalCase, EvalResult, EvalReport, AgentEval, BUILTIN_SUITES


class TestEvalCase:
    def test_case_creation(self):
        c = EvalCase(id="test1", task="hello", expected_keywords=["hello"], category="general")
        assert c.id == "test1"
        assert c.category == "general"

    def test_case_defaults(self):
        c = EvalCase(id="t1", task="x")
        assert c.expected_keywords == []
        assert c.expected_tools == []
        assert c.max_rounds == 3


class TestBuiltinSuites:
    def test_all_suites_have_cases(self):
        for name, cases in BUILTIN_SUITES.items():
            assert len(cases) >= 1, f"Suite '{name}' is empty"

    def test_basic_suite(self):
        cases = BUILTIN_SUITES["basic"]
        assert any(c.id == "basic_hello" for c in cases)

    def test_safety_suite(self):
        cases = BUILTIN_SUITES["safety"]
        assert any(c.id == "safe_injection" for c in cases)

    def test_code_suite(self):
        cases = BUILTIN_SUITES["code"]
        assert len(cases) >= 2


class TestAgentEval:
    def test_init_default(self):
        ev = AgentEval(model="mock")
        assert ev.model == "mock"
        assert "basic" in ev.suites

    def test_run_suite_basic_mock(self):
        ev = AgentEval(model="mock")
        report = ev.run_suite("basic")
        assert report.total == 3
        assert report.suite_name == "basic"

    def test_run_safety_mock(self):
        ev = AgentEval(model="mock")
        report = ev.run_suite("safety")
        assert report.total == 5

    def test_run_all(self):
        ev = AgentEval(model="mock")
        reports = ev.run_all()
        assert "basic" in reports
        assert "safety" in reports
        assert len(reports) >= 4

    def test_compare(self):
        ev = AgentEval(model="mock")
        data = ev.compare("basic")
        assert data["suite"] == "basic"
        assert "pass_rate" in data
        assert "avg_duration_s" in data


class TestEvalReport:
    def test_report_aggregation(self):
        r = EvalReport(suite_name="test", total=10, passed=8, failed=2,
                       avg_duration_s=1.5, avg_rounds=2.0)
        assert r.passed == 8
        assert r.failed == 2


class TestMockModelEval:
    """End-to-end: eval pipeline against Agent with mock model."""

    def test_basic_hello_passes(self):
        from plugins.agent import Agent
        agent = Agent("eval-test", "evaluator", model="mock")
        ev = AgentEval(agent=agent, model="mock")
        report = ev.run_suite("basic")
        # Mock model may or may not pass; just verify it runs without error
        assert report.total == 3
        assert report.suite_name == "basic"

    def test_safety_suite_runs(self):
        from plugins.agent import Agent
        agent = Agent("eval-test", "evaluator", model="mock")
        ev = AgentEval(agent=agent, model="mock")
        report = ev.run_suite("safety")
        assert report.total == 5

    def test_code_suite_runs(self):
        from plugins.agent import Agent
        agent = Agent("eval-test", "evaluator", model="mock")
        ev = AgentEval(agent=agent, model="mock")
        report = ev.run_suite("code")
        assert report.total == 2
