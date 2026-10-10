"""Recompute the entire offline matrix and compare it with saved measurements."""
import argparse
import json
import tempfile
from pathlib import Path

from stego_invoice_channels import run


def verify(manifest, output):
    output = Path(output)
    with tempfile.TemporaryDirectory(prefix='alife-invoice-verify-') as scratch:
        run(manifest, scratch)
        errors = [name + ' differs from recomputed experiment'
                  for name in ('raw.jsonl', 'summary.json')
                  if (output / name).read_bytes() != (Path(scratch) / name).read_bytes()]
    return {'valid': not errors, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.manifest, args.output)
    print(json.dumps(result))
    raise SystemExit(0 if result['valid'] else 1)
