"""Tests for specialists.py — each specialist returns structured output."""
import pytest
from unittest.mock import MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_block(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _response(*content):
    r = MagicMock()
    r.content = list(content)
    return r


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_client(monkeypatch):
    """Patch the module-level 'client' used by _llm_call and _run_agent_loop."""
    import specialists
    client = MagicMock()
    monkeypatch.setattr(specialists, "client", client)
    return client


@pytest.fixture
def sample_request():
    return {
        "id": 1,
        "name": "Bob",
        "email": "bob@example.com",
        "subject": "App crash on export",
        "message": "The app crashes when I click Export.",
        "timestamp": "2026-04-28T10:00:00",
    }


def _classification(category, confidence=0.9, impact="high"):
    return {"category": category, "confidence": confidence, "impact": impact, "reasoning": "test"}


# ── BugReportSpecialist ───────────────────────────────────────────────────────

class TestBugReportSpecialist:
    def test_analyze_severity_returns_valid_level(self, mock_client):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(_text_block("high"))
        result = BugReportSpecialist._analyze_severity("App crashes on export.")
        assert result["severity"] in {"critical", "high", "medium", "low"}

    def test_analyze_severity_unknown_value_defaults_to_medium(self, mock_client):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(_text_block("severe"))
        result = BugReportSpecialist._analyze_severity("Something is broken.")
        assert result["severity"] == "medium"

    def test_analyze_severity_empty_message_returns_error(self):
        from specialists import BugReportSpecialist
        result = BugReportSpecialist._analyze_severity("")
        assert "error" in result

    def test_extract_reproduction_steps_returns_list(self, mock_client):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block('["Step 1: Click export", "Step 2: App crashes"]')
        )
        result = BugReportSpecialist._extract_reproduction_steps("Click export then crash.")
        assert "steps" in result
        assert isinstance(result["steps"], list)

    def test_extract_reproduction_steps_bad_json_returns_empty(self, mock_client):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(_text_block("not valid json"))
        result = BugReportSpecialist._extract_reproduction_steps("Some message.")
        assert result["steps"] == []

    def test_check_known_issues_matches_export_keyword(self):
        from specialists import BugReportSpecialist
        result = BugReportSpecialist._check_known_issues("Cannot export PDF report")
        assert result["known_issues"] != "none found"
        assert isinstance(result["known_issues"], list)

    def test_check_known_issues_no_match_returns_sentinel(self):
        from specialists import BugReportSpecialist
        result = BugReportSpecialist._check_known_issues("Something completely unrelated xyz")
        assert result["known_issues"] == "none found"

    def test_generate_bug_ticket_returns_ticket_string(self, mock_client):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("## Bug Ticket\nTitle: App Crash\nSeverity: high")
        )
        result = BugReportSpecialist._generate_bug_ticket({"severity": "high", "steps": []})
        assert "ticket" in result
        assert isinstance(result["ticket"], str)

    def test_generate_bug_ticket_non_dict_returns_error(self):
        from specialists import BugReportSpecialist
        result = BugReportSpecialist._generate_bug_ticket("not a dict")
        assert "error" in result

    def test_process_returns_string(self, mock_client, sample_request):
        from specialists import BugReportSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("We have logged your bug report and will investigate.")
        )
        result = BugReportSpecialist().process(sample_request, _classification("bug_report"))
        assert isinstance(result, str)
        assert len(result) > 0


# ── FeatureRequestSpecialist ──────────────────────────────────────────────────

