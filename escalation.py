"""escalation.py — Escalation system and pre-tool-use audit hook."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path("audit_log.jsonl")

WATCHED_TOOLS = {"flag_for_human", "generate_bug_ticket"}


class EscalationSystem:
    """Evaluates whether a request should be escalated or auto-handled."""

    def evaluate(self, classification: dict[str, Any]) -> dict[str, Any]:
        confidence = float(classification.get("confidence", 1.0))
        impact = str(classification.get("impact", ""))
        category = str(classification.get("category", ""))

        if confidence < 0.6:
            return {
                "action": "escalate",
                "reason": f"Low confidence ({confidence:.0%}) — requires human review.",
                "queue": "human-review@company.com",
            }
        if impact == "critical":
            return {
                "action": "escalate",
                "reason": "Critical impact — immediate human escalation required.",
                "queue": "oncall@company.com",
            }
        if category == "billing_issue" and impact == "high":
            return {
                "action": "escalate",
                "reason": "High-impact billing issue — routed to billing escalations.",
                "queue": "billing-escalations@company.com",
            }
        return {"action": "auto-handle", "reason": "Within automated handling thresholds."}


def pre_tool_use_hook(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Intercept calls to flag_for_human and generate_bug_ticket.
    Logs to audit_log.jsonl before the tool executes.
    Returns {"allowed": True, "logged": True/False, "reason": "..."}.
    """
    if tool_name not in WATCHED_TOOLS:
        return {"allowed": True, "logged": False, "reason": "Tool not watched."}

    timestamp = datetime.now(timezone.utc).isoformat()

    if tool_name == "flag_for_human":
        risk_level = "HIGH_RISK"
        reason = f"flag_for_human: {tool_input.get('reason', '')}"
    else:  # generate_bug_ticket
        all_data = tool_input.get("all_data", {})
        severity = str(all_data.get("severity", "")).lower()
        if severity == "critical":
            risk_level = "CRITICAL"
            reason = "generate_bug_ticket with severity=critical"
        else:
            risk_level = "INFO"
            reason = f"generate_bug_ticket with severity={severity or 'unknown'}"

    entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "input": tool_input,
        "risk_level": risk_level,
        "reason": reason,
    }

    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return {"allowed": True, "logged": True, "reason": reason}
