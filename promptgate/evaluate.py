"""Write metadata-only evidence; preserve incomplete runs without inventing predictions."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from . import __version__
from .baselines import regex_screen
from .contracts import validate_prompt
from .data import read_rows, write_json
from .llm import MAX_OUTPUT_TOKENS, MODEL, PROMPT_VERSION, screen
from .metrics import summarize


def evaluate(dataset: Path, output: Path, backend: str, api_key="", max_calls=100):
    if backend not in ("llm", "regex"):
        raise ValueError("Unknown backend.")
    if output.exists():
        raise ValueError("Run directory already exists; use a new run name.")
    rows = read_rows(dataset)
    for row in rows:
        validate_prompt(row["text"])
    if backend == "llm" and (not api_key.strip() or len(rows) > max_calls):
        raise ValueError("LLM evaluation needs a key and a call limit at least as large as the dataset.")
    # Finish all local validation before spending on the first API call.
    output.mkdir(parents=True)
    source_hashes = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    manifest = {"package_version": __version__, "source_sha256": source_hashes,
                "backend": backend, "model": MODEL if backend == "llm" else None,
                "prompt_version": PROMPT_VERSION if backend == "llm" else None,
                "max_output_tokens": MAX_OUTPUT_TOKENS if backend == "llm" else None,
                "dataset_file": dataset.name, "dataset_sha256": sha256(dataset.read_bytes()).hexdigest(),
                "planned_n": len(rows), "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "protocol": "Frozen rules/prompt; no tuning on this run. Review is separate from Block.",
                "completion_evidence": "A summary.json file exists only after all planned rows finish."}
    write_json(output / "run.json", manifest)
    predictions = []
    with (output / "predictions.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            result = screen(row["text"], api_key) if backend == "llm" else regex_screen(row["text"])
            record = asdict(result)
            # Prompts and free-text explanations can contain input content; never persist them.
            record.pop("reason")
            record.update(id=row["id"], label=row["label"], text_sha256=row["text_sha256"])
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            stream.flush()
            predictions.append(record)
            if backend == "llm":
                print(f"{len(predictions)}/{len(rows)} {result.status}", flush=True)
            # Stop on credential/balance/configuration failures, retaining an explicitly incomplete run.
            if result.status in {"http_400", "http_401", "http_402", "http_403", "http_404"}:
                raise ValueError(f"Provider returned {result.status}; incomplete evidence retained. No further calls made.")
    summary = summarize(predictions)
    summary.update(backend=backend, evidence="live_api" if backend == "llm" else "deterministic_rules",
                   completed_at_utc=datetime.now(timezone.utc).isoformat(),
                   mvp_acceptance_passed=backend == "llm" and len(rows) == 100
                   and summary["failure_rate"] == 0 and summary["mvp_numeric_target_met_on_this_sample"],
                   comparison_note="The proposal's 58.3% is a historical, not yet reproducible reference. Different datasets/splits are not like-for-like comparisons.")
    write_json(output / "summary.json", summary)
    return summary
