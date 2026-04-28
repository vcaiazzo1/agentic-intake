# CLAUDE.md

## What this project does

`agentic-intake` is a Python-based agentic customer support triage system. It receives raw support requests (bug reports, feature requests, billing issues, and general questions) and routes each one through a three-stage pipeline: a coordinator agent classifies the request using structured tool-use, an escalation layer checks whether the classification warrants immediate human intervention, and then a domain-specific specialist subagent runs its own tool-use loop to produce a complete, actionable response. All high-risk tool calls are intercepted and appended to an audit log before they execute. The project is a demonstration of coordinator → specialist multi-agent patterns on AWS Bedrock.

---

## Architecture

```
  INPUT: request dict (id, name, email, subject, message, timestamp)
           │
           ▼
  ┌──────────────────────────────────┐
  │          COORDINATOR             │
  │  classify_request tool (forced)  │
  │  → category, confidence, impact, │
  │    reasoning                     │
  └──────────────┬───────────────────┘
                 │  ClassificationResult
                 ▼
  ┌──────────────────────────────────┐
  │        ESCALATION SYSTEM         │
  │  Rules evaluated in order:       │
  │  1. confidence < 0.6 → escalate  │
  │  2. impact == critical → escalate│
  │  3. billing + high → escalate    │
  │  otherwise → auto-handle         │
  └──────────────┬───────────────────┘
                 │  escalation_result
                 ▼
  ┌──────────────────────────────────────────────────────────┐
  │                    SPECIALIST DISPATCH                    │
  │                                                          │
  │  bug_report       │ feature_request │ billing_issue      │
  │  ─────────────    │ ──────────────  │ ─────────────      │
  │  analyze_severity │ assess_complex  │ detect_urgency     │
  │  extract_steps    │ score_biz_value │ identify_issue_type│
  │  check_known_bugs │ find_similar    │ check_policy       │
  │  generate_ticket  │ gen_brief       │ flag_for_human *   │
  │                   │                 │ generate_resolution│
  │                                                          │
  │  general_question                                        │
  │  ────────────────                                        │
  │  identify_topic                                          │
  │  assess_complexity                                       │
  │  find_documentation                                      │
  │  generate_response                                       │
  └──────────────┬───────────────────────────────────────────┘
                 │                         * = PreToolUse hooked
                 ▼
  ┌──────────────────────────────────┐
  │        PRE_TOOL_USE HOOK         │
  │  Fires on:                       │
  │    - generate_bug_ticket         │
  │    - flag_for_human              │
  │  Appends to audit_log.jsonl      │
  └──────────────┬───────────────────┘
                 │
                 ▼
  OUTPUT: {request, classification, escalated,
           escalation_detail, specialist_output,
           tools_called, processing_ms}
```

---

## All files and what each does

| File | Purpose |
|---|---|
| `bedrock_client.py` | Creates the shared `AnthropicBedrock` client and exports `client` and `MODEL`. All other modules import from here. |
| `coordinator.py` | Defines `CLASSIFICATION_TOOL`, the coordinator system prompt, and `process_request()`. Forces a `classify_request` tool call so classification is always structured. Also contains four simple specialist prompts used when running the coordinator alone (not the pipeline). |
| `specialists.py` | Four specialist classes (`BugReportSpecialist`, `FeatureRequestSpecialist`, `BillingSpecialist`, `GeneralQuestionSpecialist`). Each defines its own tools, tool implementations, and runs an agentic `_run_agent_loop`. Also exports `dispatch()` and the module-level `_tool_calls_log`. |
| `escalation.py` | `EscalationSystem.evaluate()` applies three escalation rules to a classification dict. `pre_tool_use_hook()` intercepts `generate_bug_ticket` and `flag_for_human` calls and appends a JSONL entry to `audit_log.jsonl`. |
| `pipeline.py` | Wires coordinator → escalation → specialists into one `run_pipeline()` function. Reads `requests.json`, calls the pipeline for each, writes `results.json`, and prints a summary. |
| `evaluation.py` | Adversarial evaluation harness. Loads `adversarial_cases.json`, classifies each with the coordinator only, computes strict/acceptable accuracy, precision, recall, false-confidence rate, and stratified results by case type. Writes `scorecard.json`. |
| `generate_requests.py` | Generates `requests.json` — 50 synthetic support requests (25 bug reports, 10 feature requests, 10 billing issues, 5 general questions) with random names, emails, and timestamps. |
| `tests/conftest.py` | Injects a mock `bedrock_client` module into `sys.modules` before any project code is imported, so tests never make AWS calls. |
| `tests/test_coordinator.py` | Unit tests for the coordinator: tool call extraction, `ClassificationResult` construction, routing to specialists, confidence/impact mapping. |
| `tests/test_escalation.py` | Unit tests for `EscalationSystem.evaluate()` covering all three escalation rules plus auto-handle paths, and for `pre_tool_use_hook()` covering both watched tools and unwatched tools. |
| `tests/test_pipeline.py` | Integration-style tests for `run_pipeline()`: mock classifies, mock specialist output, `escalated` flag propagation, tool log capture. |
| `tests/test_specialists.py` | Unit tests for each of the four specialist tool implementations: input validation, JSON parsing failures, mock LLM responses, known-issue lookups, and `_run_agent_loop` iteration. |
| `test_critical_bug.py` | Standalone smoke test (not in the `tests/` suite) for the full pipeline end-to-end on a single hardcoded critical bug request. Useful for manual spot-checking. |
| `adversarial_cases.json` | 15 hand-crafted adversarial requests in three groups: `ambiguous` (5 cases where the correct label is genuinely debatable), `misleading_subject` (5 where the subject contradicts the body), and `edge_case` (5 unusual or underspecified requests). Each entry includes `expected_category`, `acceptable_categories`, and `notes`. |
| `requests.json` | 50 generated support requests used as the main test batch for the pipeline. |
| `results.json` | Output of the most recent `pipeline.py` run — one JSON object per request. |
| `scorecard.json` | Output of the most recent `evaluation.py` run — summary metrics, per-category precision/recall, stratified results, and raw per-case data. |
| `audit_log.jsonl` | Append-only audit log of every `generate_bug_ticket` and `flag_for_human` call, written by `pre_tool_use_hook`. |

