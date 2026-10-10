#!/usr/bin/env python3
"""Optional real Glossia CLI comparison using non-payable invoice fixtures.

Glossia describes itself as a readable encoding, not steganography. This measures
round-trip robustness, not concealment. Supply a locally reviewed executable and
its expected SHA-256; this script downloads and installs nothing.
"""
import argparse
import hashlib
import json
import random
import re
import subprocess
from pathlib import Path

from stego_invoice_channels import invoice


def execute(binary, args, data):
    return subprocess.run([str(binary), *args], input=data, capture_output=True, timeout=30)


def run(binary, expected_hash, output):
    binary = Path(binary).resolve()
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    if actual != expected_hash:
        raise ValueError('Codec executable hash mismatch')
    rows = []
    for seed in range(3300, 3304):
        payload = invoice(seed)
        for dialect in ['body', 'subject', 'haiku']:
            encoded = execute(binary, ['--from-ascii', '-', '--dialect', dialect, '--seed', str(seed)], payload)
            if encoded.returncode:
                raise RuntimeError(encoded.stderr.decode(errors='replace')[:300])
            prose = encoded.stdout.decode('utf-8')
            words = prose.split()
            random.Random(seed).shuffle(words)
            versions = {'raw': prose, 'collapsed_whitespace': ' '.join(prose.split()),
                        'lowercase': prose.lower(), 'punctuation_removed': re.sub(r'[^\w\s]', '', prose),
                        'word_shuffle': ' '.join(words)}
            for transform, text in versions.items():
                decoded = execute(binary, ['--decode'], text.encode())
                recovered = decoded.stdout.removesuffix(b'\n').removesuffix(b'\r') == payload
                rows.append(dict(seed=seed, dialect=dialect, transform=transform,
                                 recovered=recovered, returncode=decoded.returncode,
                                 payload_bytes=len(payload), encoded_bytes=len(text.encode()),
                                 encoded_words=len(text.split()),
                                 stderr=decoded.stderr.decode(errors='replace')[:200]))
    summary = {'project': 'Glossia v0.6.0', 'classification': 'readable encoding; no concealment claim',
               'binary_sha256': actual, 'cases': len(rows),
               'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'cells': [{'dialect': dialect, 'transform': transform,
                          'n': len(cell), 'recovered': sum(r['recovered'] for r in cell),
                          'mean_encoded_bytes': sum(r['encoded_bytes'] for r in cell) / len(cell)}
                         for dialect in ['body', 'subject', 'haiku']
                         for transform in versions
                         if (cell := [r for r in rows if r['dialect'] == dialect and r['transform'] == transform])]}
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    raw = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows).encode()
    summary['raw_sha256'] = hashlib.sha256(raw).hexdigest()
    (out / 'glossia_raw.jsonl').write_bytes(raw)
    (out / 'glossia_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--binary-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.binary, args.binary_sha256, args.output)))
