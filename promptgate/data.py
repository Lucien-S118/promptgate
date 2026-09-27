"""Read original downloads; audit leakage; write separate, reproducible local splits."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import random

SEED = 6201


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def text_hash(text: str) -> str:
    return sha256(normalized(text).encode()).hexdigest()


def _row(text, label, source, index):
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Empty/non-text row at {source}:{index}")
    if type(label) is not int or label not in (0, 1):
        raise ValueError(f"Invalid label at {source}:{index}")
    return {"id": f"{source}:{index}", "text": text, "label": label,
            "text_sha256": text_hash(text), "source": source, "source_row": index}


def load_originals(root: Path):
    groups, files = {}, {}
    for split in ("train", "validation", "test"):
        path = root / f"prompt_injection_{split}.csv"
        source = f"slabs_{split}"
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["text", "label"]:
                raise ValueError(f"Unexpected CSV columns: {path.name}")
            groups[source] = [_row(r["text"], int(r["label"]), source, i) for i, r in enumerate(reader)]
        files[path.name] = sha256(path.read_bytes()).hexdigest()
    # Reading the local Parquet files avoids silently treating a 100-row preview as all 662 rows.
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError("Data preparation needs pyarrow. Install the [data] extra first.") from exc
    for split in ("train", "test"):
        path = root / f"deepset_prompt_injection_{split}.parquet"
        source = f"deepset_{split}"
        data = pq.read_table(path).to_pylist()
        groups[source] = [_row(r["text"], r["label"], source, i) for i, r in enumerate(data)]
        files[path.name] = sha256(path.read_bytes()).hexdigest()
    expected = {"slabs_train": 11089, "slabs_validation": 2101, "slabs_test": 2101,
                "deepset_train": 546, "deepset_test": 116}
    actual = {name: len(rows) for name, rows in groups.items()}
    if actual != expected:
        raise ValueError(f"Source sizes changed; review before proceeding: {actual}")
    return groups, files


def audit_and_clean(groups: dict[str, list[dict]]):
    keys = {name: {r["text_sha256"] for r in rows} for name, rows in groups.items()}
    labels = defaultdict(set)
    for rows in groups.values():
        for row in rows:
            labels[row["text_sha256"]].add(row["label"])
    conflicts = {key for key, values in labels.items() if len(values) > 1}
    before = {name: {"rows": len(rows), "label_counts": dict(Counter(r["label"] for r in rows)),
                     "duplicate_rows": len(rows) - len(keys[name])} for name, rows in groups.items()}
    overlap = {f"{a}__{b}": len(keys[a] & keys[b]) for a, b in combinations(groups, 2)}
    # Preserve evaluation examples ahead of training/calibration examples.
    # deepset 'train' is external evaluation only, never a training split in PromptGate.
    priority = ("deepset_test", "deepset_train", "slabs_test", "slabs_validation", "slabs_train")
    seen, clean, removed = set(), {}, {}
    for name in priority:
        clean[name], reasons = [], Counter()
        own_seen = set()
        for row in groups[name]:
            key = row["text_sha256"]
            if key in conflicts:
                reasons["conflicting_labels"] += 1
            elif key in own_seen:
                reasons["within_split_duplicate"] += 1
            elif key in seen:
                reasons["overlap_with_higher_priority_split"] += 1
            else:
                clean[name].append(row)
            own_seen.add(key)
        seen.update(own_seen)
        removed[name] = dict(reasons)
    report = {"normalization": "Unicode casefold + whitespace collapse; no fuzzy/semantic deduplication",
              "before": before, "normalized_overlap_unique_texts": overlap,
              "conflicting_texts": len(conflicts), "priority": list(priority),
              "removed": removed,
              "after": {name: {"rows": len(rows), "label_counts": dict(Counter(r["label"] for r in rows))}
                        for name, rows in clean.items()}}
    return clean, report


def stratified_mvp(rows, n=100, seed=SEED):
    if n <= 0 or n % 2:
        raise ValueError("MVP size must be positive and even.")
    rng, selected = random.Random(seed), []
    for label in (0, 1):
        pool = sorted((r for r in rows if r["label"] == label), key=lambda r: r["id"])
        if len(pool) < n // 2:
            raise ValueError("Insufficient samples for a balanced MVP set.")
        selected.extend(rng.sample(pool, n // 2))
    rng.shuffle(selected)
    return selected


def write_json(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_rows(path: Path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def prepare(source: Path, output: Path):
    if output.exists():
        raise ValueError("Output directory exists. Use a new version; do not overwrite frozen splits.")
    groups, files = load_originals(source)
    clean, audit = audit_and_clean(groups)
    mvp = stratified_mvp(clean["slabs_test"])
    selected = {r["id"] for r in mvp}
    outputs = {
        "train": clean["slabs_train"], "validation": clean["slabs_validation"],
        "mvp_100": mvp,
        "test_remaining": [r for r in clean["slabs_test"] if r["id"] not in selected],
        "external_clean": clean["deepset_train"] + clean["deepset_test"],
        "external_original_662": groups["deepset_train"] + groups["deepset_test"],
    }
    output.mkdir(parents=True)
    hashes = {}
    for name, rows in outputs.items():
        path = output / f"{name}.jsonl"
        write_rows(path, rows)
        hashes[path.name] = sha256(path.read_bytes()).hexdigest()
    audit.update({"seed": SEED, "input_file_sha256": files, "output_file_sha256": hashes,
                  "output_sizes": {name: len(rows) for name, rows in outputs.items()},
                  "mvp_ids": [r["id"] for r in mvp],
                  "historical_exposure": "Public datasets were explored in August. This is a prospective frozen split, not a claim of never-seen data.",
                  "external_use": "deepset train and test are evaluation-only; raw and cleaned views must not be pooled or used to tune thresholds."})
    write_json(output / "manifest.json", audit)
    return audit


def read_rows(path: Path):
    rows, ids = [], set()
    with path.open(encoding="utf-8") as stream:
        for i, line in enumerate(stream, 1):
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in ids:
                raise ValueError(f"Missing or duplicate ID on line {i}.")
            _row(row.get("text"), row.get("label"), "input", i)
            if row.get("text_sha256") != text_hash(row["text"]):
                raise ValueError(f"Text hash mismatch on line {i}.")
            ids.add(row["id"])
            rows.append(row)
    if not rows:
        raise ValueError("Dataset is empty.")
    return rows
