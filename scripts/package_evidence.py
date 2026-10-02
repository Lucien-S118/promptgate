"""Copy original local evidence into the portable, text-safe submission layout.

This is a packaging operation, not a new experiment. It excludes deepset text,
credentials and free-form model explanations, and refuses different existing bytes.
"""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def put(source, destination):
    payload = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise ValueError(f"Refusing to overwrite differing evidence: {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def save_json(path, data):
    payload = (json.dumps(data, indent=2, sort_keys=True) + '\n').encode()
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(f"Refusing to replace manifest: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    args = p.parse_args()
    prep = ROOT / 'data/processed/v1/manifest.json'
    audit = json.loads(prep.read_text())
    sources = {}
    for split in ('train', 'validation', 'test'):
        name = f'prompt_injection_{split}.csv'
        src = args.source / name
        if sha256(src.read_bytes()).hexdigest() != audit['input_file_sha256'][name]:
            raise ValueError(f'Source bytes differ: {name}')
        put(src, ROOT / 'data_sources/slabs' / name)
        sources[name] = {
            'url': f'https://huggingface.co/datasets/S-Labs/prompt-injection-dataset/resolve/002a9dd18514abd021869823d6b0429b38606d99/data/{split}.csv',
            'sha256': audit['input_file_sha256'][name],
            'rows': {'train': 11089, 'validation': 2101, 'test': 2101}[split],
            'included': True,
        }
    for split, suffix, count in [('train', '9564e8b05b4757ab', 546), ('test', '701d16158af87368', 116)]:
        name = f'deepset_prompt_injection_{split}.parquet'
        sources[name] = {
            'url': f'https://huggingface.co/datasets/deepset/prompt-injections/resolve/4f61ecb038e9c3fb77e21034b22511b523772cdd/data/{split}-00000-of-00001-{suffix}.parquet',
            'sha256': audit['input_file_sha256'][name], 'rows': count,
            'included': False, 'reason': 'eval-only; no redistribution of prompt text',
        }
    save_json(ROOT / 'data_sources/source_manifest.json', sources)
    put(prep, ROOT / 'data_sources/preparation_manifest.json')
    for name in ('train', 'validation', 'mvp_100', 'test_remaining'):
        put(ROOT / f'data/processed/v1/{name}.jsonl', ROOT / f'data_sources/processed/{name}.jsonl')
    for source, destination, extra in [
        ('teacher-11089-external-20260925-01', 'offline', 'protocol.json'),
        ('llm-mvp-20260922-01', 'live', 'run.json'),
    ]:
        run = ROOT / 'results/runs' / source
        for path in sorted(run.glob('*.jsonl')):
            for line in path.read_text().splitlines():
                record = json.loads(line)
                forbidden = {'text', 'prompt', 'reason', 'api_key', 'authorization'} & set(record)
                if forbidden:
                    raise ValueError(f'Unexpected sensitive fields in {path.name}: {forbidden}')
            put(path, ROOT / 'evidence' / destination / path.name)
        for name in ('summary.json', extra):
            put(run / name, ROOT / 'evidence' / destination / name)
    paths = []
    for folder in ('data_sources', 'evidence/offline', 'evidence/live', 'models/teacher-11089'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix != '.md')
    paths.extend(ROOT / 'evidence' / name for name in ('teacher-11089-summary.json', 'llm-mvp-summary.json'))
    checksums = {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    save_json(ROOT / 'evidence/artifact_sha256.json', checksums)
    print(f'Packaged {len(checksums)} payload files. No new inference or external raw text.')


if __name__ == '__main__':
    main()
