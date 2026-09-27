"""Validate untrusted model output before a caller may act on it."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Optional

ACTIONS = ("Allow", "Block", "Review")
MAX_PROMPT_CHARS = 8000
POLICY_VERSION = "mvp-v1-uncalibrated"
ALLOW_MAX = 0.2
BLOCK_MIN = 0.8


class ContractError(ValueError):
    """Invalid input or response. Messages must never contain submitted text."""


def validate_prompt(prompt: str) -> None:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ContractError("Prompt must contain text.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ContractError(f"Prompt exceeds {MAX_PROMPT_CHARS} characters; do not truncate it.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("Duplicate JSON key.")
        result[key] = value
    return result


def strict_json(text: str):
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, TypeError, RecursionError) as exc:
        raise ContractError("Invalid JSON.") from exc


@dataclass(frozen=True)
class Screening:
    action: str
    risk_score: Optional[float]
    reason: str
    status: str = "ok"
    model_action: Optional[str] = None
    backend: str = "llm"
    model: Optional[str] = None
    provider: Optional[str] = None
    latency_ms: float = 0.0
    llm_calls: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reported_cost_usd: Optional[float] = None
    policy_version: str = POLICY_VERSION

    @property
    def may_forward(self) -> bool:
        return self.status == "ok" and self.action == "Allow"

    def public_dict(self) -> dict:
        return {**asdict(self), "may_forward": self.may_forward,
                "score_kind": {"llm": "uncalibrated_model_rating", "regex": "rule_match"}.get(
                    self.backend, "sigmoid_calibrated_on_source_domain")}


def parse_decision(content: str) -> dict:
    value = strict_json(content)
    if not isinstance(value, dict) or set(value) != {"action", "risk_score", "reason"}:
        raise ContractError("Response fields do not match schema.")
    action, score, reason = value["action"], value["risk_score"], value["reason"]
    if action not in ACTIONS:
        raise ContractError("Unknown action.")
    if type(score) not in (float, int) or not 0 <= score <= 1 or not math.isfinite(score):
        raise ContractError("Risk score must be a finite number between 0 and 1.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 600:
        raise ContractError("Reason must contain 1 to 600 characters.")
    # A model cannot waive the code's policy by saying Allow with a high score.
    conflict = (action == "Allow" and score > ALLOW_MAX) or (action == "Block" and score < BLOCK_MIN)
    return {"action": "Review" if conflict else action, "risk_score": float(score),
            "reason": "Model action and score conflict; human review required." if conflict else reason.strip(),
            "model_action": action, "status": "policy_conflict" if conflict else "ok"}
