"""specialists.py — Four specialist subagents for the agentic-intake pipeline.

Each specialist receives the full request context from the coordinator and uses
an agentic tool-use loop to process the request through its domain-specific tools.
"""

from __future__ import annotations

import json
from typing import Any

from bedrock_client import client, MODEL
from escalation import pre_tool_use_hook


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _validate_str(value: Any, name: str) -> str | dict:
    """Return an error dict if value is not a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        return {"error": f"'{name}' must be a non-empty string, got: {repr(value)}"}
    return value


def _llm_call(prompt: str, system: str, max_tokens: int = 512) -> str:
    """Single LLM call returning the first text block. Used inside tool implementations."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def _run_agent_loop(
    system: str,
    user_message: str,
    tools: list[dict],
    tool_handlers: dict[str, Any],
    max_iterations: int = 10,
) -> str:
    """Run an agentic tool-use loop until Claude returns a final text response."""
    messages: list[dict] = [{"role": "user", "content": user_message}]

    for _ in range(max_iterations):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            return next(
                (b.text for b in response.content if b.type == "text"), ""
            )

        # Append Claude's full response (including tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and collect results
        tool_results = []
        for block in tool_uses:
            handler = tool_handlers.get(block.name)
            if handler is None:
                result: Any = {"error": f"Unknown tool: {block.name}"}
            else:
                try:
                    result = handler(**block.input)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": f"Tool execution failed: {exc}"}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
            })

        messages.append({"role": "user", "content": tool_results})

    return "Agent loop reached maximum iterations without producing a final response."


def _build_context_message(request: dict, classification: dict) -> str:
    """Build the standard context block passed to every specialist."""
    confidence = float(classification.get("confidence", 0))
    return (
        "## Original Support Request\n\n"
        f"**From:** {request.get('name', 'Unknown')} <{request.get('email', '')}>\n"
        f"**Subject:** {request.get('subject', '(no subject)')}\n"
        f"**Received:** {request.get('timestamp', 'unknown')}\n\n"
        f"**Message:**\n{request.get('message', '')}\n\n"
        "---\n\n"
        "## Coordinator Analysis\n\n"
        f"- **Category:** `{classification.get('category')}`\n"
        f"- **Impact:** `{classification.get('impact')}`\n"
        f"- **Confidence:** {confidence:.0%}\n\n"
        f"**Coordinator reasoning:**\n{classification.get('reasoning', '')}\n\n"
        "---\n\n"
        "Use your tools to fully process this request, then provide your final response."
    )


# ── Specialist 1: BugReportSpecialist ─────────────────────────────────────────

