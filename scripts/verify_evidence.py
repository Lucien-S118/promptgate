"""Audit packaged evidence offline; exit nonzero on inconsistent data or metrics.

Recorded provider predictions are recomputed, not replayed over the network.
The only new inference is a local frozen-model smoke check on included S-Labs data.
"""
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from promptgate.data import read_rows
from promptgate.metrics import summarize
from promptgate.ml import Detector, route


def require(condition, message):
    if not condition:
        raise ValueError(message)


def match(actual, expected, path='value'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict), f'{path}: expected object')
        for key, value in expected.items():
            require(key in actual, f'{path}: missing {key}')
            match(actual[key], value, f'{path}.{key}')
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-9), f'{path}: numeric mismatch')
    else:
        require(actual == expected, f'{path}: mismatch')


def load(path):
    return json.loads((ROOT / path).read_text())


def records(path):
    rows = [json.loads(line) for line in (ROOT / path).read_text().splitlines()]
    require(len({r['id'] for r in rows}) == len(rows), f'{path}: duplicate IDs')
    for row in rows:
        require(not ({'text', 'prompt', 'reason', 'api_key', 'authorization'} & row.keys()), f'{path}: sensitive field')
    return rows


def main():
    checksums = load('evidence/artifact_sha256.json')
    for name, expected in checksums.items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT), 'Invalid manifest path')
        require(sha256(path.read_bytes()).hexdigest() == expected, f'Checksum mismatch: {name}')
    sources = load('data_sources/source_manifest.json')
    for name, meta in sources.items():
        if meta['included']:
            with (ROOT / 'data_sources/slabs' / name).open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            require(len(rows) == meta['rows'], f'Row count: {name}')
            require(all(r['label'] in ('0', '1') and r['text'].strip() for r in rows), f'Labels/text: {name}')
    prepared = {n: read_rows(ROOT / f'data_sources/processed/{n}.jsonl')
                for n in ('train', 'validation', 'mvp_100', 'test_remaining')}
    prep = load('data_sources/preparation_manifest.json')
    for n, rows in prepared.items():
        require(len(rows) == prep['output_sizes'][n], f'Prepared size: {n}')
    require(not ({r['text_sha256'] for r in prepared['mvp_100']} & {r['text_sha256'] for r in prepared['test_remaining']}), 'MVP/test overlap')
    offline = load('evidence/offline/summary.json')
    record_sets = {}
    for split, models in offline.items():
        for model, expected in models.items():
            rows = records(f'evidence/offline/{split}--{model}.jsonl')
            record_sets[split, model] = rows
            metrics = summarize(rows)
            # Paired capture is added by the benchmark, not by summarize().
            for key in ('review_error_capture_rate', 'review_error_capture_note'):
                metrics.pop(key)
            match(expected, metrics, f'{split}.{model}')
            if split == 'test_remaining':
                match({r['id']: [r['label'], r['text_sha256']] for r in rows},
                      {r['id']: [r['label'], r['text_sha256']] for r in prepared[split]}, f'{split}.membership')
        binary = {r['id']: r for r in record_sets[split, 'naive_bayes']}
        hybrid = record_sets[split, 'hybrid']
        require(set(binary) == {r['id'] for r in hybrid}, f'{split}: paired IDs mismatch')
        errors = captured = 0
        for row in hybrid:
            base = binary[row['id']]
            require((row['label'], row['text_sha256']) == (base['label'], base['text_sha256']), 'Paired label/hash mismatch')
            error = (base['action'] == 'Block') != bool(base['label'])
            errors += error
            captured += error and row['action'] == 'Review'
        match(offline[split]['hybrid'], {'counterfactual_binary_errors': errors,
              'binary_errors_captured_by_review': captured,
              'review_error_capture_rate': captured / errors}, f'{split}.capture')
    live = records('evidence/live/predictions.jsonl')
    live_summary = load('evidence/live/summary.json')
    match(live_summary, summarize(live), 'live')
    match({r['id']: [r['label'], r['text_sha256']] for r in live},
          {r['id']: [r['label'], r['text_sha256']] for r in prepared['mvp_100']}, 'live.membership')
    short = load('evidence/teacher-11089-summary.json')
    for key, split in [('external_original_662', 'external_clean'), ('slabs_remaining_test', 'test_remaining')]:
        expected = dict(short[key])
        if 'confusion' in expected:
            expected['block_confusion'] = expected.pop('confusion')
        match(offline[split]['naive_bayes'], expected, f'headline.{key}')
    comparison = short['comparison']
    for name, value in comparison.items():
        model, key = name.split('_external_', 1)
        full = offline['external_clean']['hybrid' if model == 'hybrid' else 'logistic_word_char']
        if key == 'review_n':
            actual = sum(r['action'] == 'Review' for r in record_sets['external_clean', 'hybrid'])
        else:
            actual = full['block_confusion' if key == 'confusion' else key]
        match(actual, value, f'headline.{name}')
    live_short = load('evidence/llm-mvp-summary.json')
    match(live_summary, {k:v for k,v in live_short.items() if k not in ('run','backend')}, 'live.headline')
    model = Detector(ROOT / 'models/teacher-11089')
    match(model.meta['policy_split_metrics'], {
        'n': short['development_policy']['n'],
        'attack_block_recall': short['development_policy']['attack_block_recall'],
        'benign_block_fpr': short['development_policy']['benign_block_fpr'],
        'block_confusion': short['development_policy']['confusion'],
    }, 'policy.headline')
    from promptgate.baselines import COMPILED
    for row in prepared['mvp_100']:
        result = model.screen(row['text'])
        require(result.action == route(result.risk_score, model.meta['block_threshold'],
                model.meta['review_margin'], any(rule.search(row['text']) for rule in COMPILED)), 'Local routing mismatch')
        require(result.llm_calls == 0, 'Unexpected external call')
    recorded = {r['id']: r for r in record_sets['test_remaining', 'hybrid']}
    for row in prepared['test_remaining']:
        result = model.screen(row['text'])
        require(result.action == recorded[row['id']]['action'], 'Frozen held-out decision changed')
        match(result.risk_score, recorded[row['id']]['risk_score'], 'Frozen held-out score')
    print(f'PASS: {len(checksums)} artifact hashes, source counts, split membership, 8 offline prediction files, 100 live records, headline metrics and paired Review capture.')
    print('PASS: local classifier runs on the 100 MVP inputs and reproduces all 2,001 held-out hybrid decisions. No new provider calls.')


if __name__ == '__main__':
    main()
