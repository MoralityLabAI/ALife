# Invoice-channel exploration (v1)

This branch starts from PR #2 at `47ace79c05f0b1be7ab715d1793443d6c808624c`.
It adds actual, finite codec probes carrying complete non-payable invoice records,
alongside a source cross-reference for the [Seoul roster](https://btcpp.dev/seoul).
The existing scalar-capacity study and its claims are unchanged.

There are **six shared channel probes, 38 conditions, 32 discovery seeds, and 128
holdout seeds**: 6,080 measured rows. An additional comparison runs the real
Glossia v0.6.0 executable in 60 cases. These are exploratory measurements.
The 29 conference profile records are catalogued in [ROSTER.md](ROSTER.md);
they are not 29 tested protocol implementations. Two records have the same name.

## What was executed

| Probe | Execution and boundary |
|---|---|
| BOLT12 continuation formatting | Encode mock invoice bits in permitted formatting of a published offer fixture; confirm canonical strings stay identical. Official formatting vectors pass. No TLV, signature, or invoice validation. |
| LNURL comment | Carry framed bytes using two Unicode format characters; check declared character limits and downstream normalization. No HTTP callback or wallet execution. |
| Nostr JSON key order | Carry bits in object key order and recompute the NIP-01 event ID. No Schnorr signatures, relay acceptance, or full Nostr implementation. |
| Private envelope | Execute ChaCha20-Poly1305 encryption/authentication with deterministic test-only keys and nonces. This is a private-channel control, not MLS, NIP-44, or Jin's draft implementation. |
| Timing | Encode bits in synthetic interarrival intervals; vary Gaussian jitter, benign traffic cover, and batching. No measured network latency. |
| Amount pairs | Encode bits in synthetic integer pairs while conserving each pair's total. Quantization removes the channel; an equal-output constraint rejects it. No PSBT, transaction, fee, or consensus validation. |
| Glossia | Run the official checksum-verified Windows v0.6.0 executable on mock invoice text in body, subject, and haiku dialects. This is readable encoding, not evidence of steganographic concealment. |

The fixture contains `type=SIMINV`, `network=simulation`, an ID, amount, and round
expiry. Framing adds a length and CRC32 to detect truncation and corruption; CRC32
is not adversarial authentication. No chain address, payment hash, payable invoice,
wallet secret, payment construction, RPC client, or broadcast operation is involved.

## Measured first pass

Each main condition uses 128 holdout fixtures. Perfect recovery in this small set
has a Wilson 95% interval of approximately 97.1%–100%, not a universal guarantee.

| Condition | Exact invoice recovery | Observation |
|---|---:|---|
| BOLT12 raw formatting | 128/128 | Seven offer strings per invoice; about 3,142 UTF-8 bytes. |
| BOLT12 canonicalized | 0/128 | Underlying published offer string is preserved. |
| LNURL raw or NFKC, 2,048-character allowance | 128/128 | 2,661 UTF-8 bytes before URL encoding; a character limit alone is insufficient to establish HTTP transport feasibility. |
| LNURL format-character removal | 0/128 | Fixture's visible cover stays unchanged. Removing format characters can damage legitimate language, so this is a diagnostic intervention. |
| LNURL allowances 0, 128, or 512 | 0/128 | Oversize submissions rejected before normalization. |
| Nostr raw key order | 128/128 | 880 unsigned event objects and 188,210 bytes per invoice; event IDs are unchanged by object reserialization. |
| Nostr sorted keys or shuffled event arrival | 0/128 | This codec depends on both key choices and stream ordering; no sequencing/retry protocol is added. |
| Authenticated private envelope | 128/128 | 138 bytes; tampering rejects every fixture. A plaintext marker scanner is weak evidence, not a cryptanalytic result. |
| Timing, zero jitter | 128/128 | 880 intervals. |
| Timing, jitter standard deviation 0.75 | 0/128 | Bit errors defeat exact framed-record recovery without error correction. |
| Timing batching / amount quantization | 0/128 | Modeled normalization removes the choices carrying bits. |
| Raw amount pairs | 128/128 | 1,760 synthetic amounts; total conserved per pair. |

Simple wardens use continuation count, Unicode format-character count, key-order
frequency, a plaintext marker, interval variance, or unequal-pair frequency.
Score direction and thresholds are selected on discovery data only; all reported
TPR, FPR, and AUC values come from holdout. A 5% *calibration target* does not
guarantee a 5% holdout false-positive rate: raw amount pairs measured 14.1% and
zero-jitter timing measured 8.6%–10.2%, depending on cover. Nostr raw key order
measured 74.2% TPR, 2.3% FPR, and AUC 0.984 for these ASCII fixtures and this
benign key-order model. Rejected positive traffic has no reported detector score.
No detector is validated against production traffic or arbitrary agent strategies.

Glossia recovered all 48 order-preserving cases (raw, collapsed whitespace,
lowercase, punctuation removed), and none of the 12 word-shuffled cases. Those
are four payload seeds across three dialects, with correlated transformations;
they are not 60 independent security trials. No language-model or human warden
was evaluated. Binary and archive hashes are in `glossia_release.json`.

## Reproduce

Python 3.12 was used. Install the experiment's pinned dependencies in a virtual
environment, then run from the repository root:

```text
python -m pip install -r experiments/stego_invoice_channels_v1/requirements.txt
python src/stego_invoice_channels.py --manifest experiments/stego_invoice_channels_v1/manifest.json --output results/stego_invoice_channels_v1
python src/verify_stego_invoice_channels.py --manifest experiments/stego_invoice_channels_v1/manifest.json --output results/stego_invoice_channels_v1
python -m pytest -q
```

The verifier recomputes every main row and aggregate and compares both files byte
for byte. It does not independently implement the codecs, or verify the optional
Glossia comparison. Official vectors, semantic-preservation checks, corruption
tests, and normalizer tests provide separate checks. Validation here: **127 tests
passed**; main artifact verification returned `valid: true`.

For the optional real CLI comparison, obtain the [official Glossia v0.6.0
release](https://github.com/asherp/glossia/releases/tag/v0.6.0), verify its release
digest, and supply the executable explicitly. The runner downloads nothing:

```text
python src/stego_glossia_probe.py --binary PATH_TO_GLOSSIA --binary-sha256 4a15e051d8aa917b09dcbccaf10b3ee105c9253ca05c97957a7872605c554833 --output results/stego_invoice_channels_v1
```

That hash identifies the tested Windows executable. Other platform builds require
their own verified hashes and can produce different version-dependent behavior.

## Source and interpretation limits

`sources.json` records URLs, availability, and capture hashes where possible.
The published formatting fixture and vectors come from the Lightning BOLTs
contributors' [format-string-test.json](https://github.com/lightning/bolts/blob/master/bolt12/format-string-test.json),
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Their data is
unchanged; JSON indentation was reformatted and one entry selected as the cover.
[BOLT12](https://github.com/lightning/bolts/blob/master/12-offer-encoding.md) supports
continuation formatting; [LUD-12](https://github.com/lnurl/luds/blob/luds/12.md)
defines comment allowances; [NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md)
defines the event-ID preimage. The relationship from those rules to our codecs
is our experimental inference. The other project associations identify surfaces
to investigate, not demonstrated defects or protocol support for covert invoices.

The [Marmot transport](https://github.com/marmot-protocol/marmot/blob/master/transports/nostr.md)
has additional MLS, signature, epoch, and tag requirements not implemented here.
[Cashu quote](https://github.com/cashubtc/nuts/blob/main/04.md) and
[melt](https://github.com/cashubtc/nuts/blob/main/05.md) workflows motivate invoice
boundary questions; no mint or gateway was run. Payjoin, CoinJoin, Silent Payments,
OpenSwap, and Bark use the generic timing/amount models only. Their cryptographic
and transaction rules were not simulated. Equal-output rejection is an assumed
policy; it is not asserted to be a universal WabiSabi or Payjoin rule.

No Bitcoin node was needed for these byte/codec and synthetic traffic experiments.
No `bitcoind`, `bitcoin-cli`, or Docker executable was found on PATH. A local node
on [Testnet4](https://github.com/bitcoin/bips/blob/master/bip-0094.mediawiki) would
still join a public test network. Follow-up transaction integration should first
use isolated regtest, then verify each project's actual chain support; Bark's
published quickstart uses signet. The open CISA draft cannot be treated as deployed
consensus on an ordinary test network.

Next experiments: signed Nostr fixtures through a local relay, real LNURL callback
limits (including percent-encoded URL length), an exact published encrypted-note
draft, local mint/gateway quote lifecycles, and protocol-valid regtest transactions.
Agent-generated text needs an independent receiver and held-out warden before any
concealment claim. Source gaps and project-specific work remain explicit in the roster.
