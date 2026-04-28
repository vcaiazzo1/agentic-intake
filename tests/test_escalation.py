"""Tests for escalation.py — EscalationSystem and pre_tool_use_hook."""
import json
import pytest


# ── EscalationSystem ──────────────────────────────────────────────────────────

class TestEscalationSystem:
    @pytest.fixture
    def escalation(self):
        from escalation import EscalationSystem
        return EscalationSystem()

    # Low confidence → escalate
    def test_low_confidence_triggers_escalation(self, escalation):
        result = escalation.evaluate({"confidence": 0.59, "impact": "medium", "category": "bug_report"})
        assert result["action"] == "escalate"

    def test_low_confidence_reason_mentions_confidence(self, escalation):
        result = escalation.evaluate({"confidence": 0.50, "impact": "low", "category": "general_question"})
        assert "confidence" in result["reason"].lower()

    def test_low_confidence_has_queue(self, escalation):
        result = escalation.evaluate({"confidence": 0.40, "impact": "low", "category": "general_question"})
        assert "queue" in result

    # Confidence at exactly 0.60 → no escalation from confidence alone
    def test_confidence_at_threshold_does_not_escalate(self, escalation):
        result = escalation.evaluate({"confidence": 0.60, "impact": "low", "category": "general_question"})
        assert result["action"] == "auto-handle"

    # Critical impact → escalate regardless of confidence
    def test_critical_impact_triggers_escalation(self, escalation):
        result = escalation.evaluate({"confidence": 0.95, "impact": "critical", "category": "bug_report"})
        assert result["action"] == "escalate"

    def test_critical_impact_routes_to_oncall(self, escalation):
        result = escalation.evaluate({"confidence": 0.95, "impact": "critical", "category": "bug_report"})
        assert result["queue"] == "oncall@company.com"

    # billing_issue + high impact → escalate
    def test_billing_high_impact_triggers_escalation(self, escalation):
        result = escalation.evaluate({"confidence": 0.80, "impact": "high", "category": "billing_issue"})
        assert result["action"] == "escalate"

    def test_billing_high_impact_routes_to_billing_queue(self, escalation):
        result = escalation.evaluate({"confidence": 0.80, "impact": "high", "category": "billing_issue"})
        assert result["queue"] == "billing-escalations@company.com"

    # Non-billing high impact → no escalation
    def test_bug_report_high_impact_does_not_escalate(self, escalation):
        result = escalation.evaluate({"confidence": 0.85, "impact": "high", "category": "bug_report"})
        assert result["action"] == "auto-handle"

    def test_feature_request_high_impact_does_not_escalate(self, escalation):
        result = escalation.evaluate({"confidence": 0.85, "impact": "high", "category": "feature_request"})
        assert result["action"] == "auto-handle"

    # Normal cases → auto-handle
    def test_normal_case_auto_handle(self, escalation):
        result = escalation.evaluate({"confidence": 0.85, "impact": "medium", "category": "feature_request"})
        assert result["action"] == "auto-handle"

    def test_auto_handle_result_has_reason(self, escalation):
        result = escalation.evaluate({"confidence": 0.90, "impact": "low", "category": "general_question"})
        assert "reason" in result

    # Edge: empty dict defaults confidence to 1.0 → auto-handle
    def test_empty_dict_defaults_to_auto_handle(self, escalation):
        result = escalation.evaluate({})
        assert result["action"] == "auto-handle"

    # Result structure
    def test_escalate_result_has_action_reason_queue(self, escalation):
        result = escalation.evaluate({"confidence": 0.30, "impact": "low", "category": "general_question"})
        assert "action" in result
        assert "reason" in result
        assert "queue" in result

    def test_auto_handle_result_has_action_and_reason(self, escalation):
        result = escalation.evaluate({"confidence": 0.80, "impact": "low", "category": "general_question"})
        assert "action" in result
        assert "reason" in result


