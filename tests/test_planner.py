"""Tests for core/planner.py — Planner, PlanStep, ExecutionPlan."""
import pytest
from core.planner import Planner, PlanStep, ExecutionPlan


class TestPlanStep:
    def test_plan_step_defaults(self):
        ps = PlanStep(index=1, description="test step")
        assert ps.index == 1
        assert ps.description == "test step"
        assert ps.tool is None
        assert ps.tool_args is None
        assert ps.depends_on == []

    def test_plan_step_with_tool(self):
        ps = PlanStep(index=2, description="read config", tool="read_file",
                      tool_args={"filepath": ".env"})
        assert ps.tool == "read_file"
        assert ps.tool_args == {"filepath": ".env"}


class TestExecutionPlan:
    def test_execution_plan(self):
        steps = [PlanStep(index=1, description="step 1")]
        plan = ExecutionPlan(task="test task", steps=steps)
        assert plan.task == "test task"
        assert len(plan.steps) == 1


class TestPlannerParse:
    def test_parse_valid_json(self):
        p = Planner()
        raw = '[{"index":1,"description":"read file","tool":"read_file","tool_args":{"filepath":"x.txt"},"expected_output":"content"}]'
        steps = p._parse_plan(raw, ["read_file", "write_file"])
        assert len(steps) == 1
        assert steps[0].tool == "read_file"
        assert steps[0].index == 1

    def test_parse_rejects_invalid_tool(self):
        p = Planner()
        raw = '[{"index":1,"description":"bad","tool":"hack"}]'
        steps = p._parse_plan(raw, ["read_file"])
        assert steps[0].tool is None  # rejected

    def test_parse_fallback_line_format(self):
        p = Planner()
        raw = "STEP 1: Read the config file\nSTEP 2: Write test"
        steps = p._parse_plan(raw, [])
        assert len(steps) == 2
        assert steps[0].description == "Read the config file"

    def test_heuristic_plan(self):
        p = Planner()
        plan = p._heuristic_plan("simple task", ["read_file"])
        assert len(plan.steps) == 1
        assert plan.steps[0].description == "simple task"
        assert plan.model_used == "heuristic"
