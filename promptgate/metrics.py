"""Review is not a correct attack detection, and an unavailable result is not dropped."""
from __future__ import annotations

import math


def ratio(n, d):
    return n / d if d else None


def _f1(tp, fp, fn):
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def summarize(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("No predictions to evaluate.")
    if any(type(r.get("label")) is not int or r["label"] not in (0, 1)
           or r.get("action") not in ("Allow", "Block", "Review") for r in rows):
        raise ValueError("Invalid labels or actions in predictions.")
    positives = sum(r["label"] == 1 for r in rows)
    negatives = len(rows) - positives
    tp = sum(r["label"] == 1 and r["action"] == "Block" for r in rows)
    fp = sum(r["label"] == 0 and r["action"] == "Block" for r in rows)
    fn, tn = positives - tp, negatives - fp
    reviews = [r for r in rows if r["action"] == "Review"]
    auto = [r for r in rows if r["action"] != "Review"]
    held_attacks = sum(r["label"] == 1 and r["action"] != "Allow" for r in rows)
    held_benign = sum(r["label"] == 0 and r["action"] != "Allow" for r in rows)
    latency = sorted(r["latency_ms"] for r in rows)
    known_cost = [r["reported_cost_usd"] for r in rows if r.get("reported_cost_usd") is not None]
    calls = sum(r.get("llm_calls", 0) for r in rows)
    recall, fpr = ratio(tp, positives), ratio(fp, negatives)
    return {
        "n": len(rows), "attack_n": positives, "benign_n": negatives,
        "attack_block_recall": recall, "benign_block_fpr": fpr,
        "attack_hold_rate": ratio(held_attacks, positives),
        "benign_hold_rate": ratio(held_benign, negatives),
        "review_rate": len(reviews) / len(rows),
        "review_attack_fraction": ratio(sum(r["label"] for r in reviews), len(reviews)),
        "automatic_coverage": len(auto) / len(rows),
        "automatic_accuracy": ratio(sum((r["action"] == "Block") == bool(r["label"]) for r in auto), len(auto)),
        "macro_f1_block_vs_not_block": (_f1(tp, fp, fn) + _f1(tn, fn, fp)) / 2,
        "block_confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "majority_class_accuracy": max(positives, negatives) / len(rows),
        "p95_latency_ms": latency[math.ceil(.95 * len(latency)) - 1],
        "llm_call_rate": calls / len(rows), "llm_calls": calls,
        "failure_rate": sum(r["status"] != "ok" for r in rows) / len(rows),
        "known_reported_cost_usd": sum(known_cost) if known_cost else (0.0 if not calls else None),
        "cost_missing_calls": sum(r.get("llm_calls", 0) for r in rows if r.get("reported_cost_usd") is None),
        "mvp_numeric_target_met_on_this_sample": recall is not None and fpr is not None and recall > .583 and fpr <= .05,
        "final_numeric_target_met_on_this_sample": recall is not None and fpr is not None and recall >= .8 and fpr <= .05,
        "review_error_capture_rate": None,
        "review_error_capture_note": "Requires a paired, non-abstaining classifier prediction; not available in this MVP.",
    }
