"""test_critical_bug.py — End-to-end demo: critical bug report through escalation + audit hook."""

import json
from pathlib import Path

from escalation import EscalationSystem, pre_tool_use_hook, AUDIT_LOG_PATH

SEP = "=" * 64

CRITICAL_BUG = {
    "id": 999,
    "name": "Alex Rivera",
    "email": "alex.rivera@bigclient.com",
    "subject": "URGENT: Complete data loss after today's update — all reports gone",
    "message": (
        "After the v2.5.0 update deployed this morning ALL of our historical reports "
        "have disappeared from the dashboard. 3000+ records are gone. "
        "Our entire finance team is blocked and we have an external audit tomorrow. "
        "Steps to reproduce: 1. Log in  2. Navigate to Reports  3. Dashboard is empty. "
        "This is a system-down, data-loss situation — we need an immediate fix."
    ),
    "timestamp": "2026-04-28T09:15:00",
}

# Coordinator classification that would be produced for this request
CLASSIFICATION = {
    "category": "bug_report",
    "confidence": 0.97,
    "impact": "critical",
    "reasoning": (
        "Customer explicitly describes data loss ('3000+ records gone'), "
        "full team blocked, and an imminent external deadline. "
        "Matches critical: system-down / data-loss threshold."
    ),
}


def section(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


# ── Reset audit log for a clean demo run ─────────────────────────────────────
if AUDIT_LOG_PATH.exists():
    AUDIT_LOG_PATH.unlink()

section("STEP 1 — Support request")
print(f"  From   : {CRITICAL_BUG['name']} <{CRITICAL_BUG['email']}>")
print(f"  Subject: {CRITICAL_BUG['subject']}")
print(f"  Message: {CRITICAL_BUG['message'][:120]}...")

section("STEP 2 — Coordinator classification")
for k, v in CLASSIFICATION.items():
    print(f"  {k:12s}: {v}")

section("STEP 3 — EscalationSystem.evaluate()")
escalation = EscalationSystem()
decision = escalation.evaluate(CLASSIFICATION)
print(f"  action : {decision['action']}")
print(f"  reason : {decision['reason']}")
if "queue" in decision:
    print(f"  queue  : {decision['queue']}")

section("STEP 4 — Full BugReportSpecialist pipeline (via Bedrock)")
print("  Running specialist — this will call generate_bug_ticket, triggering the hook...")
try:
    from specialists import dispatch

    response = dispatch(CRITICAL_BUG, CLASSIFICATION)

    print("\n  [Specialist response — first 800 chars]")
    print("  " + response[:800].replace("\n", "\n  "))
except Exception as exc:
    print(f"  ERROR: {exc}")

section("STEP 5 — Audit log (audit_log.jsonl)")
if AUDIT_LOG_PATH.exists():
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    if lines:
        for line in lines:
            entry = json.loads(line)
            print(
                f"  {entry['timestamp']}  "
                f"risk={entry['risk_level']:<10}  "
                f"tool={entry['tool']:<25}  "
                f"{entry['reason']}"
            )
        print(f"\n  {len(lines)} entry/entries written to {AUDIT_LOG_PATH}")
    else:
        print("  (empty)")
else:
    print("  (file not created)")

print(f"\n{SEP}\nDone.\n{SEP}\n")