---

## Environment setup

**Requirements:** Python 3.11+, the `anthropic` SDK, and pytest.

```bash
pip install anthropic pytest
```

**AWS credentials:** The project uses the `bootcamp` AWS profile via `AnthropicBedrock`. Add this to `~/.aws/config`:

```ini
[profile bootcamp]
region = us-east-1
# ... your SSO or key configuration
```

**Model:** `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4, cross-region inference prefix `us.`)

**Client configuration** (`bedrock_client.py`):

```python
client = anthropic.AnthropicBedrock(
    aws_profile="bootcamp",
    aws_region="us-east-1",
)
MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"
```

All modules import `client` and `MODEL` from `bedrock_client.py`. To switch models or profiles, change only that file.

---

## How to run

### Generate test requests

```bash
python generate_requests.py
# writes requests.json (50 synthetic support requests)
```

### Run the full pipeline

```bash
python pipeline.py          # all 50 requests
python pipeline.py 5        # first 5 only
```

Output is printed per-request (category, impact, confidence, escalated, tools called, time). Final summary shows totals and category breakdown. Writes `results.json`.

### Run the adversarial evaluation

```bash
python evaluation.py            # all 15 adversarial cases
python evaluation.py --dry-run  # validate adversarial_cases.json only, no API calls
```

Writes `scorecard.json` and prints a detailed report with strict accuracy, acceptable accuracy, per-category precision/recall, false-confidence rate, and a per-case table.

### Run the coordinator alone (single request)

```bash
python coordinator.py       # uses requests.json index 0
python coordinator.py 3     # uses requests.json index 3
```

### Run the test suite

```bash
pytest                      # all tests (no AWS calls)
pytest tests/               # same, explicit directory
pytest -v                   # verbose output
```

Tests are fully offline — `conftest.py` mocks the Bedrock client.

---

## How Claude Code was used to build this

Each major component was built with a focused prompt to Claude Code. The prompts below are the ones actually used:

**1. Bedrock client (`bedrock_client.py`)**
> "Create a bedrock_client.py that sets up an AnthropicBedrock client using aws_profile=bootcamp and aws_region=us-east-1 with model us.anthropic.claude-sonnet-4-20250514-v1:0. Include a test() function that sends a hello message and prints the response."

**2. Coordinator agent (`coordinator.py`)**
> "Build a coordinator.py that uses Claude's tool_use feature with a classify_request tool to classify support requests into bug_report, feature_request, billing_issue, or general_question. Force the tool call with tool_choice. Include a ClassificationResult dataclass with category, confidence, impact, and reasoning. After classification, route to a specialist subagent that receives the original request plus the coordinator's full reasoning as explicit context."

**3. Escalation system and PreToolUse hook (`escalation.py`)**
> "Add an escalation system with three rules: escalate if confidence < 0.6, if impact is critical, or if it's a high-impact billing issue. Add a pre_tool_use_hook that intercepts generate_bug_ticket and flag_for_human calls and appends a JSONL entry to audit_log.jsonl with timestamp, tool name, input, risk level, and reason. Return allowed=True always so the tool still executes."

**4. Four specialist subagents (`specialists.py`)**
> "Create four specialist subagents for bug_report, feature_request, billing_issue, and general_question. Each should use an agentic tool-use loop (_run_agent_loop) with 4-5 domain-specific tools. Each tool must do exactly one thing (strict descriptions so Claude doesn't conflate tools). The last tool in each specialist synthesises all prior tool outputs. Wire the pre_tool_use_hook onto generate_bug_ticket in BugReportSpecialist and flag_for_human in BillingSpecialist. Add a dispatch() function and a module-level tool call log."

**5. Full pipeline (`pipeline.py`)**
> "Write a pipeline.py that wires coordinator → escalation → specialists. Load requests.json, run each request, capture tools_called and processing_ms, write results.json, and print a summary. Import ClassificationResult and CLASSIFICATION_TOOL from coordinator.py so classification logic is not duplicated."

**6. Adversarial evaluation (`evaluation.py`)**
> "Build an adversarial evaluation harness that loads adversarial_cases.json and classifies each case using only the coordinator. Compute strict accuracy, acceptable accuracy (using acceptable_categories), per-category precision and recall, false-confidence rate (high-confidence wrong predictions), and stratified breakdown by case type. Print a formatted scorecard and write scorecard.json."

**7. Test suite (`tests/`)**
> "Write a full pytest suite for coordinator, escalation, pipeline, and specialists. Mock the bedrock_client entirely in conftest.py by injecting a fake module into sys.modules before imports, so no AWS credentials are needed. Test tool call extraction, all escalation rule branches, the agent loop, input validation, JSON parse failure handling, and tool log capture."

---

## How subagents pass context explicitly

There is no shared state between the coordinator and specialist. Context is passed through the message itself.

`_build_context_message()` in `specialists.py` constructs a structured Markdown block that every specialist receives as its first user message:

```
## Original Support Request

