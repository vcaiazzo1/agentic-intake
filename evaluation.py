"""evaluation.py — Adversarial evaluation harness for the coordinator classifier.

Usage:
    python evaluation.py                   # run all 15 adversarial cases
    python evaluation.py --dry-run         # validate case file only, no API calls

Produces:
    scorecard.json   — full machine-readable results
    stdout           — human-readable report
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from bedrock_client import client, MODEL
from coordinator import CLASSIFICATION_TOOL, COORDINATOR_SYSTEM, ClassificationResult


CASES_FILE = Path("adversarial_cases.json")
SCORECARD_FILE = Path("scorecard.json")

CATEGORIES = ["bug_report", "feature_request", "billing_issue", "general_question"]
HIGH_CONFIDENCE_THRESHOLD = 0.8


# ── Classifier (mirrors pipeline._classify, no specialist overhead) ───────────

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
        raise RuntimeError("Coordinator returned no classify_request tool call.")
    args = tool_block.input
    return ClassificationResult(
        category=args["category"],
        confidence=float(args["confidence"]),
        impact=args["impact"],
        reasoning=args["reasoning"],
    )


# ── Scorecard ─────────────────────────────────────────────────────────────────

class Scorecard:
    """Run adversarial cases against the classifier and compute evaluation metrics."""

    def __init__(self, cases: list[dict[str, Any]]) -> None:
        self.cases = cases
        self.results: list[dict[str, Any]] = []

    # ── Execution ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        print(f"\nRunning {len(self.cases)} adversarial cases against the coordinator...\n")
        for i, case in enumerate(self.cases, 1):
            expected = case["expected_category"]
            acceptable = case.get("acceptable_categories", [expected])
            subject_preview = (case.get("subject") or "").encode("ascii", "replace").decode()[:52]
            print(f"[{i:>2}/{len(self.cases)}] #{case['id']} ({case['type']:<18}) {subject_preview}")

            t0 = time.monotonic()
            try:
                result = _classify(case)
                elapsed_ms = round((time.monotonic() - t0) * 1000)
                predicted = result.category
                confidence = result.confidence

                correct = predicted == expected
                acceptable_correct = predicted in acceptable
                high_conf = confidence >= HIGH_CONFIDENCE_THRESHOLD
                false_conf = high_conf and not correct

                badge = "OK" if correct else ("~" if acceptable_correct else "XX")
                print(
                    f"  [{badge}] predicted={predicted:<20} conf={confidence:.0%}"
                    f"  expected={expected}  [{elapsed_ms} ms]"
                )

                self.results.append({
                    "id": case["id"],
                    "type": case["type"],
                    "subject": case.get("subject", ""),
                    "notes": case.get("notes", ""),
                    "expected_category": expected,
                    "acceptable_categories": acceptable,
                    "predicted_category": predicted,
                    "confidence": confidence,
                    "impact": result.impact,
                    "correct": correct,
                    "acceptable_correct": acceptable_correct,
                    "high_confidence": high_conf,
                    "false_confidence": false_conf,
                    "elapsed_ms": elapsed_ms,
                })

            except Exception as exc:
                elapsed_ms = round((time.monotonic() - t0) * 1000)
                print(f"  [XX] ERROR: {exc}")
                self.results.append({
                    "id": case["id"],
                    "type": case["type"],
                    "subject": case.get("subject", ""),
                    "notes": case.get("notes", ""),
                    "expected_category": expected,
                    "acceptable_categories": acceptable,
                    "predicted_category": None,
                    "confidence": None,
                    "impact": None,
                    "correct": False,
                    "acceptable_correct": False,
                    "high_confidence": False,
                    "false_confidence": False,
                    "error": str(exc),
                    "elapsed_ms": elapsed_ms,
                })

    # ── Metrics ───────────────────────────────────────────────────────────────

    def _precision_recall(self) -> dict[str, dict[str, float | int]]:
        """Strict per-category precision and recall (expected_category as ground truth)."""
        tp: dict[str, int] = defaultdict(int)
        fp: dict[str, int] = defaultdict(int)
        fn: dict[str, int] = defaultdict(int)

        for r in self.results:
            pred = r["predicted_category"]
            exp = r["expected_category"]
            if pred is None:
                fn[exp] += 1
            elif pred == exp:
                tp[pred] += 1
            else:
                fp[pred] += 1
                fn[exp] += 1

        out: dict[str, dict[str, float | int]] = {}
        for cat in CATEGORIES:
            p_denom = tp[cat] + fp[cat]
            r_denom = tp[cat] + fn[cat]
            out[cat] = {
                "tp": tp[cat],
                "fp": fp[cat],
                "fn": fn[cat],
                "precision": round(tp[cat] / p_denom, 4) if p_denom else 0.0,
                "recall": round(tp[cat] / r_denom, 4) if r_denom else 0.0,
            }
        return out

    def _false_confidence_rate(self) -> float:
        """Fraction of high-confidence predictions that were wrong (strict)."""
        high_conf = [r for r in self.results if r["high_confidence"]]
        if not high_conf:
            return 0.0
        false_conf = sum(1 for r in high_conf if r["false_confidence"])
        return round(false_conf / len(high_conf), 4)

    def _stratified_results(self) -> dict[str, dict[str, Any]]:
        """Per-type accuracy, confidence, and false-confidence breakdown."""
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in self.results:
            by_type[r["type"]].append(r)

        out: dict[str, dict[str, Any]] = {}
        for t, cases in by_type.items():
            total = len(cases)
            valid = [c for c in cases if c["confidence"] is not None]
            avg_conf = round(sum(c["confidence"] for c in valid) / len(valid), 4) if valid else 0.0
            out[t] = {
                "total": total,
                "strict_correct": sum(1 for c in cases if c["correct"]),
                "acceptable_correct": sum(1 for c in cases if c["acceptable_correct"]),
                "strict_accuracy": round(sum(1 for c in cases if c["correct"]) / total, 4),
                "acceptable_accuracy": round(sum(1 for c in cases if c["acceptable_correct"]) / total, 4),
                "avg_confidence": avg_conf,
                "false_confidence_count": sum(1 for c in cases if c["false_confidence"]),
            }
        return out

    # ── Scorecard assembly ────────────────────────────────────────────────────

    def build_scorecard(self) -> dict[str, Any]:
        total = len(self.results)
        valid = [r for r in self.results if r["confidence"] is not None]
        avg_conf = round(sum(r["confidence"] for r in valid) / len(valid), 4) if valid else 0.0

        strict_correct = sum(1 for r in self.results if r["correct"])
        acceptable_correct = sum(1 for r in self.results if r["acceptable_correct"])

        return {
            "summary": {
                "total_cases": total,
                "strict_correct": strict_correct,
                "acceptable_correct": acceptable_correct,
                "strict_accuracy": round(strict_correct / total, 4),
                "acceptable_accuracy": round(acceptable_correct / total, 4),
                "avg_confidence": avg_conf,
                "false_confidence_rate": self._false_confidence_rate(),
                "high_confidence_threshold": HIGH_CONFIDENCE_THRESHOLD,
            },
            "precision_recall_per_category": self._precision_recall(),
            "stratified_results": self._stratified_results(),
            "raw_results": self.results,
        }

    # ── Report printer ────────────────────────────────────────────────────────

    @staticmethod
    def print_report(sc: dict[str, Any]) -> None:
        s = sc["summary"]
        total = s["total_cases"]
        W = 66

        print("\n" + "=" * W)
        print("ADVERSARIAL EVALUATION SCORECARD")
        print("=" * W)
        print(f"  Total cases            : {total}")
        print(f"  Strict accuracy        : {s['strict_accuracy']:.0%}  ({s['strict_correct']}/{total})")
        print(f"  Acceptable accuracy    : {s['acceptable_accuracy']:.0%}  ({s['acceptable_correct']}/{total})")
        print(f"  Avg confidence         : {s['avg_confidence']:.1%}")
        print(
            f"  False confidence rate  : {s['false_confidence_rate']:.1%}"
            f"  (conf >= {s['high_confidence_threshold']:.0%} but wrong)"
        )

        print("\n-- Precision / Recall per Category " + "-" * (W - 35))
        hdr = f"  {'Category':<25} {'Precision':>10} {'Recall':>8} {'TP':>4} {'FP':>4} {'FN':>4}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for cat, m in sc["precision_recall_per_category"].items():
            print(
                f"  {cat:<25} {m['precision']:>10.0%} {m['recall']:>8.0%}"
                f" {m['tp']:>4} {m['fp']:>4} {m['fn']:>4}"
            )

        print("\n-- Stratified Results " + "-" * (W - 21))
        print(
            f"  {'Type':<20} {'Strict':>8} {'Accept':>8}"
            f" {'AvgConf':>8} {'FalseConf':>10}"
        )
        print("  " + "-" * 56)
        for t, m in sc["stratified_results"].items():
            print(
                f"  {t:<20} {m['strict_accuracy']:>8.0%} {m['acceptable_accuracy']:>8.0%}"
                f" {m['avg_confidence']:>8.1%} {m['false_confidence_count']:>10}"
            )

        print("\n-- Per-Case Detail " + "-" * (W - 18))
        print(
            f"  {'#':>3} {'Type':<18} {'Expected':<20} {'Predicted':<20} {'Conf':>5} {'OK':>3}"
        )
        print("  " + "-" * 72)
        for r in sc["raw_results"]:
            badge = "OK" if r["correct"] else (" ~" if r["acceptable_correct"] else "XX")
            pred = r["predicted_category"] or "ERROR"
            conf_str = f"{r['confidence']:.0%}" if r["confidence"] is not None else "  N/A"
            print(
                f"  {r['id']:>3} {r['type']:<18} {r['expected_category']:<20}"
                f" {pred:<20} {conf_str:>5} {badge:>4}"
            )
            if r.get("error"):
                print(f"      -> error: {r['error']}")

        print("=" * W)
        print("\nLegend: OK=strictly correct  ~=acceptable alternative  XX=wrong")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with CASES_FILE.open(encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    print(f"Loaded {len(cases)} adversarial cases from {CASES_FILE}")
    type_counts: dict[str, int] = defaultdict(int)
    for c in cases:
        type_counts[c["type"]] += 1
    for t, n in sorted(type_counts.items()):
        print(f"  {t:<22} {n} case{'s' if n != 1 else ''}")

    if dry_run:
        print("\n[dry-run] Skipping API calls. Case file is valid.")
        return

    sc_obj = Scorecard(cases)
    sc_obj.run()

    scorecard = sc_obj.build_scorecard()

    with SCORECARD_FILE.open("w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2, ensure_ascii=False)
    print(f"\nScorecard saved -> {SCORECARD_FILE}")

    sc_obj.print_report(scorecard)


if __name__ == "__main__":
    main()
