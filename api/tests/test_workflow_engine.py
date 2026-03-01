"""Tests for workflow execution engine."""
import pytest
from services.workflow_engine import resolve_template, topological_sort


def test_resolve_template_simple():
    ctx = {"inputs": {"feature": "auth module"}}
    result = resolve_template("Test {{ inputs.feature }}", ctx)
    assert result == "Test auth module"


def test_resolve_template_step_output():
    ctx = {
        "steps": {"extract": {"output": "found 3 files", "session_id": "abc"}},
        "inputs": {},
    }
    result = resolve_template(
        "Review: {{ steps.extract.output }}", ctx
    )
    assert result == "Review: found 3 files"


def test_resolve_template_missing_var():
    ctx = {"inputs": {}, "steps": {}}
    result = resolve_template("Test {{ inputs.missing }}", ctx)
    assert result == "Test "


def test_topological_sort_linear():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
    ]
    step_ids = ["a", "b", "c"]
    result = topological_sort(step_ids, edges)
    assert result == ["a", "b", "c"]


def test_topological_sort_fan_out():
    edges = [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "c"},
    ]
    step_ids = ["a", "b", "c"]
    result = topological_sort(step_ids, edges)
    assert result[0] == "a"
    assert set(result[1:]) == {"b", "c"}


def test_topological_sort_fan_in():
    edges = [
        {"source": "a", "target": "c"},
        {"source": "b", "target": "c"},
    ]
    step_ids = ["a", "b", "c"]
    result = topological_sort(step_ids, edges)
    assert result[-1] == "c"
    assert set(result[:2]) == {"a", "b"}


def test_evaluate_condition_true():
    from services.workflow_engine import evaluate_condition

    ctx = {"steps": {"review": {"output": "found issues", "has_issues": "true"}}}
    assert evaluate_condition("{{ steps.review.has_issues }} == true", ctx) is True


def test_evaluate_condition_false():
    from services.workflow_engine import evaluate_condition

    ctx = {"steps": {"review": {"output": "all good", "has_issues": "false"}}}
    assert evaluate_condition("{{ steps.review.has_issues }} == true", ctx) is False


def test_evaluate_condition_none():
    from services.workflow_engine import evaluate_condition

    assert evaluate_condition(None, {}) is True  # No condition = always run