**From:** <name> <email>
**Subject:** <subject>
**Received:** <timestamp>

**Message:**
<raw message text>

---

## Coordinator Analysis

- **Category:** `bug_report`
- **Impact:** `high`
- **Confidence:** 87%

**Coordinator reasoning:**
<full step-by-step reasoning from classify_request tool args>

---

Use your tools to fully process this request, then provide your final response.
```

This means:
- The specialist always has the original customer message (it can extract information itself)
- The specialist always has the coordinator's reasoning (it does not need to re-classify)
- The specialist's system prompt explicitly says "do NOT re-classify"

The reasoning field is captured from the `classify_request` tool call arguments, not from Claude's prose response. This is intentional: tool arguments are structured and reliable; prose can be truncated or omitted.

---

## How the PreToolUse hook works

`pre_tool_use_hook()` in `escalation.py` is called directly inside tool handler wrappers in `specialists.py` — it is not a Claude Code hook. It is a Python function that runs synchronously before the real tool executes.

**Where it fires:**

- `BugReportSpecialist._make_handlers()` wraps `generate_bug_ticket` with a closure that calls `pre_tool_use_hook("generate_bug_ticket", {"all_data": all_data})` before delegating to `_generate_bug_ticket`.
- `BillingSpecialist._make_handlers()` wraps `flag_for_human` the same way.

**What it does:**

1. Checks `tool_name` against `WATCHED_TOOLS = {"flag_for_human", "generate_bug_ticket"}`.
2. For `flag_for_human`: assigns risk level `HIGH_RISK`.
3. For `generate_bug_ticket`: assigns `CRITICAL` if `severity == "critical"`, otherwise `INFO`.
4. Writes one JSONL line to `audit_log.jsonl`:
   ```json
   {"timestamp": "...", "tool": "...", "input": {...}, "risk_level": "...", "reason": "..."}
   ```
5. Returns `{"allowed": True, "logged": True, "reason": "..."}` — the tool always executes.

**Design intent:** In production you would check the return value and block the tool if `allowed` were `False`. Here it is always `True` to demonstrate the pattern without adding policy enforcement.

---

## Known limitations

- **No real tool integrations.** All specialist tools (`check_known_issues`, `find_documentation`, `_check_policy`, etc.) use hardcoded mock data. In production these would call a real ticketing system, knowledge base, and billing platform.
- **No retry or rate-limit handling.** The pipeline catches exceptions per-request and logs an error string, but there is no backoff or retry on Bedrock throttling.
- **No prompt caching.** The coordinator system prompt and specialist system prompts are sent uncached on every request. Adding `cache_control: {"type": "ephemeral"}` to long system prompts would reduce latency and cost at scale.
- **Sequential processing.** `pipeline.py` processes requests one at a time. There is no async concurrency or batching.
- **`flag_for_human` never blocks.** The `pre_tool_use_hook` always returns `allowed: True`. A real implementation would check risk level and optionally return `allowed: False` to prevent the tool from executing.
- **Mock knowledge bases.** `check_known_issues` and `find_similar_requests` match on simple substring keywords, not semantic search. False negatives are frequent.
- **Adversarial cases are coordinator-only.** The evaluation harness tests classification accuracy but does not evaluate specialist response quality.
- **No persistence.** `results.json` and `scorecard.json` are overwritten on each run. There is no run history or result diffing.
