"""pipeline.py — Full agentic pipeline: coordinator → escalation → specialist.

Usage:
    python pipeline.py          # process all requests
    python pipeline.py 5        # process first N requests
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from bedrock_client import client, MODEL
from coordinator import CLASSIFICATION_TOOL, COORDINATOR_SYSTEM, ClassificationResult
from escalation import EscalationSystem
import specialists as specialists_module
from specialists import dispatch as specialist_dispatch


ESCALATION = EscalationSystem()


# ── Step 1: coordinator classification ───────────────────────────────────────

def _classify(request: dict[str, Any]) -> ClassificationResult:
    user_message = (
        "Please analyze and classify the following support request:\n\n"
        f"**From:** {request.get('name', 'Unknown')} <{request.get('email', '')}>\n"
        f"**Subject:** {request.get('subject', '(no subject)')}\n"
        f"**Received:** {request.get('timestamp', 'unknown')}\n\n"
        f"**Message:**\n{request.get('message', '')}\n\n"
        "Reason through this carefully, then call `classify_request`."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=COORDINATOR_SYSTEM,
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "classify_request"},
        messages=[{"role": "user", "content": user_message}],
    )
    tool_block = next(
        (b for b in response.content if b.type == "tool_use" and b.name == "classify_request"),
        None,
    )
    if tool_block is None:
        raise RuntimeError("Coordinator did not return a classify_request tool call.")
    args = tool_block.input
    return ClassificationResult(
        category=args["category"],
        confidence=float(args["confidence"]),
        impact=args["impact"],
        reasoning=args["reasoning"],
    )


# ── Full pipeline for one request ─────────────────────────────────────────────

def run_pipeline(request: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()

    # Coordinator → classification
    classification = _classify(request)
    classification_dict = {
        "category": classification.category,
        "confidence": classification.confidence,
        "impact": classification.impact,
        "reasoning": classification.reasoning,
    }

    # Escalation check
    escalation_result = ESCALATION.evaluate(classification_dict)
    escalated = escalation_result["action"] == "escalate"

    # Specialist (agentic tool-use loop)
    specialists_module.clear_tool_log()
    specialist_output = specialist_dispatch(request, classification_dict)
    tools_called = specialists_module.get_tool_log()

    return {
        "request": request,
        "classification": classification_dict,
        "escalated": escalated,
        "escalation_detail": escalation_result,
        "specialist_output": specialist_output,
        "tools_called": tools_called,
        "processing_ms": round((time.monotonic() - t0) * 1000),
    }


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    if total == 0:
        print("No results to summarise.")
        return

    escalated_count = sum(1 for r in results if r["escalated"])
    avg_confidence = sum(r["classification"]["confidence"] for r in results) / total

    category_counts: dict[str, int] = {}
    for r in results:
        cat = r["classification"]["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Total processed : {total}")
    print(f"Escalation rate : {escalated_count}/{total} ({escalated_count / total:.0%})")
    print(f"Avg confidence  : {avg_confidence:.1%}")
    print("\nBreakdown by category:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat:<28} {count}")
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(limit: int | None = None) -> None:
    with open("requests.json", encoding="utf-8") as f:
        all_requests: list[dict[str, Any]] = json.load(f)

    batch = all_requests[:limit] if limit is not None else all_requests
    good_results: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []

    for i, request in enumerate(batch, 1):
        req_id = request.get("id", i)
        subject = request.get("subject", "(no subject)")
        print(f"\n[{i}/{len(batch)}] Request #{req_id}: {subject}")
        print("-" * 60)
        try:
            result = run_pipeline(request)
            clf = result["classification"]
            print(f"  Category  : {clf['category']}")
            print(f"  Impact    : {clf['impact']}")
            print(f"  Confidence: {clf['confidence']:.0%}")
            print(f"  Escalated : {result['escalated']}", end="")
            if result["escalated"]:
                print(f"  ← {result['escalation_detail']['reason']}", end="")
            print()
            print(f"  Tools     : {result['tools_called']}")
            print(f"  Time      : {result['processing_ms']} ms")
            all_results.append(result)
            good_results.append(result)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            all_results.append({"request": request, "error": str(exc)})

    out_path = Path("results.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path} ({len(all_results)} entries)")

    print_summary(good_results)


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=limit)
