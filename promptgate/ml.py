"""Train-only vocabulary; disjoint probability calibration and policy selection.

External outcomes are not used for fitting or selection. Data preparation separately
inspects source labels for integrity checks; benchmark() scores frozen candidates.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
from pathlib import Path
import time

import joblib
import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline

from .baselines import COMPILED, regex_screen
from .contracts import Screening, validate_prompt
from .data import read_rows, write_json, write_rows
from .metrics import summarize

SEED = 6201


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def block_threshold(labels, scores, fpr_cap=.05):
    labels, scores = np.asarray(labels), np.asarray(scores)
    if set(labels.tolist()) != {0, 1} or not np.isfinite(scores).all():
        raise ValueError("Threshold fitting needs both classes and finite scores.")
    fpr, recall, thresholds = roc_curve(labels, scores, drop_intermediate=False)
    eligible = np.flatnonzero(fpr <= fpr_cap)
    # Maximize recall, then minimize FPR, then prefer the higher threshold.
    i = max(eligible, key=lambda j: (recall[j], -fpr[j], thresholds[j]))
    return float(thresholds[i]) if np.isfinite(thresholds[i]) else float(np.nextafter(1., 2.))


def route(score, threshold, margin=0.0, rule_hit=False, hybrid=True):
    if not np.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Invalid classifier score.")
    if not np.isfinite(threshold) or not 0 <= margin <= 1:
        raise ValueError("Invalid decision policy.")
    if not hybrid:
        return "Block" if score >= threshold else "Allow"
    if score >= threshold + margin:
        return "Block"
    if score >= max(0., threshold - margin) or rule_hit:
        return "Review"
    return "Allow"


def select_margin(labels, scores, hits, threshold, max_review=.19):
    base = np.asarray(scores) >= threshold
    errors = base != np.asarray(labels)
    candidates = []
    # Predeclared grid; policy labels only. No external tuning.
    for margin in np.linspace(0., .30, 61):
        actions = [route(p, threshold, float(margin), h) for p, h in zip(scores, hits)]
        reviews = np.array([a == "Review" for a in actions])
        rate = float(np.mean(reviews))
        if rate <= max_review:
            captured = int(np.sum(errors & reviews))
            candidates.append((captured, -rate, -float(margin), float(margin)))
    if not candidates:
        raise ValueError("Rule disagreements already exceed the validation Review budget.")
    return max(candidates)[3]


def calibration_report(labels, scores):
    fraction, mean = calibration_curve(labels, scores, n_bins=10, strategy="uniform")
    return {"brier_score": float(brier_score_loss(labels, scores)),
            "bin_mean_score": mean.tolist(), "bin_attack_fraction": fraction.tolist()}


def review_quality(labels, scores, threshold, actions):
    errors = (np.asarray(scores) >= threshold) != np.asarray(labels)
    reviews = np.asarray(actions) == "Review"
    return {"counterfactual_binary_errors": int(np.sum(errors)),
            "binary_errors_captured_by_review": int(np.sum(errors & reviews)),
            "review_error_capture_rate": float(np.sum(errors & reviews) / np.sum(errors)) if np.any(errors) else None,
            "review_error_precision": float(np.sum(errors & reviews) / np.sum(reviews)) if np.any(reviews) else None,
            "review_error_capture_note": "Compared against this same calibrated classifier at the frozen binary threshold, before abstention."}


def fit_models(data: Path, output: Path, raw_train_path: Path | None = None):
    if output.exists():
        raise ValueError("Model directory already exists; choose a new version.")
    train, validation = read_rows(data / "train.jsonl"), read_rows(data / "validation.jsonl")
    if raw_train_path is not None:
        with raw_train_path.open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['text', 'label']:
                raise ValueError('Unexpected raw training columns.')
            raw_rows = list(reader)
        if len(raw_rows) != 11089 or any(r['label'] not in ('0', '1') or not r['text'].strip() for r in raw_rows):
            raise ValueError('The requested original 11,089-row S-Labs training set is unavailable or invalid.')
        train = [{'id': f'original_train:{i}', 'text': r['text'], 'label': int(r['label']),
                  'text_sha256': sha256(' '.join(r['text'].casefold().split()).encode()).hexdigest()}
                 for i,r in enumerate(raw_rows)]
    overlap = {r['text_sha256'] for r in train} & {r['text_sha256'] for r in validation}
    if raw_train_path is not None:
        validation = [r for r in validation if r['text_sha256'] not in overlap]
    elif overlap:
        raise ValueError("Training/calibration leakage detected.")
    cal_idx, policy_idx = train_test_split(np.arange(len(validation)), test_size=.5, random_state=SEED,
                                          stratify=[r['label'] for r in validation])
    cal = [validation[i] for i in cal_idx]
    policy = [validation[i] for i in policy_idx]
    x_train, y_train = [r['text'] for r in train], [r['label'] for r in train]
    x_cal, y_cal = [r['text'] for r in cal], [r['label'] for r in cal]
    x_policy, y_policy = [r['text'] for r in policy], [r['label'] for r in policy]
    hits = [any(rule.search(t) for rule in COMPILED) for t in x_policy]
    candidates = {
        "naive_bayes": Pipeline([
            ('features', TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, min_df=2, max_features=50000)),
            ('classifier', MultinomialNB(alpha=1.))]),
        "logistic_word_char": Pipeline([
            ('features', FeatureUnion([
                ('word', TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, min_df=2, max_features=50000)),
                ('char', TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5), sublinear_tf=True, min_df=2, max_features=50000))])),
            ('classifier', LogisticRegression(C=4., max_iter=1500, solver='liblinear', random_state=SEED))]),
    }
    output.mkdir(parents=True)
    plan = {"seed": SEED, "train_n": len(train), "probability_calibration_n": len(cal),
            "policy_selection_n": len(policy), "probability_calibration_ids": [r['id'] for r in cal],
            "policy_selection_ids": [r['id'] for r in policy], "sklearn_version": sklearn.__version__,
            "train_sha256": digest(raw_train_path or data/'train.jsonl'),
            "train_source": 'original_S_Labs_11089_rows' if raw_train_path else 'deduplicated_S_Labs_11045_rows',
            "raw_training_overlap_removed_from_validation": len(overlap) if raw_train_path else 0,
            "validation_sha256": digest(data/'validation.jsonl'),
            "source_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
            "fpr_cap_on_policy_split": .05, "review_cap_on_policy_split": .19,
            "model_selection": "Highest policy-split binary recall at <=5% FPR; tie: lower FPR, then name.",
            "external_use": "Not used in fitting, calibration, policy selection, or model selection.",
            "candidates": list(candidates), "created_at_utc": datetime.now(timezone.utc).isoformat()}
    write_json(output/'training_protocol.json', plan)
    summaries = {}
    for name, estimator in candidates.items():
        print('Fitting', name, flush=True)
        start = time.perf_counter()
        estimator.fit(x_train, y_train)
        model = CalibratedClassifierCV(FrozenEstimator(estimator), method='sigmoid')
        model.fit(x_cal, y_cal)
        probabilities = model.predict_proba(x_policy)[:, 1]
        threshold = block_threshold(y_policy, probabilities)
        margin = select_margin(y_policy, probabilities, hits, threshold)
        rows = [{"label": y, "action": route(p, threshold, hybrid=False), "status": "ok", "latency_ms": 0., "llm_calls": 0}
                for y,p in zip(y_policy, probabilities)]
        summary = summarize(rows)
        summary.pop('p95_latency_ms')
        summary.update(calibration=calibration_report(y_policy, probabilities),
                       uncalibrated_brier_score=float(brier_score_loss(y_policy, estimator.predict_proba(x_policy)[:,1])),
                       training_seconds=time.perf_counter()-start)
        meta = {"name": name, "block_threshold": threshold, "review_margin": margin,
                "policy_version": "hybrid-v1", "score_kind": "sigmoid_calibrated_on_source_domain",
                "policy_split_metrics": summary}
        model_path = output/f'{name}.joblib'
        joblib.dump(model, model_path, compress=3)
        meta['model_sha256'] = digest(model_path)
        write_json(output/f'{name}.json', meta)
        summaries[name] = meta
        print(name, 'policy recall', round(summary['attack_block_recall'],4),
              'FPR',round(summary['benign_block_fpr'],4),'margin',margin,flush=True)
    selected = max(summaries, key=lambda n: (summaries[n]['policy_split_metrics']['attack_block_recall'],
                                           -summaries[n]['policy_split_metrics']['benign_block_fpr'], n))
    write_json(output/'selection.json', {"selected": selected, "basis": plan['model_selection'],
                                       "external_labels_seen_for_selection": False})
    return {"selected": selected, "candidates": summaries}


class Detector:
    def __init__(self, directory: Path, name=None):
        name = name or json.loads((directory/'selection.json').read_text())['selected']
        if name not in ('naive_bayes','logistic_word_char'):
            raise ValueError('Unknown model name')
        self.meta = json.loads((directory/f'{name}.json').read_text())
        path = directory/f'{name}.joblib'
        if digest(path) != self.meta['model_sha256']:
            raise ValueError('Model checksum mismatch')
        # Only load locally generated, trusted artifacts. A checksum is not a signature.
        self.model = joblib.load(path)

    def screen(self, prompt, hybrid=True):
        validate_prompt(prompt)
        start = time.perf_counter()
        score = float(self.model.predict_proba([prompt])[0,1])
        hit = any(rule.search(prompt) for rule in COMPILED)
        action = route(score, self.meta['block_threshold'], self.meta['review_margin'], hit, hybrid)
        reason = {'Allow':'Score is below the frozen review boundary; no conflicting rule matched.',
                  'Block':'Score meets the frozen blocking boundary.',
                  'Review':'Score is near the decision boundary or a rule disagrees; human review is required.'}[action]
        return Screening(action,score,reason,backend='hybrid' if hybrid else 'classifier',
                         model=self.meta['name'], latency_ms=(time.perf_counter()-start)*1000,
                         policy_version=self.meta['policy_version'])


def benchmark(data: Path, models: Path, output: Path):
    if output.exists():
        raise ValueError('Benchmark directory exists; do not silently re-test.')
    output.mkdir(parents=True)
    write_json(output/'protocol.json', {"selection_sha256":digest(models/'selection.json'),
               "source_sha256":{p.name:digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
               "note":"All configurations frozen before reading test labels. Offline evidence; no LLM calls.",
               "created_at_utc":datetime.now(timezone.utc).isoformat()})
    detectors = {n:Detector(models,n) for n in ('naive_bayes','logistic_word_char')}
    reports = {}
    for split in ('test_remaining','external_clean'):
        samples = read_rows(data/f'{split}.jsonl')
        reports[split] = {}
        for name in ('regex','naive_bayes','logistic_word_char','hybrid'):
            detector = detectors.get(name) if name != 'hybrid' else Detector(models)
            records = []
            for row in samples:
                result = regex_screen(row['text']) if name == 'regex' else detector.screen(row['text'], hybrid=name=='hybrid')
                item = asdict(result)
                item.pop('reason')
                item.update(id=row['id'],label=row['label'],text_sha256=row['text_sha256'])
                records.append(item)
            summary = summarize(records)
            if detector is not None:
                probabilities = [r['risk_score'] for r in records]
                labels = [r['label'] for r in records]
                summary.update(calibration=calibration_report(labels,probabilities),
                               **review_quality(labels,probabilities,detector.meta['block_threshold'],[r['action'] for r in records]))
            summary.update(dataset_sha256=digest(data/f'{split}.jsonl'), evidence='offline_trained_model' if detector else 'deterministic_rules')
            write_rows(output/f'{split}--{name}.jsonl',records)
            reports[split][name]=summary
            print(split,name,'recall',round(summary['attack_block_recall'],4),'FPR',round(summary['benign_block_fpr'],4),
                  'Review',round(summary['review_rate'],4),flush=True)
    write_json(output/'summary.json',reports)
    return reports


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('operation',choices=['train','benchmark'])
    p.add_argument('--data',type=Path,default=Path('data/processed/v1'))
    p.add_argument('--models',type=Path,default=Path('models/v1'))
    p.add_argument('--output',type=Path)
    p.add_argument('--raw-train',type=Path,default=None,
                   help='Use the original 11,089-row S-Labs train CSV as the teacher requested')
    a=p.parse_args()
    if a.operation=='train':
        fit_models(a.data,a.models,a.raw_train)
    elif a.output is None:
        p.error('--output is required for benchmark')
    else:
        benchmark(a.data,a.models,a.output)


if __name__=='__main__':
    main()