class TestFeatureRequestSpecialist:
    def test_assess_complexity_returns_valid(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(_text_block("complex"))
        result = FeatureRequestSpecialist._assess_complexity("Add AI-powered scheduling.")
        assert result["complexity"] in {"simple", "medium", "complex"}

    def test_assess_complexity_unknown_defaults_to_medium(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(_text_block("hard"))
        result = FeatureRequestSpecialist._assess_complexity("Some feature.")
        assert result["complexity"] == "medium"

    def test_score_business_value_returns_int_in_range(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block('{"score": 7, "reasoning": "High demand feature."}')
        )
        result = FeatureRequestSpecialist._score_business_value("Feature request text.")
        assert "score" in result
        assert isinstance(result["score"], int)
        assert 1 <= result["score"] <= 10

    def test_score_business_value_bad_json_defaults_to_5(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(_text_block("not json"))
        result = FeatureRequestSpecialist._score_business_value("Request text.")
        assert result["score"] == 5

    def test_score_business_value_clamped_to_bounds(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block('{"score": 15, "reasoning": "Too high."}')
        )
        result = FeatureRequestSpecialist._score_business_value("Request.")
        assert result["score"] <= 10

    def test_find_similar_requests_matches_csv(self):
        from specialists import FeatureRequestSpecialist
        result = FeatureRequestSpecialist._find_similar_requests("I need CSV export functionality")
        assert result["similar_requests"] != "none"

    def test_find_similar_requests_no_match(self):
        from specialists import FeatureRequestSpecialist
        result = FeatureRequestSpecialist._find_similar_requests("xyzzy frobblezorp wumpus")
        assert result["similar_requests"] == "none"

    def test_generate_product_brief_returns_brief(self, mock_client):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("## Product Brief\nTitle: Feature\nComplexity: simple")
        )
        result = FeatureRequestSpecialist._generate_product_brief({"complexity": "simple"})
        assert "brief" in result
        assert isinstance(result["brief"], str)

    def test_generate_product_brief_non_dict_returns_error(self):
        from specialists import FeatureRequestSpecialist
        result = FeatureRequestSpecialist._generate_product_brief("not a dict")
        assert "error" in result

    def test_process_returns_string(self, mock_client, sample_request):
        from specialists import FeatureRequestSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("Thank you for your feature request.")
        )
        result = FeatureRequestSpecialist().process(sample_request, _classification("feature_request"))
        assert isinstance(result, str)


# ── BillingSpecialist ─────────────────────────────────────────────────────────

class TestBillingSpecialist:
    def test_detect_urgency_returns_valid(self, mock_client):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(_text_block("urgent"))
        result = BillingSpecialist._detect_urgency("I was overcharged $1000!")
        assert result["urgency"] in {"urgent", "normal"}

    def test_detect_urgency_unknown_defaults_to_normal(self, mock_client):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(_text_block("high"))
        result = BillingSpecialist._detect_urgency("Some billing issue.")
        assert result["urgency"] == "normal"

    def test_identify_issue_type_returns_valid(self, mock_client):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(_text_block("refund"))
        result = BillingSpecialist._identify_issue_type("I want a refund.")
        assert result["issue_type"] in {"overcharge", "refund", "subscription", "other"}

    def test_identify_issue_type_unknown_defaults_to_other(self, mock_client):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(_text_block("mystery"))
        result = BillingSpecialist._identify_issue_type("Billing issue.")
        assert result["issue_type"] == "other"

    def test_check_policy_overcharge_returns_policy(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._check_policy("overcharge")
        assert "policy" in result
        policy_lower = result["policy"].lower()
        assert "dispute" in policy_lower or "overcharge" in policy_lower

    def test_check_policy_refund_returns_policy(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._check_policy("refund")
        assert "policy" in result
        assert "refund" in result["policy"].lower()

    def test_check_policy_subscription_returns_policy(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._check_policy("subscription")
        assert "policy" in result
        assert "subscription" in result["policy"].lower()

    def test_check_policy_unknown_type_falls_back_to_general(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._check_policy("unknown_type_xyz")
        assert "policy" in result

    def test_flag_for_human_returns_escalation_dict(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._flag_for_human("Dispute over $800.")
        assert result["escalated"] is True
        assert "escalation_reason" in result
        assert "assigned_queue" in result
        assert "sla_hours" in result

    def test_flag_for_human_empty_reason_returns_error(self):
        from specialists import BillingSpecialist
        result = BillingSpecialist._flag_for_human("")
        assert "error" in result

    def test_generate_resolution_returns_resolution(self, mock_client):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("1. Verify account\n2. Process refund")
        )
        result = BillingSpecialist._generate_resolution({"urgency": "urgent", "issue_type": "refund"})
        assert "resolution" in result
        assert isinstance(result["resolution"], str)

    def test_process_returns_string(self, mock_client, sample_request):
        from specialists import BillingSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("We'll handle your billing issue right away.")
        )
        result = BillingSpecialist().process(sample_request, _classification("billing_issue"))
        assert isinstance(result, str)


# ── GeneralQuestionSpecialist ─────────────────────────────────────────────────

class TestGeneralQuestionSpecialist:
    def test_identify_topic_returns_topic_and_confidence(self, mock_client):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block('{"topic": "api", "confidence": 0.9}')
        )
        result = GeneralQuestionSpecialist._identify_topic("How do I use the API?")
        assert "topic" in result
        assert "confidence" in result

    def test_identify_topic_bad_json_defaults(self, mock_client):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(_text_block("not json"))
        result = GeneralQuestionSpecialist._identify_topic("Something.")
        assert result["topic"] == "other"
        assert result["confidence"] == pytest.approx(0.5)

    def test_assess_complexity_returns_valid(self, mock_client):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(_text_block("simple"))
        result = GeneralQuestionSpecialist._assess_complexity("How do I reset my password?")
        assert result["complexity"] in {"simple", "complex"}

    def test_assess_complexity_unknown_defaults_to_simple(self, mock_client):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(_text_block("moderate"))
        result = GeneralQuestionSpecialist._assess_complexity("Some question.")
        assert result["complexity"] == "simple"

    def test_find_documentation_known_topic_returns_docs(self):
        from specialists import GeneralQuestionSpecialist
        result = GeneralQuestionSpecialist._find_documentation("api")
        assert "documentation" in result
        assert len(result["documentation"]) > 0
        assert "title" in result["documentation"][0]

    def test_find_documentation_unknown_topic_returns_fallback(self):
        from specialists import GeneralQuestionSpecialist
        result = GeneralQuestionSpecialist._find_documentation("unknowntopicxyzzy")
        assert "documentation" in result
        assert len(result["documentation"]) > 0

    def test_generate_response_returns_response(self, mock_client):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("Here's the answer to your question about the API.")
        )
        result = GeneralQuestionSpecialist._generate_response({"topic": "api", "complexity": "simple"})
        assert "response" in result
        assert isinstance(result["response"], str)

    def test_generate_response_non_dict_returns_error(self):
        from specialists import GeneralQuestionSpecialist
        result = GeneralQuestionSpecialist._generate_response("not a dict")
        assert "error" in result

    def test_process_returns_string(self, mock_client, sample_request):
        from specialists import GeneralQuestionSpecialist
        mock_client.messages.create.return_value = _response(
            _text_block("Great question! Here's what you need to know.")
        )
        result = GeneralQuestionSpecialist().process(sample_request, _classification("general_question", impact="low"))
        assert isinstance(result, str)


# ── Shared helpers ────────────────────────────────────────────────────────────

class TestValidateStr:
    def test_empty_string_returns_error(self):
        from specialists import _validate_str
        result = _validate_str("", "message")
        assert isinstance(result, dict) and "error" in result

    def test_whitespace_only_returns_error(self):
        from specialists import _validate_str
        result = _validate_str("   ", "message")
        assert isinstance(result, dict) and "error" in result

    def test_non_string_returns_error(self):
        from specialists import _validate_str
        result = _validate_str(None, "message")
        assert isinstance(result, dict) and "error" in result

    def test_valid_string_returns_string(self):
        from specialists import _validate_str
        result = _validate_str("hello world", "message")
        assert result == "hello world"


# ── Dispatch ──────────────────────────────────────────────────────────────────

class TestDispatch:
    @pytest.mark.parametrize("category", ["bug_report", "feature_request", "billing_issue", "general_question"])
    def test_dispatch_routes_all_categories(self, mock_client, sample_request, category):
        from specialists import dispatch
        mock_client.messages.create.return_value = _response(
            _text_block(f"Handled as {category}.")
        )
        result = dispatch(sample_request, _classification(category))
        assert isinstance(result, str)

    def test_dispatch_unknown_category_raises_key_error(self, sample_request):
        from specialists import dispatch
        with pytest.raises(KeyError):
            dispatch(sample_request, _classification("unknown_category"))
