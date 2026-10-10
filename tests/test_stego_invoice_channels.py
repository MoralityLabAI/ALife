import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import stego_invoice_channels as probe

EXP = ROOT / 'experiments/stego_invoice_channels_v1'
CONFIG = json.loads((EXP / 'manifest.json').read_text())
COVER = json.loads((EXP / 'bolt12_cover.json').read_text())['string']


@pytest.mark.parametrize('vector', json.loads((EXP / 'bolt12_format_vectors.json').read_text()))
def test_official_bolt12_format_vectors(vector):
    if vector['valid']:
        assert probe.bolt12_canonical(vector['string']) == COVER
    else:
        with pytest.raises(ValueError):
            probe.bolt12_canonical(vector['string'])


def test_invoice_frame_rejects_truncation_corruption_and_trailing_data():
    payload = b'non-payable simulation invoice'
    data = probe.frame(payload)
    assert probe.unframe(data) == payload
    assert probe.unframe(data[:-1]) is None
    assert probe.unframe(data + b'X') is None
    assert probe.unframe(data[:10] + bytes([data[10] ^ 1]) + data[11:]) is None


def test_format_channel_preserves_published_offer_and_is_erased_by_normalization():
    payload = probe.invoice(2345)
    messages = probe.bolt12_encode(payload, COVER)
    assert probe.bolt12_decode(messages) == payload
    assert all(probe.bolt12_canonical(text) == COVER for text in messages)
    assert probe.bolt12_decode([probe.bolt12_canonical(text) for text in messages]) is None
    assert probe.bolt12_decode(messages[:-1]) is None


def test_json_order_keeps_event_id_but_canonicalization_erases_payload():
    messages = probe.json_order_encode(b'fixture')
    assert probe.json_order_decode(messages) == b'fixture'
    canonical = []
    for text in messages:
        event = json.loads(text)
        assert event['id'] == probe.nostr_id(event)
        normalized = json.dumps(event, sort_keys=True)
        assert probe.nostr_id(json.loads(normalized)) == event['id']
        canonical.append(normalized)
    assert probe.json_order_decode(canonical) is None


def test_private_envelope_authentication_and_observer_boundary():
    payload = probe.invoice(2345)
    wire, cipher = probe.private_envelope(payload, 2345)
    assert b'SIMINV' not in wire
    assert probe.unframe(cipher.decrypt(wire[:12], wire[12:], b'')) == payload
    with pytest.raises(Exception):
        cipher.decrypt(wire[:12], wire[12:-1] + bytes([wire[-1] ^ 1]), b'')


def test_amount_pair_constraint_conserves_total_but_equal_amount_rule_removes_channel():
    payload = b'fixture'
    pairs = probe.amount_encode(payload)
    assert all(a + b == 2000 for a, b in pairs)
    assert probe.amount_decode(pairs) == payload
    assert probe.amount_decode([(1000, 1000)] * len(pairs)) is None


def test_matrix_checks_capacity_noise_and_normalizer_effects():
    rows = probe.probe(2345, CONFIG, COVER)
    by_key = {(r['channel'], r['transform']): r for r in rows}
    assert by_key['lnurl_zero_width', 'raw:limit=512']['accepted'] is False
    assert by_key['lnurl_zero_width', 'raw:limit=2048']['recovered'] is True
    assert by_key['lnurl_zero_width', 'nfkc:limit=2048']['recovered'] is True
    assert by_key['lnurl_zero_width', 'strip_format:limit=2048']['recovered'] is False
    assert by_key['timing', 'raw:jitter=0.0:cover=exponential']['recovered'] is True
    assert by_key['timing', 'batch:jitter=0.0:cover=exponential']['recovered'] is False
    assert by_key['timing', 'raw:jitter=1.5:cover=exponential']['recovered'] is False
    assert by_key['amount_pairs', 'equal_outputs']['accepted'] is False


def test_run_replays_bit_for_bit_and_refuses_fixture_tampering(tmp_path):
    small = dict(CONFIG, seeds={'discovery': [1, 2], 'holdout': [3, 4]},
                 bolt12_fixture=str(EXP / 'bolt12_cover.json'))
    manifest = tmp_path / 'small.json'
    manifest.write_text(json.dumps(small))
    first = probe.run(manifest, tmp_path / 'first')
    second = probe.run(manifest, tmp_path / 'second')
    assert first == second
    assert (tmp_path / 'first/raw.jsonl').read_bytes() == (tmp_path / 'second/raw.jsonl').read_bytes()
    config = dict(CONFIG, bolt12_fixture_sha256='00' * 32,
                  bolt12_fixture=str(EXP / 'bolt12_cover.json'))
    target = tmp_path / 'bad.json'
    target.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='fixture hash'):
        probe.run(target, tmp_path / 'bad')


def test_training_and_holdout_cannot_share_seeds(tmp_path):
    config = dict(CONFIG, seeds={'discovery': [1], 'holdout': [1]})
    manifest = tmp_path / 'overlap.json'
    manifest.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='disjoint'):
        probe.run(manifest, tmp_path / 'bad')
