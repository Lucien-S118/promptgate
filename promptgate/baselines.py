"""A frozen non-AI comparator. Never describe these outputs as LLM predictions."""
import re
import time

from .contracts import Screening, validate_prompt

PATTERNS = (
    r"\b(ignore|disregard|forget)\b.{0,70}\b(previous|prior|above|system)\b.{0,40}\b(instructions?|rules?|prompts?)\b",
    r"\b(reveal|show|print|repeat|disclose)\b.{0,70}\b(system prompt|hidden instructions|internal instructions)\b",
    r"\b(override|bypass|disable)\b.{0,40}\b(safety|guardrails?|restrictions?|filters?)\b",
)
COMPILED = tuple(re.compile(p, re.IGNORECASE | re.DOTALL) for p in PATTERNS)


def regex_screen(prompt: str) -> Screening:
    validate_prompt(prompt)
    start = time.perf_counter()
    match = any(pattern.search(prompt) for pattern in COMPILED)
    return Screening(action="Block" if match else "Allow", risk_score=float(match),
                     reason="An injection-related rule matched." if match else "No configured rule matched.",
                     backend="regex", latency_ms=(time.perf_counter() - start) * 1000,
                     policy_version="regex-v1")