class BugReportSpecialist:
    SYSTEM = """\
You are a senior technical support engineer specialising in bug investigation.
The coordinator has already classified this request — do NOT re-classify it.

Use your tools in this order:
  1. analyze_severity         — determine how severe the bug is
  2. extract_reproduction_steps — pull out reproduction steps from the message
  3. check_known_issues       — check if this matches any known issue
  4. generate_bug_ticket      — produce a formatted ticket with all gathered data

After calling all four tools, write a concise customer-facing response:
  - Acknowledge the issue empathetically
  - Share the severity assessment
  - List the reproduction steps you extracted (or ask for them if none found)
  - Mention whether a known issue was found
  - Confirm a bug ticket has been created and share its content
"""

    TOOLS: list[dict] = [
        {
            "name": "analyze_severity",
            "description": (
                "Analyzes the customer message and returns a severity level: "
                "critical, high, medium, or low. "
                "Does NOT check known issues, does NOT extract steps, does NOT generate a ticket."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "extract_reproduction_steps",
            "description": (
                "Extracts ordered reproduction steps from the customer message. "
                "Does NOT assess severity, does NOT look up known issues, does NOT create a ticket."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "check_known_issues",
            "description": (
                "Searches a mock knowledge base for issues matching the given subject. "
                "Does NOT analyze severity, does NOT extract steps, does NOT create a ticket."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "The support request subject line."},
                },
                "required": ["subject"],
            },
        },
        {
            "name": "generate_bug_ticket",
            "description": (
                "Generates a formatted bug ticket from all gathered data. "
                "Does NOT analyze severity, does NOT extract steps, does NOT search known issues. "
                "Call this last, after the other three tools."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "all_data": {
                        "type": "object",
                        "description": (
                            "Object containing severity, steps, known_issues, "
                            "and the original request details."
                        ),
                    },
                },
                "required": ["all_data"],
            },
        },
    ]

    # ── Tool implementations ───────────────────────────────────────────────────

    @staticmethod
    def _analyze_severity(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        result = _llm_call(
            prompt=f"Customer message:\n{message}\n\nReturn ONLY one word: critical, high, medium, or low.",
            system=(
                "You are a triage engineer. Evaluate the business impact of the described bug. "
                "critical=system-down/data-loss, high=major feature broken for many users, "
                "medium=partial degradation with workaround, low=minor/cosmetic. "
                "Reply with exactly one word."
            ),
            max_tokens=16,
        ).strip().lower()
        if result not in {"critical", "high", "medium", "low"}:
            result = "medium"
        return {"severity": result}

    @staticmethod
    def _extract_reproduction_steps(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        raw = _llm_call(
            prompt=(
                f"Customer message:\n{message}\n\n"
                "Extract ordered reproduction steps as a JSON array of strings. "
                "If no steps are discernible, return an empty array. "
                "Return ONLY valid JSON, no prose."
            ),
            system="You are a QA engineer extracting bug reproduction steps. Return valid JSON only.",
            max_tokens=512,
        ).strip()
        try:
            steps = json.loads(raw)
            if not isinstance(steps, list):
                steps = []
        except json.JSONDecodeError:
            steps = []
        return {"steps": steps}

    @staticmethod
    def _check_known_issues(subject: str) -> dict:
        err = _validate_str(subject, "subject")
        if isinstance(err, dict):
            return err
        # Mocked knowledge base
        known: dict[str, str] = {
            "export": "KI-1042: PDF export hangs on reports > 10 MB. Fix shipped in v2.4.1.",
            "login": "KI-0981: SSO redirect loop affects accounts with special chars in email.",
            "crash": "KI-1103: App crash on iOS 17.4 when camera permission is revoked mid-session.",
            "slow":  "KI-1077: Dashboard load time regression since v2.3.0 due to N+1 query.",
            "timeout": "KI-1088: API requests time out after 30s under heavy load. Mitigation: retry with backoff.",
        }
        subject_lower = subject.lower()
        matches = [v for k, v in known.items() if k in subject_lower]
        return {"known_issues": matches if matches else "none found"}

    @staticmethod
    def _generate_bug_ticket(all_data: dict) -> dict:
        if not isinstance(all_data, dict):
            return {"error": "'all_data' must be a dict."}
        ticket = _llm_call(
            prompt=(
                f"Data:\n{json.dumps(all_data, indent=2)}\n\n"
                "Generate a formatted bug ticket with these sections:\n"
                "Title, Severity, Reporter, Description, Reproduction Steps, "
                "Known Issues, Priority, Next Steps."
            ),
            system="You are a technical writer creating internal bug tickets. Be concise and structured.",
            max_tokens=800,
        )
        return {"ticket": ticket}

    def _make_handlers(self) -> dict[str, Any]:
        def _hooked_generate_bug_ticket(all_data: dict) -> dict:
            pre_tool_use_hook("generate_bug_ticket", {"all_data": all_data})
            return self._generate_bug_ticket(all_data)

        return {
            "analyze_severity":           lambda message: self._analyze_severity(message),
            "extract_reproduction_steps": lambda message: self._extract_reproduction_steps(message),
            "check_known_issues":         lambda subject: self._check_known_issues(subject),
            "generate_bug_ticket":        _hooked_generate_bug_ticket,
        }

    def process(self, request: dict, classification: dict) -> str:
        return _run_agent_loop(
            system=self.SYSTEM,
            user_message=_build_context_message(request, classification),
            tools=self.TOOLS,
            tool_handlers=self._make_handlers(),
        )


# ── Specialist 2: FeatureRequestSpecialist ────────────────────────────────────

class FeatureRequestSpecialist:
    SYSTEM = """\
You are a product specialist handling feature requests.
The coordinator has already classified this request — do NOT re-classify it.

Use your tools in this order:
  1. assess_complexity      — gauge implementation complexity
  2. score_business_value   — score the business value 1-10
  3. find_similar_requests  — check for duplicate or related requests
  4. generate_product_brief — produce a formatted product brief with all gathered data

After calling all four tools, write a concise customer-facing response:
  - Acknowledge the customer's need warmly
  - Confirm the feature has been logged
  - Mention if similar requests already exist
  - Set realistic expectations about the evaluation timeline
"""

    TOOLS: list[dict] = [
        {
            "name": "assess_complexity",
            "description": (
                "Assesses the implementation complexity of the feature: simple, medium, or complex. "
                "Does NOT score business value, does NOT search for similar requests, "
                "does NOT generate a brief."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "score_business_value",
            "description": (
                "Returns a business value score from 1 to 10 with brief reasoning. "
                "Does NOT assess complexity, does NOT search for similar requests, "
                "does NOT generate a brief."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "find_similar_requests",
            "description": (
                "Searches a mock backlog for similar past feature requests. "
                "Does NOT assess complexity, does NOT score value, does NOT generate a brief."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "generate_product_brief",
            "description": (
                "Generates a formatted product brief from all gathered data. "
                "Does NOT assess complexity, does NOT score value, does NOT search similar requests. "
                "Call this last."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "all_data": {
                        "type": "object",
                        "description": (
                            "Object with complexity, business_value, similar_requests, "
                            "and the original request details."
                        ),
                    },
                },
                "required": ["all_data"],
            },
        },
    ]

    @staticmethod
    def _assess_complexity(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        result = _llm_call(
            prompt=f"Feature request:\n{message}\n\nReturn ONLY one word: simple, medium, or complex.",
            system=(
                "You are a senior engineer estimating implementation complexity. "
                "simple=hours, medium=days-to-weeks, complex=months or major redesign. "
                "Reply with exactly one word."
            ),
            max_tokens=16,
        ).strip().lower()
        if result not in {"simple", "medium", "complex"}:
            result = "medium"
        return {"complexity": result}

    @staticmethod
    def _score_business_value(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        raw = _llm_call(
            prompt=(
                f"Feature request:\n{message}\n\n"
                'Return a JSON object with keys "score" (integer 1-10) '
                'and "reasoning" (one sentence).'
            ),
            system="You are a product manager assessing business value. Return valid JSON only.",
            max_tokens=128,
        ).strip()
        try:
            data = json.loads(raw)
            score = max(1, min(10, int(data.get("score", 5))))
            reasoning = str(data.get("reasoning", ""))
        except (json.JSONDecodeError, ValueError):
            score, reasoning = 5, "Unable to parse LLM response; defaulting to 5."
        return {"score": score, "reasoning": reasoning}

    @staticmethod
    def _find_similar_requests(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        backlog = [
            {"id": "FR-201", "summary": "Allow CSV export for all report types", "status": "planned"},
            {"id": "FR-187", "summary": "Dark mode support across the dashboard", "status": "in-review"},
            {"id": "FR-164", "summary": "Bulk user import via CSV", "status": "delivered"},
            {"id": "FR-133", "summary": "SSO via SAML 2.0", "status": "delivered"},
            {"id": "FR-099", "summary": "Webhook notifications on status change", "status": "planned"},
            {"id": "FR-211", "summary": "Mobile app for iOS and Android", "status": "in-review"},
            {"id": "FR-178", "summary": "Advanced reporting with custom date ranges", "status": "planned"},
        ]
        keywords = {w.lower() for w in message.split() if len(w) > 3}
        matches = [
            r for r in backlog
            if any(kw in r["summary"].lower() for kw in keywords)
        ]
        return {"similar_requests": matches if matches else "none"}

    @staticmethod
    def _generate_product_brief(all_data: dict) -> dict:
        if not isinstance(all_data, dict):
            return {"error": "'all_data' must be a dict."}
        brief = _llm_call(
            prompt=(
                f"Data:\n{json.dumps(all_data, indent=2)}\n\n"
                "Generate a product brief with these sections:\n"
                "Title, Summary, Business Value, Complexity, "
                "Similar Requests, Recommended Priority, Next Steps."
            ),
            system="You are a product manager writing internal feature briefs. Be concise and structured.",
            max_tokens=800,
        )
        return {"brief": brief}

    def _make_handlers(self) -> dict[str, Any]:
        return {
            "assess_complexity":     lambda message: self._assess_complexity(message),
            "score_business_value":  lambda message: self._score_business_value(message),
            "find_similar_requests": lambda message: self._find_similar_requests(message),
            "generate_product_brief": lambda all_data: self._generate_product_brief(all_data),
        }

    def process(self, request: dict, classification: dict) -> str:
        return _run_agent_loop(
            system=self.SYSTEM,
            user_message=_build_context_message(request, classification),
            tools=self.TOOLS,
            tool_handlers=self._make_handlers(),
        )


# ── Specialist 3: BillingSpecialist ───────────────────────────────────────────

class BillingSpecialist:
    SYSTEM = """\
You are a billing support specialist.
The coordinator has already classified this request — do NOT re-classify it.

Use your tools in this order:
  1. detect_urgency     — determine if this is urgent or normal priority
  2. identify_issue_type — classify the billing issue subtype
  3. check_policy       — retrieve the relevant billing policy
  4. flag_for_human     — escalate if the issue genuinely warrants human review (skip if not needed)
  5. generate_resolution — produce resolution steps using all gathered data

After calling the tools, write a concise, professional customer-facing response:
  - Acknowledge the billing concern
  - Reference the relevant policy
  - Outline concrete next steps
  - Note if the case has been escalated for human review
"""

    TOOLS: list[dict] = [
        {
            "name": "detect_urgency",
            "description": (
                "Detects whether the billing issue is urgent or normal priority. "
                "Does NOT classify the issue type, does NOT look up policy, "
                "does NOT flag for human review."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "identify_issue_type",
            "description": (
                "Classifies the billing issue as: overcharge, refund, subscription, or other. "
                "Does NOT detect urgency, does NOT look up policy, does NOT flag for human review."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Returns the relevant billing policy text for a given issue type. "
                "Does NOT detect urgency, does NOT classify the issue type, "
                "does NOT generate resolution steps."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "description": "One of: overcharge, refund, subscription, other.",
                    },
                },
                "required": ["issue_type"],
            },
        },
        {
            "name": "flag_for_human",
            "description": (
                "Creates an escalation flag so a human agent reviews this case. "
                "Does NOT resolve the issue, does NOT look up policy, does NOT classify the issue. "
                "Only call this when human review is genuinely required (e.g., disputes > $500, "
                "legal threats, or data discrepancies)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why this case needs human review."},
                },
                "required": ["reason"],
            },
        },
        {
            "name": "generate_resolution",
            "description": (
                "Generates structured resolution steps from all gathered billing data. "
                "Does NOT detect urgency, does NOT classify issue type, does NOT look up policy. "
                "Call this last."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "all_data": {
                        "type": "object",
                        "description": (
                            "Object with urgency, issue_type, policy, escalated flag, "
                            "and the original request details."
                        ),
                    },
                },
                "required": ["all_data"],
            },
        },
    ]

    @staticmethod
    def _detect_urgency(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        result = _llm_call(
            prompt=f"Billing message:\n{message}\n\nReturn ONLY one word: urgent or normal.",
            system=(
                "You are a billing triage specialist. "
                "urgent=service suspended, legal threat, overcharge > $500, or imminent deadline. "
                "Reply with exactly one word."
            ),
            max_tokens=8,
        ).strip().lower()
        if result not in {"urgent", "normal"}:
            result = "normal"
        return {"urgency": result}

    @staticmethod
    def _identify_issue_type(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        result = _llm_call(
            prompt=(
                f"Billing message:\n{message}\n\n"
                "Return ONLY one word: overcharge, refund, subscription, or other."
            ),
            system=(
                "You are a billing analyst. Classify the primary billing issue type. "
                "Reply with exactly one word from: overcharge, refund, subscription, other."
            ),
            max_tokens=16,
        ).strip().lower()
        if result not in {"overcharge", "refund", "subscription", "other"}:
            result = "other"
        return {"issue_type": result}

    @staticmethod
    def _check_policy(issue_type: str) -> dict:
        err = _validate_str(issue_type, "issue_type")
        if isinstance(err, dict):
            return err
        policies = {
            "overcharge": (
                "Overcharge Policy: Disputes must be filed within 60 days of the invoice date. "
                "Verified overcharges are refunded within 5-7 business days to the original payment method."
            ),
            "refund": (
                "Refund Policy: Refunds are available within 30 days of purchase for annual plans "
                "and within 7 days for monthly plans. "
                "Pro-rated refunds apply for annual plans after 30 days."
            ),
            "subscription": (
                "Subscription Policy: Subscriptions can be upgraded, downgraded, or cancelled at any time. "
                "Cancellations take effect at the end of the current billing period. "
                "No partial-month refunds on monthly plans."
            ),
            "other": (
                "General Billing Policy: Contact billing support with your account ID and invoice number. "
                "All billing inquiries are resolved within 3 business days."
            ),
        }
        policy = policies.get(issue_type.lower(), policies["other"])
        return {"policy": policy}

    @staticmethod
    def _flag_for_human(reason: str) -> dict:
        err = _validate_str(reason, "reason")
        if isinstance(err, dict):
            return err
        return {
            "escalated": True,
            "escalation_reason": reason,
            "assigned_queue": "billing-escalations@company.com",
            "sla_hours": 4,
        }

    @staticmethod
    def _generate_resolution(all_data: dict) -> dict:
        if not isinstance(all_data, dict):
            return {"error": "'all_data' must be a dict."}
        resolution = _llm_call(
            prompt=(
                f"Billing case data:\n{json.dumps(all_data, indent=2)}\n\n"
                "Generate numbered resolution steps for both the billing team and the customer."
            ),
            system="You are a billing specialist writing clear resolution steps. Be precise and professional.",
            max_tokens=600,
        )
        return {"resolution": resolution}

    def _make_handlers(self) -> dict[str, Any]:
        def _hooked_flag_for_human(reason: str) -> dict:
            pre_tool_use_hook("flag_for_human", {"reason": reason})
            return self._flag_for_human(reason)

        return {
            "detect_urgency":      lambda message: self._detect_urgency(message),
            "identify_issue_type": lambda message: self._identify_issue_type(message),
            "check_policy":        lambda issue_type: self._check_policy(issue_type),
            "flag_for_human":      _hooked_flag_for_human,
            "generate_resolution": lambda all_data: self._generate_resolution(all_data),
        }

    def process(self, request: dict, classification: dict) -> str:
        return _run_agent_loop(
            system=self.SYSTEM,
            user_message=_build_context_message(request, classification),
            tools=self.TOOLS,
            tool_handlers=self._make_handlers(),
        )


# ── Specialist 4: GeneralQuestionSpecialist ───────────────────────────────────

class GeneralQuestionSpecialist:
    SYSTEM = """\
You are a customer-success agent handling general inquiries.
The coordinator has already classified this request — do NOT re-classify it.

Use your tools in this order:
  1. identify_topic      — determine the topic category of the question
  2. assess_complexity   — determine if this is a simple or complex question
  3. find_documentation  — retrieve relevant documentation sections for the topic
  4. generate_response   — draft a full customer response using all gathered data

After calling all four tools, write a warm, clear, customer-facing response:
  - Directly answer the question
  - Reference the documentation you found
  - Offer one or two follow-up resources
"""

    TOOLS: list[dict] = [
        {
            "name": "identify_topic",
            "description": (
                "Identifies the primary topic category of the question "
                "(e.g., account, billing, api, onboarding, integrations, reporting). "
                "Does NOT assess complexity, does NOT find documentation, "
                "does NOT generate a response."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "assess_complexity",
            "description": (
                "Assesses whether the question is simple (answerable in one step) "
                "or complex (multi-step or highly nuanced). "
                "Does NOT identify the topic, does NOT find documentation, "
                "does NOT generate a response."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The raw customer message text."},
                },
                "required": ["message"],
            },
        },
        {
            "name": "find_documentation",
            "description": (
                "Returns relevant documentation sections for a given topic from the mock doc index. "
                "Does NOT identify the topic, does NOT assess complexity, "
                "does NOT generate a response."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic category to search documentation for.",
                    },
                },
                "required": ["topic"],
            },
        },
        {
            "name": "generate_response",
            "description": (
                "Generates a full draft response to the customer using all gathered data. "
                "Does NOT identify the topic, does NOT assess complexity, "
                "does NOT search documentation. Call this last."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "all_data": {
                        "type": "object",
                        "description": (
                            "Object with topic, complexity, documentation, "
                            "and the original request details."
                        ),
                    },
                },
                "required": ["all_data"],
            },
        },
    ]

    @staticmethod
    def _identify_topic(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        raw = _llm_call(
            prompt=(
                f"Customer question:\n{message}\n\n"
                'Return a JSON object with "topic" (a short category label such as '
                '"account", "billing", "api", "onboarding", "integrations", '
                '"permissions", "reporting", or "other") '
                'and "confidence" (float 0.0-1.0). Return ONLY valid JSON.'
            ),
            system="You are a support classifier. Return valid JSON only.",
            max_tokens=64,
        ).strip()
        try:
            data = json.loads(raw)
            return {
                "topic": str(data.get("topic", "other")),
                "confidence": float(data.get("confidence", 0.8)),
            }
        except (json.JSONDecodeError, ValueError):
            return {"topic": "other", "confidence": 0.5}

    @staticmethod
    def _assess_complexity(message: str) -> dict:
        err = _validate_str(message, "message")
        if isinstance(err, dict):
            return err
        result = _llm_call(
            prompt=f"Customer question:\n{message}\n\nReturn ONLY one word: simple or complex.",
            system=(
                "You are a support analyst. "
                "simple=single direct answer, complex=multi-step or highly contextual. "
                "Reply with exactly one word."
            ),
            max_tokens=8,
        ).strip().lower()
        if result not in {"simple", "complex"}:
            result = "simple"
        return {"complexity": result}

    @staticmethod
    def _find_documentation(topic: str) -> dict:
        err = _validate_str(topic, "topic")
        if isinstance(err, dict):
            return err
        # Mocked documentation index
        docs: dict[str, list[dict]] = {
            "account": [
                {"title": "Managing Your Account", "url": "/docs/account/manage",
                 "summary": "Update profile, password, and 2FA settings."},
                {"title": "Account Deletion", "url": "/docs/account/delete",
                 "summary": "How to permanently delete your account and data."},
            ],
            "billing": [
                {"title": "Billing FAQ", "url": "/docs/billing/faq",
                 "summary": "Common billing questions and answers."},
                {"title": "Invoice Management", "url": "/docs/billing/invoices",
                 "summary": "Download, dispute, or update billing information."},
            ],
            "api": [
                {"title": "API Getting Started", "url": "/docs/api/quickstart",
                 "summary": "Authentication, rate limits, and your first API call."},
                {"title": "API Reference", "url": "/docs/api/reference",
                 "summary": "Full endpoint documentation with examples."},
            ],
            "onboarding": [
                {"title": "Getting Started Guide", "url": "/docs/onboarding/start",
                 "summary": "Step-by-step setup for new users."},
                {"title": "Video Tutorials", "url": "/docs/onboarding/videos",
                 "summary": "Recorded walkthroughs of core features."},
            ],
            "integrations": [
                {"title": "Available Integrations", "url": "/docs/integrations/list",
                 "summary": "All supported third-party integrations."},
                {"title": "Webhook Setup", "url": "/docs/integrations/webhooks",
                 "summary": "Configure webhooks for real-time events."},
            ],
            "reporting": [
                {"title": "Report Builder", "url": "/docs/reporting/builder",
                 "summary": "Create and schedule custom reports."},
                {"title": "Exporting Data", "url": "/docs/reporting/export",
                 "summary": "Export reports as CSV, PDF, or Excel."},
            ],
            "permissions": [
                {"title": "Roles & Permissions", "url": "/docs/admin/roles",
                 "summary": "Configure user roles and access controls."},
                {"title": "SSO & SAML Setup", "url": "/docs/admin/sso",
                 "summary": "Set up single sign-on for your organisation."},
            ],
        }
        topic_lower = topic.lower()
        sections = docs.get(topic_lower)
        if not sections:
            sections = next(
                (v for k, v in docs.items() if k in topic_lower or topic_lower in k),
                [{"title": "Help Center", "url": "/docs",
                  "summary": "Browse all documentation."}],
            )
        return {"documentation": sections}

    @staticmethod
    def _generate_response(all_data: dict) -> dict:
        if not isinstance(all_data, dict):
            return {"error": "'all_data' must be a dict."}
        response = _llm_call(
            prompt=(
                f"Data:\n{json.dumps(all_data, indent=2)}\n\n"
                "Write a friendly, helpful customer response that directly answers the question, "
                "references the relevant documentation, and offers one or two follow-up resources."
            ),
            system="You are a customer-success agent writing clear, warm support responses.",
            max_tokens=600,
        )
        return {"response": response}

    def _make_handlers(self) -> dict[str, Any]:
        return {
            "identify_topic":     lambda message: self._identify_topic(message),
            "assess_complexity":  lambda message: self._assess_complexity(message),
            "find_documentation": lambda topic: self._find_documentation(topic),
            "generate_response":  lambda all_data: self._generate_response(all_data),
        }

    def process(self, request: dict, classification: dict) -> str:
        return _run_agent_loop(
            system=self.SYSTEM,
            user_message=_build_context_message(request, classification),
            tools=self.TOOLS,
            tool_handlers=self._make_handlers(),
        )


# ── Registry & dispatch ───────────────────────────────────────────────────────

SPECIALISTS: dict[str, Any] = {
    "bug_report":       BugReportSpecialist(),
    "feature_request":  FeatureRequestSpecialist(),
    "billing_issue":    BillingSpecialist(),
    "general_question": GeneralQuestionSpecialist(),
}


def dispatch(request: dict, classification: dict) -> str:
    """Route to the correct specialist. Raises KeyError for unknown category."""
    category = classification.get("category", "")
    specialist = SPECIALISTS.get(category)
    if specialist is None:
        raise KeyError(
            f"No specialist registered for category '{category}'. "
            f"Valid categories: {list(SPECIALISTS)}"
        )
    return specialist.process(request, classification)
