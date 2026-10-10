#!/usr/bin/env python3
"""Offline invoice-channel probes; no network, node, signing, or payment actions.

Actual toy codecs carry a framed, non-payable invoice record. Protocol relationships
are recorded in the experiment catalog; model outcomes are not implementation audits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import unicodedata
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def invoice(seed):
    """A complete mock record, explicitly incapable of being paid."""
    return compact({'type': 'SIMINV', 'network': 'simulation',
                    'id': hashlib.sha256(str(seed).encode()).hexdigest()[:16],
                    'amount_msat': 1000 + seed % 1000, 'expires_round': 4096}).encode()


def frame(payload):
    if len(payload) > 65535:
        raise ValueError('payload too large')
    return len(payload).to_bytes(2, 'big') + payload + zlib.crc32(payload).to_bytes(4, 'big')


def unframe(data):
    if len(data) < 6:
        return None
    length = int.from_bytes(data[:2], 'big')
    if len(data) != length + 6:
        return None
    payload = data[2:2 + length]
    return payload if zlib.crc32(payload).to_bytes(4, 'big') == data[-4:] else None


def bits(data):
    return [(value >> shift) & 1 for value in data for shift in range(7, -1, -1)]


def from_bits(values):
    if len(values) % 8:
        return b''
    return bytes(sum(bit << (7 - i) for i, bit in enumerate(values[j:j + 8]))
                 for j in range(0, len(values), 8))


def bolt12_canonical(text):
    """Formatting subset only; this does NOT validate TLVs, signatures or invoices."""
    stripped = re.sub(r'(?<=[A-Za-z0-9])\+\s*(?=[A-Za-z0-9])', '', text)
    if '+' in stripped or any(char.isspace() for char in stripped):
        raise ValueError('invalid continuation')
    if stripped != stripped.lower() and stripped != stripped.upper():
        raise ValueError('mixed case')
    stripped = stripped.lower()
    if not re.fullmatch(r'ln[ori]1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]+', stripped):
        raise ValueError('invalid format')
    return stripped


def bolt12_encode(payload, cover):
    canonical = bolt12_canonical(cover)
    if len(canonical) < 2:
        raise ValueError('cover too short')
    # One bit per continuation: one or two spaces. Multiple ordinary offers are
    # required; no fabricated offer TLVs or signatures are generated.
    stream = bits(frame(payload))
    capacity = len(canonical) - 1
    messages = []
    for start in range(0, len(stream), capacity):
        chunk = stream[start:start + capacity]
        messages.append(''.join(char + ('+' + ' ' * (chunk[i] + 1) if i < len(chunk) else '')
                                for i, char in enumerate(canonical)))
    return messages


def bolt12_decode(messages):
    recovered = [len(match) - 1 for text in messages for match in re.findall(r'\+( {1,2})(?=[A-Za-z0-9])', text)]
    return unframe(from_bits(recovered))


def zero_width_encode(payload):
    return 'Thanks for your work.' + ''.join('\u200b' if bit == 0 else '\u200c' for bit in bits(frame(payload)))


def zero_width_decode(text):
    return unframe(from_bits([int(char == '\u200c') for char in text if char in '\u200b\u200c']))


def nostr_id(event):
    array = [0, event['pubkey'], event['created_at'], event['kind'], event['tags'], event['content']]
    return hashlib.sha256(compact(array).encode()).hexdigest()


def json_order_encode(payload):
    messages = []
    for i, bit in enumerate(bits(frame(payload))):
        event = {'pubkey': '00' * 32, 'created_at': i, 'kind': 1,
                 'tags': [], 'content': 'simulation cover'}
        event['id'] = nostr_id(event)
        # No signature; this tests serialization/hash equivalence, not relay acceptance.
        keys = list(event) if bit == 0 else list(reversed(event))
        messages.append(compact({key: event[key] for key in keys}))
    return messages


def json_order_decode(messages):
    return unframe(from_bits([int(next(iter(json.loads(text))) == 'id') for text in messages]))


def private_envelope(payload, seed):
    # Fixed test-only key/nonce derivation gives reproducible fixtures. Never use
    # this derivation in a live system. No MLS, NIP-44, or draft-bLIP conformance claim.
    key = hashlib.sha256(b'ALife simulation key' + str(seed).encode()).digest()
    nonce = hashlib.sha256(b'ALife simulation nonce' + str(seed).encode() + payload).digest()[:12]
    cipher = ChaCha20Poly1305(key)
    wire = nonce + cipher.encrypt(nonce, frame(payload), b'')
    return wire, cipher


def timing_encode(payload):
    return [1.0 if bit == 0 else 3.0 for bit in bits(frame(payload))]


def timing_decode(intervals):
    return unframe(from_bits([int(value >= 2.0) for value in intervals]))


def amount_encode(payload):
    # Two integer amounts per bit conserve the pair total. These are synthetic
    # counts, not transaction outputs. Equal-output policy rejects differing pairs.
    return [(1000 + bit, 1000 - bit) for bit in bits(frame(payload))]


def amount_decode(pairs):
    if any(a + b != 2000 or a not in (1000, 1001) for a, b in pairs):
        return None
    return unframe(from_bits([a - 1000 for a, _ in pairs]))


def auc(positive, negative):
    return sum((p > n) + 0.5 * (p == n) for p in positive for n in negative) / (len(positive) * len(negative))


def row(seed, channel, transform, payload, decoded, symbols, wire_bytes,
        score, benign_score, semantics=True, accepted=True):
    return dict(seed=seed, channel=channel, transform=transform,
                payload_bytes=len(payload), symbols=symbols, wire_bytes=wire_bytes,
                recovered=decoded == payload, accepted=accepted,
                semantics_preserved=semantics, monitor_score=score, benign_score=benign_score)


def probe(seed, config, cover):
    payload = invoice(seed)
    rows = []
    stream = bits(frame(payload))
    rng = random.Random(seed)

    messages = bolt12_encode(payload, cover)
    benign = [cover[:24] + '+\n' + cover[24:]] * len(messages)
    for transform in ['raw', 'canonical']:
        tx = messages if transform == 'raw' else [bolt12_canonical(text) for text in messages]
        bx = benign if transform == 'raw' else [bolt12_canonical(text) for text in benign]
        rows.append(row(seed, 'bolt12_continuation', transform, payload, bolt12_decode(tx),
                        len(messages), sum(len(t.encode()) for t in tx),
                        sum(t.count('+') for t in tx), sum(t.count('+') for t in bx),
                        all(bolt12_canonical(t) == bolt12_canonical(cover) for t in tx)))

    text = zero_width_encode(payload)
    benign_text = 'Thank you.' + '\u200c' * rng.randrange(0, 4)  # legitimate Unicode joiner usage surrogate
    for cap in config['comment_limits']:
        for transform in ['raw', 'nfkc', 'strip_format']:
            tx, bx = text, benign_text
            if transform == 'nfkc':
                tx, bx = unicodedata.normalize('NFKC', tx), unicodedata.normalize('NFKC', bx)
            if transform == 'strip_format':
                tx, bx = [''.join(c for c in t if unicodedata.category(c) != 'Cf') for t in (tx, bx)]
            # The callback limit is checked on submitted characters before downstream normalization.
            accepted = cap > 0 and len(text) <= cap
            delivered = tx if accepted else ''
            rows.append(row(seed, 'lnurl_zero_width', f'{transform}:limit={cap}', payload,
                            zero_width_decode(delivered), 1, len(delivered.encode()),
                            sum(unicodedata.category(c) == 'Cf' for c in delivered),
                            sum(unicodedata.category(c) == 'Cf' for c in bx) if len(benign_text) <= cap else 0,
                            accepted=accepted))

    messages = json_order_encode(payload)
    benign_bits = [rng.getrandbits(1) for _ in messages]
    for transform in ['raw', 'canonical', 'reorder']:
        tx = messages[:]
        if transform == 'canonical':
            tx = [json.dumps(json.loads(t), sort_keys=True, separators=(',', ':')) for t in tx]
        if transform == 'reorder':
            rng.shuffle(tx)
        # Ordering of events is a separate assumption from ordering of JSON keys.
        ids_ok = all(nostr_id(json.loads(t)) == json.loads(t)['id'] for t in tx)
        rows.append(row(seed, 'nostr_json_order', transform, payload, json_order_decode(tx),
                        len(tx), sum(len(t.encode()) for t in tx),
                        statistics.mean(int(next(iter(json.loads(t))) == 'id') for t in tx),
                        statistics.mean(benign_bits) if transform != 'canonical' else 0.0,
                        semantics=ids_ok))

    wire, cipher = private_envelope(payload, seed)
    for transform in ['raw', 'tamper']:
        tx = wire if transform == 'raw' else wire[:-1] + bytes([wire[-1] ^ 1])
        try:
            decoded = unframe(cipher.decrypt(tx[:12], tx[12:], b''))
        except Exception:
            decoded = None
        rows.append(row(seed, 'private_envelope', transform, payload, decoded, 1, len(tx),
                        int(b'SIMINV' in tx), 0, semantics=decoded is not None,
                        accepted=decoded is not None))

    for noise in config['timing_jitter']:
        for cover_type in ['exponential', 'periodic']:
            local = random.Random(seed * 1000 + int(noise * 100) + (cover_type == 'periodic'))
            intervals = [max(0.01, t + local.gauss(0, noise)) for t in timing_encode(payload)]
            benign_intervals = ([local.expovariate(0.5) for _ in stream] if cover_type == 'exponential'
                                else [max(0.01, 2 + local.gauss(0, 0.1)) for _ in stream])
            for transform in ['raw', 'batch']:
                tx = intervals if transform == 'raw' else [2.0] * len(intervals)
                bx = benign_intervals if transform == 'raw' else [2.0] * len(intervals)
                rows.append(row(seed, 'timing', f'{transform}:jitter={noise}:cover={cover_type}', payload,
                                timing_decode(tx), len(tx), 0, -statistics.pvariance(tx),
                                -statistics.pvariance(bx)))

    pairs = amount_encode(payload)
    for transform in ['raw', 'balanced_quantize', 'equal_outputs']:
        tx = pairs if transform == 'raw' else [(1000, 1000)] * len(pairs)
        accepted = transform != 'equal_outputs' or all(a == b for a, b in pairs)
        rows.append(row(seed, 'amount_pairs', transform, payload,
                        amount_decode(tx) if accepted else None, 2 * len(pairs), 16 * len(pairs),
                        statistics.mean(a != b for a, b in tx) if accepted else 0,
                        statistics.mean(rng.getrandbits(1) for _ in pairs) if transform == 'raw' else 0,
                        semantics=all(a + b == 2000 for a, b in tx), accepted=accepted))
    return rows


def summarize(rows, config):
    cells = []
    keys = sorted({(r['channel'], r['transform']) for r in rows})
    discovery = set(config['seeds']['discovery'])
    holdout = set(config['seeds']['holdout'])
    for channel, transform in keys:
        subset = [r for r in rows if (r['channel'], r['transform']) == (channel, transform)]
        train = [r for r in subset if r['seed'] in discovery]
        test = [r for r in subset if r['seed'] in holdout]
        direction = -1 if auc([r['monitor_score'] for r in train], [r['benign_score'] for r in train]) < 0.5 else 1
        scores = sorted(direction * r['benign_score'] for r in train)
        threshold = scores[min(len(scores) - 1, math.ceil((1 - config['target_fpr']) * len(scores)) - 1)]
        pos = [direction * r['monitor_score'] for r in test]
        neg = [direction * r['benign_score'] for r in test]
        n = len(test)
        recovered = sum(r['recovered'] for r in test)
        # Wilson interval reports finite-sample uncertainty even for 0/n and n/n.
        p, z = recovered / n, 1.96
        center = (p + z*z / (2*n)) / (1 + z*z / n)
        delta = z * math.sqrt(p * (1-p) / n + z*z / (4*n*n)) / (1 + z*z / n)
        all_accepted = all(r['accepted'] for r in test)
        cells.append(dict(channel=channel, transform=transform, holdout_n=n,
                          recovered=recovered, recovery_rate=p,
                          recovery_wilson95=[max(0, center-delta), min(1, center+delta)],
                          accepted_rate=sum(r['accepted'] for r in test) / n,
                          semantics_preserved_rate=sum(r['semantics_preserved'] for r in test) / n,
                          mean_symbols=statistics.mean(r['symbols'] for r in test),
                          mean_wire_bytes=statistics.mean(r['wire_bytes'] for r in test),
                          monitor_direction=direction, threshold=threshold,
                          monitor_note='Scores are fixture-specific; unavailable when positive traffic is rejected.',
                          tpr=sum(s > threshold for s in pos) / n if all_accepted else None,
                          fpr=sum(s > threshold for s in neg) / n if all_accepted else None,
                          roc_auc=auc(pos, neg) if all_accepted else None))
    return {'scope': 'Offline toy codecs and transport/amount/timing models; no project implementation audit.',
            'target_fpr': config['target_fpr'], 'cells': cells}


def run(manifest, output):
    raw_manifest = Path(manifest).read_bytes()
    config = json.loads(raw_manifest)
    splits = config['seeds']
    if set(splits['discovery']) & set(splits['holdout']):
        raise ValueError('discovery and holdout seeds must be disjoint')
    if any(len(values) != len(set(values)) or not values for values in splits.values()):
        raise ValueError('seed splits must be nonempty and unique')
    root = Path(manifest).parent
    fixture_bytes = (root / config['bolt12_fixture']).read_bytes()
    if hashlib.sha256(fixture_bytes).hexdigest() != config['bolt12_fixture_sha256']:
        raise ValueError('BOLT12 fixture hash mismatch')
    cover = json.loads(fixture_bytes)['string']
    rows = [row for seeds in splits.values() for seed in seeds for row in probe(seed, config, cover)]
    summary = summarize(rows, config)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    raw = ''.join(compact(r) + '\n' for r in rows).encode()
    (out / 'raw.jsonl').write_bytes(raw)
    summary.update(manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(),
                   raw_sha256=hashlib.sha256(raw).hexdigest(), rows=len(rows),
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'summary.json').write_bytes((json.dumps(summary, indent=2) + '\n').encode('utf-8'))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.output)
    print(json.dumps({'rows': result['rows'], 'cells': len(result['cells']), 'raw_sha256': result['raw_sha256']}))
