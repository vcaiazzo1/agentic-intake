"""Tests for coordinator.py — classification returns valid category and scores."""
import pytest
from unittest.mock import MagicMock

from coordinator import process_request, CoordinatorResponse


VALID_CATEGORIES = {"bug_report", "feature_request", "billing_issue", "general_question"}
VALID_IMPACTS = {"low", "medium", "high", "critical"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tool_block(name, input_dict, block_id="tu_1"):
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.input = input_dict
    b.id = block_id
    return b


def _text_block(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _response(*content):
    r = MagicMock()
    r.content = list(content)
    return r


def _classify_response(category, confidence, impact, reasoning="test reasoning"):
    return _response(
        _tool_block("classify_request", {
            "category": category,
            "confidence": confidence,
            "impact": impact,
            "reasoning": reasoning,
        })
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_client(monkeypatch):
    import coordinator
    client = MagicMock()
    monkeypatch.setattr(coordinator, "client", client)
    return client


@pytest.fixture
def sample_request():
    return {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "subject": "Login broken",
        "message": "I cannot log in to my account.",
        "timestamp": "2026-04-28T10:00:00",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestClassification:
    def test_returns_coordinator_response_type(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("bug_report", 0.95, "high"),
            _response(_text_block("We'll look into it.")),
        ]
        result = process_request(sample_request)
        assert isinstance(result, CoordinatorResponse)

    def test_category_is_valid(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("bug_report", 0.95, "high"),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        assert result.category in VALID_CATEGORIES

    def test_confidence_is_float_in_range(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("feature_request", 0.75, "medium"),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_value_preserved(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("billing_issue", 0.88, "high"),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        assert result.confidence == pytest.approx(0.88)

    def test_impact_is_valid(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("billing_issue", 0.88, "critical"),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        assert result.impact in VALID_IMPACTS

    def test_subagent_output_is_string(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("general_question", 0.90, "low"),
            _response(_text_block("Here is the answer.")),
        ]
        result = process_request(sample_request)
        assert isinstance(result.subagent_output, str)
        assert len(result.subagent_output) > 0

    def test_raises_if_no_tool_call(self, mock_client, sample_request):
        # Coordinator returns only text — no tool_use block
        mock_client.messages.create.return_value = _response(_text_block("I think it's a bug."))
        with pytest.raises(RuntimeError, match="classify_request"):
            process_request(sample_request)

    @pytest.mark.parametrize("category", sorted(VALID_CATEGORIES))
    def test_all_categories_returned_correctly(self, mock_client, sample_request, category):
        mock_client.messages.create.side_effect = [
            _classify_response(category, 0.85, "medium"),
            _response(_text_block("Specialist response.")),
        ]
        result = process_request(sample_request)
        assert result.category == category

    @pytest.mark.parametrize("impact", sorted(VALID_IMPACTS))
    def test_all_impacts_returned_correctly(self, mock_client, sample_request, impact):
        mock_client.messages.create.side_effect = [
            _classify_response("bug_report", 0.80, impact),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        assert result.impact == impact

    def test_to_dict_returns_expected_keys(self, mock_client, sample_request):
        mock_client.messages.create.side_effect = [
            _classify_response("bug_report", 0.9, "high"),
            _response(_text_block("Handled.")),
        ]
        result = process_request(sample_request)
        d = result.to_dict()
        assert set(d.keys()) == {"category", "confidence", "impact", "subagent_output"}
