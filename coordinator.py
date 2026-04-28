"""coordinator.py — Main coordinator agent using Claude API tool-use orchestration.

Architecture:
  1. Coordinator calls Claude with a `classify_request` tool, which forces structured
     reasoning + classification (category, confidence, impact).
  2. The coordinator's analysis is passed *explicitly* as context to the appropriate
     specialist subagent.
  3. Returns a structured CoordinatorResponse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from bedrock_client import client, MODEL


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    category: str    # bug_report | feature_request | billing_issue | general_question
    confidence: float
    impact: str      # low | medium | high | critical
    reasoning: str


@dataclass
class CoordinatorResponse:
    category: str
    confidence: float
    impact: str
    subagent_output: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Coordinator: classification tool definition ───────────────────────────────

CLASSIFICATION_TOOL: dict[str, Any] = {
    "name": "classify_request",
    "description": (
        "After reasoning about the support request, call this tool to record your "
        "classification. Include your full reasoning so it can be forwarded to the "
        "specialist subagent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": (
                    "Step-by-step explanation of why you chose this category and impact. "
                    "Reference specific phrases from the customer's message."
                ),
            },
            "category": {
                "type": "string",
                "enum": [
                    "bug_report",
                    "feature_request",
                    "billing_issue",
                    "general_question",
                ],
                "description": "The primary classification of the support request.",
            },
            "confidence": {
                "type": "number",
                "description": (
                    "How confident you are in the classification, from 0.0 (uncertain) "
                    "to 1.0 (certain)."
                ),
            },
            "impact": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": (
                    "Estimated business impact. "
                    "critical=system-down/data-loss, high=major feature broken for many users, "
                    "medium=partial degradation with workaround, low=minor/cosmetic/question."
                ),
            },
        },
        "required": ["reasoning", "category", "confidence", "impact"],
    },
}

COORDINATOR_SYSTEM = """\
You are a senior support coordinator. Your job is to analyze incoming support requests
and classify them before handing off to the appropriate specialist.

Categories:
  - bug_report         → Something is broken or behaving unexpectedly
  - feature_request    → Request for new or enhanced functionality
  - billing_issue      → Questions or problems with payments, invoices, subscriptions
  - general_question   → How-to questions, clarifications, or anything else

Impact levels:
  - critical  → System down, data loss, security breach, blocking all users
  - high      → Major feature broken, affecting multiple users significantly
  - medium    → Feature partially degraded; a workaround exists
  - low       → Minor inconvenience, cosmetic issue, simple how-to question

Instructions:
  1. Read the request carefully.
  2. Reason step-by-step: what is the customer describing, what is the impact, what
     category fits best, and how confident are you?
  3. Call the `classify_request` tool with your reasoning and conclusions.
"""


# ── Specialist subagents ──────────────────────────────────────────────────────

_SPECIALIST_SYSTEMS: dict[str, str] = {
    "bug_report": """\
You are a senior technical support engineer specialising in bug investigation.
The coordinator has already classified this request — do NOT re-classify it.

Your response must:
  1. Acknowledge the reported issue clearly and empathetically.
  2. Ask up to three targeted diagnostic questions to isolate the root cause.
  3. Suggest any immediate workaround if one is known.
  4. Outline the escalation path (e.g., engineering ticket, hotfix review).
Be concise and technical.""",

    "feature_request": """\
You are a product specialist handling feature requests.
The coordinator has already classified this request — do NOT re-classify it.

Your response must:
  1. Acknowledge the customer's need warmly.
  2. Ask one clarifying question about the business use case.
  3. Explain how to officially submit or track the feature request.
  4. Set realistic expectations about the evaluation timeline.
Be empathetic and constructive.""",

    "billing_issue": """\
You are a billing support specialist.
The coordinator has already classified this request — do NOT re-classify it.

Your response must:
  1. Acknowledge the billing concern professionally.
  2. Request the minimum necessary account verification details.
  3. Briefly explain the relevant billing policy.
  4. Outline the concrete next steps to resolve the issue.
Be precise, reassuring, and professional.""",

    "general_question": """\
You are a customer-success agent handling general inquiries.
The coordinator has already classified this request — do NOT re-classify it.

