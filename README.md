# agentic-intake

> Agentic customer support triage on AWS Bedrock — coordinator → escalation → specialist, end to end.

---

## The problem

Picture a support inbox receiving 200 tickets a day. Bug reports land next to feature requests. Billing emergencies sit buried beneath routine how-to questions. A human reads each one, decides what it is, judges how urgent it is, writes a response, and decides whether to escalate. It is slow, inconsistent, and expensive — and it does not scale.

The real cost is not the volume. It is the variance. The same critical billing issue gets triaged differently on a Monday morning versus a Friday afternoon. Confidence and impact are gut calls, not data. High-risk actions — flagging a customer for human review, creating a P1 bug ticket — happen with no audit trail.

---

## The solution

`agentic-intake` is a multi-agent triage pipeline built on AWS Bedrock. It takes a raw support request and routes it through three stages:

1. **A coordinator agent** classifies the request using forced structured tool-use, producing a category, confidence score, impact level, and step-by-step reasoning — every time, in the same format.
2. **An escalation layer** applies deterministic rules to that classification: low confidence, critical impact, or high-impact billing all trigger immediate human escalation.
3. **A domain specialist subagent** runs its own tool-use loop — 4–5 purpose-built tools — to produce a complete, actionable response.

Every high-risk tool call is intercepted by a `pre_tool_use_hook` and appended to an immutable audit log before it executes.

---

## Architecture

```
  INPUT
  { id, name, email, subject, message, timestamp }
           │
           ▼
  ┌─────────────────────────────────────┐
  │           COORDINATOR               │
  │  Tool: classify_request (forced)    │
  │  → category                         │
  │  → confidence  (0.0 – 1.0)          │
  │  → impact      (low/med/high/crit)  │
  │  → reasoning   (step-by-step)       │
  └──────────────┬──────────────────────┘
                 │  ClassificationResult
                 ▼
  ┌─────────────────────────────────────┐
  │         ESCALATION CHECK            │
  │  Rule 1: confidence < 0.6           │
  │  Rule 2: impact == critical         │
  │  Rule 3: billing + high impact      │
  │  → escalate (human) or auto-handle  │
  └──────────────┬──────────────────────┘
                 │
       ┌─────────┴──────────┐
       │ auto-handle        │ escalated
       ▼                    ▼
  ┌──────────────────┐   human queue
  │  SPECIALIST      │
  │  AGENT DISPATCH  │
  │                  │
  │  bug_report      │  feature_request
  │  ─────────────   │  ────────────────
  │  analyze_sev     │  assess_complexity
  │  extract_steps   │  score_biz_value
  │  check_known     │  find_similar
  │  gen_ticket *    │  gen_brief
  │                  │
  │  billing_issue   │  general_question
  │  ─────────────   │  ────────────────
  │  detect_urgency  │  identify_topic
  │  identify_type   │  assess_complexity
  │  check_policy    │  find_docs
  │  flag_human *    │  gen_response
  │  gen_resolution  │
  └──────┬───────────┘
         │ * = PreToolUse hooked
         ▼
  ┌─────────────────────────────────────┐
  │        PRE_TOOL_USE HOOK            │
  │  Fires on: generate_bug_ticket      │
  │            flag_for_human           │
  │  Writes to: audit_log.jsonl         │
  │  { timestamp, tool, input,          │
  │    risk_level, reason }             │
  └──────────────┬──────────────────────┘
                 ▼
  OUTPUT
  { request, classification, escalated,
    escalation_detail, specialist_output,
    tools_called, processing_ms }
```

---

## Key features

### Explicit context passing between agents

There is no shared memory between the coordinator and the specialist. Context is passed as a structured Markdown block — the original customer message, the coordinator's classification, and the full step-by-step reasoning — injected as the specialist's first user message. The specialist always knows what the coordinator concluded and why, without re-classifying.

### Confidence + impact scoring

Every classification carries a numeric confidence (0.0–1.0) and a four-level impact rating. These are not post-hoc labels — they are required fields in the `classify_request` tool schema, forcing the model to reason about uncertainty explicitly before routing.

### PreToolUse hook for audit trail

High-risk tool calls (`generate_bug_ticket`, `flag_for_human`) are intercepted in Python before they execute. Each call is appended as a JSONL line to `audit_log.jsonl` with a timestamp, the full tool input, a risk level (`INFO` / `HIGH_RISK` / `CRITICAL`), and the reason. The tool always proceeds — but nothing goes unlogged.

### Adversarial evaluation scorecard

The classifier is stress-tested against 15 hand-crafted adversarial cases in three groups: genuinely ambiguous requests, requests with subjects that contradict the body, and edge cases (empty messages, foreign-language tickets, all-emoji subjects). Strict accuracy, acceptable accuracy, per-category precision/recall, and false-confidence rate are computed and written to `scorecard.json`.

