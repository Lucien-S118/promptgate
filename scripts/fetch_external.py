"""Explicit, checksum-verified external-data fetch for local evaluation only.

No credentials, uploads or inference. Raw outputs remain under Git-ignored data/.
"""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def verified_write(path, payload, expected):
    if sha256(payload).hexdigest() != expected:
        raise ValueError(f'Frozen checksum mismatch for {path.name}; refusing changed source.')
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f'Refusing to overwrite {path.name}.')
        return
    with path.open('xb') as stream:
        stream.write(payload)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument('--accept-source-terms', action='store_true',
                   help='Confirm you reviewed upstream terms for local evaluation; does not grant redistribution rights.')
    args = p.parse_args()
    if not args.accept_source_terms:
        p.error('Review data_sources/README.md and the upstream terms before opting in.')
    manifest = json.loads((ROOT / 'data_sources/source_manifest.json').read_text())
    destination = ROOT / 'data/raw'
    destination.mkdir(parents=True, exist_ok=True)
    for name, item in manifest.items():
        path = destination / name
        if path.exists():
            verified_write(path, path.read_bytes(), item['sha256'])
        elif item['included']:
            verified_write(path, (ROOT / 'data_sources/slabs' / name).read_bytes(), item['sha256'])
        else:
            with urlopen(item['url'], timeout=60) as response:
                payload = response.read(5_000_001)
            if len(payload) > 5_000_000:
                raise ValueError('Unexpected download size; source must be reviewed.')
            verified_write(path, payload, item['sha256'])
        print(f'Verified {name} ({item["rows"]} rows expected).')
    print('Ready for local prepare/train/benchmark. Do not commit data/raw/.')


if __name__ == '__main__':
    main()