Your response must:
  1. Directly answer the question or point to the most relevant documentation.
  2. Identify any unspoken need behind the question.
  3. Offer one or two follow-up resources.
Be friendly, clear, and thorough.""",
}


def _call_specialist(
    request: dict[str, Any],
    classification: ClassificationResult,
) -> str:
    """Route the request to the appropriate specialist with full coordinator context."""
    system = _SPECIALIST_SYSTEMS[classification.category]

    # Explicit context: specialist receives both the raw request AND the coordinator's analysis
    user_message = (
        "## Original Support Request\n\n"
        f"**From:** {request.get('name', 'Unknown')} <{request.get('email', '')}>\n"
        f"**Subject:** {request.get('subject', '(no subject)')}\n"
        f"**Received:** {request.get('timestamp', 'unknown')}\n\n"
        f"**Message:**\n{request.get('message', '')}\n\n"
        "---\n\n"
        "## Coordinator Analysis\n\n"
        f"- **Category:** `{classification.category}`\n"
        f"- **Impact:** `{classification.impact}`\n"
        f"- **Confidence:** {classification.confidence:.0%}\n\n"
        f"**Coordinator reasoning:**\n{classification.reasoning}\n\n"
        "---\n\n"
        f"Please handle this as the specialist for `{classification.category}` requests."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )


# ── Coordinator entry point ───────────────────────────────────────────────────

def process_request(request: dict[str, Any]) -> CoordinatorResponse:
    """
    Analyze a support request, classify it, and route it to the right specialist.

    Args:
        request: Dict with at minimum 'subject' and 'message' keys.

    Returns:
        CoordinatorResponse with category, confidence, impact, and subagent_output.
    """
    # Build coordinator prompt
    user_message = (
        "Please analyze and classify the following support request:\n\n"
        f"**From:** {request.get('name', 'Unknown')} <{request.get('email', '')}>\n"
        f"**Subject:** {request.get('subject', '(no subject)')}\n"
        f"**Received:** {request.get('timestamp', 'unknown')}\n\n"
        f"**Message:**\n{request.get('message', '')}\n\n"
        "Reason through this carefully, then call `classify_request`."
    )

    # Step 1 — Coordinator classifies via tool call (reasoning is inside the tool args)
    coordinator_response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=COORDINATOR_SYSTEM,
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "classify_request"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_block = next(
        (
            b
            for b in coordinator_response.content
            if b.type == "tool_use" and b.name == "classify_request"
        ),
        None,
    )
    if tool_block is None:
        raise RuntimeError("Coordinator did not return a classify_request tool call.")

    args = tool_block.input
    classification = ClassificationResult(
        category=args["category"],
        confidence=float(args["confidence"]),
        impact=args["impact"],
        reasoning=args["reasoning"],
    )

    print(
        f"[Coordinator] Reasoning: {classification.reasoning}\n"
        f"[Coordinator] → category={classification.category}"
        f"  impact={classification.impact}"
        f"  confidence={classification.confidence:.0%}"
    )

    # Step 2 — Route to specialist with full context
    subagent_output = _call_specialist(request, classification)

    return CoordinatorResponse(
        category=classification.category,
        confidence=classification.confidence,
        impact=classification.impact,
        subagent_output=subagent_output,
    )


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Pick a request from requests.json (default: first item, or pass index as arg)
    try:
        with open("requests.json", encoding="utf-8") as f:
            samples: list[dict[str, Any]] = json.load(f)
        idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        request = samples[idx % len(samples)]
    except FileNotFoundError:
        request = {
            "id": 0,
            "name": "Demo User",
            "email": "demo@example.com",
            "subject": "Cannot export my report",
            "message": (
                "I've been trying to export my monthly report to PDF for the past hour. "
                "The button shows a spinner and then nothing happens. I need this for a "
                "meeting in 30 minutes."
            ),
            "timestamp": "2026-04-28T10:00:00",
        }

    print(f"\nProcessing request #{request.get('id')}: {request.get('subject')}")
    print("=" * 64)

    result = process_request(request)

    print("\n" + "=" * 64)
    print("STRUCTURED RESPONSE")
    print("=" * 64)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