---

## Setup and installation

**Requirements:** Python 3.11+, the `anthropic` SDK, pytest, and an AWS profile with Bedrock access.

```bash
pip install anthropic pytest
```

Add a `bootcamp` profile to `~/.aws/config`:

```ini
[profile bootcamp]
region = us-east-1
# your SSO or key configuration here
```

The project uses `us.anthropic.claude-sonnet-4-20250514-v1:0` via cross-region inference. Model and profile are configured in `bedrock_client.py` — change them there to switch.

---

## How to run

```bash
# Generate 50 synthetic support requests
python generate_requests.py

# Run the full triage pipeline (all 50 requests)
python pipeline.py

# Run on only the first 5
python pipeline.py 5

# Run the coordinator alone on a single request
python coordinator.py        # uses requests.json index 0
python coordinator.py 3      # uses requests.json index 3

# Run the adversarial evaluation
python evaluation.py
python evaluation.py --dry-run   # validate cases only, no API calls

# Run the offline test suite (no AWS credentials required)
pytest
pytest -v
```

---

## Example output

Request from Frank Brown — search completely broken, affecting the whole team:

```
Request #1 — Frank Brown <frank.brown13@hotmail.com>
Subject   : Search returns no results for any query
Category  : bug_report
Impact    : high  |  Confidence: 0.90
Escalated : No (auto-handle)
Tools     : analyze_severity → extract_reproduction_steps → check_known_issues → generate_bug_ticket
Time      : 30,536 ms
```

Specialist response (excerpt):

```
Dear Frank,

Thank you for reporting this search functionality issue. I've classified
this as a high severity issue given that the search function is completely
non-functional and multiple team members are experiencing the same problem.

Bug Ticket Created:

  Title    : Search functionality returning no results for all queries
  Severity : High
  Reporter : Frank Brown <frank.brown13@hotmail.com>
  Priority : High — Critical functionality impacting multiple users

  Next Steps:
  1. Investigate search service status and logs starting from 10:00 AM on 2025-06-19
  2. Verify search index integrity
  3. Check database connectivity for search components
  4. Reproduce issue and document steps

Our engineering team is already investigating and will prioritize this
given the widespread impact.

Best regards,
Technical Support Team
```

---

## Scorecard results

Evaluated against 15 adversarial cases across three difficulty groups.

| Metric                  | Score  |
|-------------------------|--------|
| Strict accuracy         | 80.0%  |
| Acceptable accuracy     | 100.0% |
| Avg confidence          | 0.813  |
| False-confidence rate   | 0.0%   |

**By category:**

| Category          | Precision | Recall |
|-------------------|-----------|--------|
| bug_report        | 83.3%     | 83.3%  |
| feature_request   | 80.0%     | 80.0%  |
| billing_issue     | 50.0%     | 100.0% |
| general_question  | 100.0%    | 66.7%  |

**By case type:**

| Type                | Strict acc | Acceptable acc | Avg conf |
|---------------------|------------|----------------|----------|
| ambiguous           | 60.0%      | 100.0%         | 0.83     |
| misleading_subject  | 100.0%     | 100.0%         | 0.94     |
| edge_case           | 80.0%      | 100.0%         | 0.67     |

The classifier never produced a high-confidence wrong answer (false-confidence rate = 0%). When it was wrong, it said so — confidence dropped appropriately on genuinely ambiguous and edge cases. It scored a perfect 5/5 on misleading subjects, correctly ignoring subject lines that contradicted the message body (including an all-caps "URGENT: Complete System Outage" that turned out to be a dark-mode feature request).

---

## What's next

**1. Prompt caching on system prompts.**
The coordinator and all four specialist system prompts are sent uncached on every request. Adding `cache_control: {"type": "ephemeral"}` to these long, static prompts would cut latency and cost at scale — the specialist prompts alone are several hundred tokens each.

**2. Async concurrency in the pipeline.**
`pipeline.py` processes requests sequentially. Converting `run_pipeline()` to use `asyncio` with a bounded semaphore would let the pipeline process dozens of requests in parallel, reducing wall-clock time from minutes to seconds for large batches.

**3. Real tool integrations.**
Every specialist tool (`check_known_issues`, `find_documentation`, `check_policy`) currently returns hardcoded mock data. The next step is wiring these to real backends: a vector-search knowledge base for `find_documentation`, a Jira/Linear API for `generate_bug_ticket`, and a billing platform SDK for `check_policy` and `generate_resolution`.

---

## Built with Claude Code

Every component in this project was built interactively with [Claude Code](https://claude.ai/code) — the Bedrock client, the coordinator, the escalation system, the four specialist agents, the full pipeline, the adversarial evaluation harness, and the test suite. Each was a focused, single-purpose prompt. The architecture in this README reflects the system as it actually runs, not as it was planned.
