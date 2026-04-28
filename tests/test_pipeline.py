"""Tests for pipeline.py — processes a single request end to end."""
import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_request():
    return {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "subject": "Cannot export report",
        "message": "The export button does nothing.",
        "timestamp": "2026-04-28T10:00:00",
    }


def _make_clf(category="bug_report", confidence=0.9, impact="high", reasoning="test"):
    from coordinator import ClassificationResult
    return ClassificationResult(
        category=category, confidence=confidence, impact=impact, reasoning=reasoning
    )


def _run(request, clf, specialist_output="Handled.", tools=None):
    """Helper: run the pipeline with all external calls mocked."""
    from pipeline import run_pipeline
    with patch("pipeline._classify", return_value=clf), \
         patch("pipeline.specialist_dispatch", return_value=specialist_output), \
         patch("pipeline.specialists_module.clear_tool_log"), \
         patch("pipeline.specialists_module.get_tool_log", return_value=tools or []):
        return run_pipeline(request)


# ── Output structure ──────────────────────────────────────────────────────────

class TestRunPipelineStructure:
    def test_returns_dict(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert isinstance(result, dict)

    def test_has_request_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "request" in result

    def test_has_classification_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "classification" in result

    def test_has_escalated_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "escalated" in result

    def test_has_escalation_detail_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "escalation_detail" in result

    def test_has_specialist_output_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "specialist_output" in result

    def test_has_tools_called_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "tools_called" in result

    def test_has_processing_ms_key(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert "processing_ms" in result

    def test_classification_dict_has_required_fields(self, sample_request):
        result = _run(sample_request, _make_clf("feature_request", 0.75, "medium", "Feature ask."))
        clf = result["classification"]
        for field in ("category", "confidence", "impact", "reasoning"):
            assert field in clf, f"Missing field: {field}"


# ── Classification values ─────────────────────────────────────────────────────

class TestRunPipelineClassification:
    def test_category_preserved(self, sample_request):
        result = _run(sample_request, _make_clf("feature_request", 0.75, "medium"))
        assert result["classification"]["category"] == "feature_request"

    def test_confidence_preserved(self, sample_request):
        result = _run(sample_request, _make_clf(confidence=0.75))
        assert result["classification"]["confidence"] == pytest.approx(0.75)

    def test_impact_preserved(self, sample_request):
        result = _run(sample_request, _make_clf(impact="medium"))
        assert result["classification"]["impact"] == "medium"


# ── Escalation logic ──────────────────────────────────────────────────────────

class TestRunPipelineEscalation:
    def test_not_escalated_for_normal_case(self, sample_request):
        result = _run(sample_request, _make_clf("general_question", 0.9, "low"))
        assert result["escalated"] is False

    def test_escalated_for_critical_impact(self, sample_request):
        result = _run(sample_request, _make_clf("bug_report", 0.95, "critical"))
        assert result["escalated"] is True

    def test_escalated_for_low_confidence(self, sample_request):
        result = _run(sample_request, _make_clf("bug_report", 0.40, "low"))
        assert result["escalated"] is True

    def test_escalated_for_billing_high_impact(self, sample_request):
        result = _run(sample_request, _make_clf("billing_issue", 0.80, "high"))
        assert result["escalated"] is True

    def test_not_escalated_for_bug_high_impact(self, sample_request):
        result = _run(sample_request, _make_clf("bug_report", 0.80, "high"))
        assert result["escalated"] is False

    def test_escalation_detail_action_matches_escalated_flag(self, sample_request):
        result = _run(sample_request, _make_clf("bug_report", 0.95, "critical"))
        assert result["escalation_detail"]["action"] == "escalate"
        assert result["escalated"] is True

    def test_auto_handle_action_matches_not_escalated(self, sample_request):
        result = _run(sample_request, _make_clf("general_question", 0.9, "low"))
        assert result["escalation_detail"]["action"] == "auto-handle"
        assert result["escalated"] is False


# ── Passthrough values ────────────────────────────────────────────────────────

class TestRunPipelinePassthrough:
    def test_specialist_output_preserved(self, sample_request):
        expected = "Your billing issue has been resolved in 3 steps."
        result = _run(sample_request, _make_clf("billing_issue", 0.8, "medium"), specialist_output=expected)
        assert result["specialist_output"] == expected

    def test_tools_called_list_preserved(self, sample_request):
        tools = ["analyze_severity", "extract_reproduction_steps", "generate_bug_ticket"]
        result = _run(sample_request, _make_clf(), tools=tools)
        assert result["tools_called"] == tools

    def test_tools_called_empty_list_when_none_used(self, sample_request):
        result = _run(sample_request, _make_clf(), tools=[])
        assert result["tools_called"] == []

    def test_request_object_preserved(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert result["request"] == sample_request

    def test_processing_ms_is_non_negative(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert result["processing_ms"] >= 0

    def test_processing_ms_is_integer(self, sample_request):
        result = _run(sample_request, _make_clf())
        assert isinstance(result["processing_ms"], int)