# ── pre_tool_use_hook ─────────────────────────────────────────────────────────

class TestPreToolUseHook:
    @pytest.fixture(autouse=True)
    def redirect_audit_log(self, tmp_path, monkeypatch):
        """Redirect audit_log.jsonl writes to a temp file for every test."""
        import escalation
        log_path = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr(escalation, "AUDIT_LOG_PATH", log_path)
        return log_path

    @pytest.fixture
    def log_path(self, redirect_audit_log):
        return redirect_audit_log

    # --- flag_for_human ---

    def test_flag_for_human_returns_allowed_true(self, log_path):
        from escalation import pre_tool_use_hook
        result = pre_tool_use_hook("flag_for_human", {"reason": "Dispute over $600."})
        assert result["allowed"] is True

    def test_flag_for_human_returns_logged_true(self, log_path):
        from escalation import pre_tool_use_hook
        result = pre_tool_use_hook("flag_for_human", {"reason": "Legal threat."})
        assert result["logged"] is True

    def test_flag_for_human_writes_log_file(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "Overcharge."})
        assert log_path.exists()

    def test_flag_for_human_risk_level_is_high_risk(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "Legal threat."})
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["risk_level"] == "HIGH_RISK"

    def test_flag_for_human_log_tool_field(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "Test."})
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["tool"] == "flag_for_human"

    # --- generate_bug_ticket ---

    def test_generate_bug_ticket_critical_logged(self, log_path):
        from escalation import pre_tool_use_hook
        result = pre_tool_use_hook("generate_bug_ticket", {"all_data": {"severity": "critical"}})
        assert result["logged"] is True

    def test_generate_bug_ticket_critical_risk_level(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("generate_bug_ticket", {"all_data": {"severity": "critical"}})
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["risk_level"] == "CRITICAL"

    def test_generate_bug_ticket_non_critical_is_info(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("generate_bug_ticket", {"all_data": {"severity": "medium"}})
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["risk_level"] == "INFO"

    def test_generate_bug_ticket_high_severity_is_info(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("generate_bug_ticket", {"all_data": {"severity": "high"}})
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["risk_level"] == "INFO"

    # --- unwatched tools ---

    def test_unwatched_tool_returns_logged_false(self, log_path):
        from escalation import pre_tool_use_hook
        result = pre_tool_use_hook("analyze_severity", {"message": "App crash."})
        assert result["logged"] is False

    def test_unwatched_tool_returns_allowed_true(self, log_path):
        from escalation import pre_tool_use_hook
        result = pre_tool_use_hook("analyze_severity", {"message": "App crash."})
        assert result["allowed"] is True

    def test_unwatched_tool_does_not_write_log(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("analyze_severity", {"message": "App crash."})
        assert not log_path.exists()

    # --- log entry structure ---

    def test_log_entry_has_all_required_fields(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "Overcharge."})
        entry = json.loads(log_path.read_text().splitlines()[0])
        for field in ("timestamp", "tool", "input", "risk_level", "reason"):
            assert field in entry, f"Missing field: {field}"

    def test_log_entry_input_matches_tool_input(self, log_path):
        from escalation import pre_tool_use_hook
        tool_input = {"reason": "Big dispute."}
        pre_tool_use_hook("flag_for_human", tool_input)
        entry = json.loads(log_path.read_text().splitlines()[0])
        assert entry["input"] == tool_input

    def test_multiple_calls_append_entries(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "First."})
        pre_tool_use_hook("flag_for_human", {"reason": "Second."})
        lines = log_path.read_text().splitlines()
        assert len(lines) == 2

    def test_each_entry_is_valid_json(self, log_path):
        from escalation import pre_tool_use_hook
        pre_tool_use_hook("flag_for_human", {"reason": "Test."})
        pre_tool_use_hook("generate_bug_ticket", {"all_data": {"severity": "high"}})
        for line in log_path.read_text().splitlines():
            json.loads(line)  # raises if invalid
