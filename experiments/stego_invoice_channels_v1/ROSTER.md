# Seoul project cross-reference

Snapshot: 10 October 2026. The [main agenda](https://btcpp.dev/seoul) contains 29 profile records, including two profiles named Dan Gould. The separate directory was less complete when retrieved. Records are retained separately rather than inferring identity.

A modeled channel is a shared surface experiment, not execution of the named wallet or protocol. All project-specific integration remains untested except the separately recorded Glossia CLI comparison. Source availability is recorded in `sources.json`.

| Profile | Project/context | Primary sources | Coverage |
|---|---|---|---|
| [Eric Sirion](https://btcpp.dev/whois/elsirion) | Fedimint | [fedimint](https://raw.githubusercontent.com/fedimint/fedimint/master/README.md) | private_envelope, timing, amount_pairs |
| [Fabian Jahr](https://btcpp.dev/whois/fjahr) | CISA | [cisa](https://raw.githubusercontent.com/fjahr/bips/cisa/bip-0460.mediawiki) | draft source reviewed; consensus implementation not tested |
| [Kruw](https://btcpp.dev/whois/kruwed) | Wasabi/WabiSabi | [wasabi](https://docs.wasabiwallet.io/using-wasabi/CoinJoin.html) | amount_pairs, timing |
| [Oleksandr Kurbatov](https://btcpp.dev/whois/mjthatch) | Silent Payments/multiparty | [silent_payments](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0352.mediawiki) | amount_pairs |
| [Adam Gibson (@waxwing)](https://btcpp.dev/whois/adam-gibson-waxwing) | JoinMarket/privacy analysis | [joinmarket](https://raw.githubusercontent.com/JoinMarket-Org/joinmarket-clientserver/master/README.md) | amount_pairs, timing |
| [stutxo](https://btcpp.dev/whois/stutxo) | Char/privacy comparison | [char](https://char.network) | context/source gap; no invoice-channel test |
| [Anmol Sharma](https://btcpp.dev/whois/theanmolsharma) | Silent Payments | [silent_payments](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0352.mediawiki) | amount_pairs |
| [Asher Pembroke](https://btcpp.dev/whois/asherp) | Rose/Fathomx; additional Glossia repository | [glossia](https://raw.githubusercontent.com/asherp/glossia/master/README.md) | Real Glossia CLI robustness comparison; Rose source not located |
| [Ben Knab](https://btcpp.dev/whois/benknab) | Message proofs | [message_proofs](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0322.mediawiki) | context/source gap; no invoice-channel test |
| [Calvin Kim](https://btcpp.dev/whois/kcalvinalvin) | Privacy context | Agenda only / source gap | context/source gap; no invoice-channel test |
| [Dan Gould](https://btcpp.dev/whois/dangould-c420fc7c) | Payjoin | [payjoin](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0078.mediawiki) | amount_pairs |
| [Dan Gould](https://btcpp.dev/whois/dangould-97659680) | Payjoin | [payjoin](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0078.mediawiki) | amount_pairs |
| [Danny](https://btcpp.dev/whois/dannym-arx-45ec0b3e) | Marmot | [marmot](https://raw.githubusercontent.com/marmot-protocol/marmot/master/transports/nostr.md), [nostr_event](https://raw.githubusercontent.com/nostr-protocol/nips/master/01.md) | private_envelope, nostr_json_order, timing |
| [Jin](https://btcpp.dev/whois/4xvgal) | Encrypted payer notes draft | [lnurl_comment](https://raw.githubusercontent.com/lnurl/luds/luds/12.md), [bolt12](https://raw.githubusercontent.com/lightning/bolts/master/12-offer-encoding.md) | lnurl_zero_width, bolt12_continuation, private_envelope |
| [Joe Miyamoto](https://btcpp.dev/whois/joemphilips) | bitCaster/Cashu | [bitcaster](https://bitcasterdoc.com/technical/), [cashu_mint](https://raw.githubusercontent.com/cashubtc/nuts/main/04.md), [cashu_melt](https://raw.githubusercontent.com/cashubtc/nuts/main/05.md), [nostr_event](https://raw.githubusercontent.com/nostr-protocol/nips/master/01.md) | private_envelope, nostr_json_order, timing, amount_pairs |
| [niftynei](https://btcpp.dev/whois/niftynei) | Base58/education | [base58](https://base58.school) | context/source gap; no invoice-channel test |
| [Rademenez](https://btcpp.dev/whois/rademenez) | QR/Lightning bridge | [lnurl_comment](https://raw.githubusercontent.com/lnurl/luds/luds/12.md) | lnurl_zero_width, timing |
| [Matthew Vuk](https://btcpp.dev/whois/matthewvuk2) | Bark/Cashu | [bark](https://second.tech/docs), [cashu_mint](https://raw.githubusercontent.com/cashubtc/nuts/main/04.md), [cashu_melt](https://raw.githubusercontent.com/cashubtc/nuts/main/05.md) | private_envelope, timing, amount_pairs |
| [m0wer](https://btcpp.dev/whois/m0wer) | JoinMarket NG | [joinmarket_ng](https://raw.githubusercontent.com/joinmarket-ng/joinmarket-ng/main/README.md) | private_envelope, timing, amount_pairs |
| [sam](https://btcpp.dev/whois/samthomson) | Nostr/relaykit | [nostr_event](https://raw.githubusercontent.com/nostr-protocol/nips/master/01.md), [nostr_encryption](https://raw.githubusercontent.com/nostr-protocol/nips/master/44.md) | nostr_json_order, private_envelope, timing |
| [Misha Komarov](https://btcpp.dev/whois/nemothenoone) | Allocin | [allocin](https://allocin.it) | context/source gap; no invoice-channel test |
| [Marek Feder](https://btcpp.dev/whois/federmarek) | AmityAge | [amityage](https://www.amityage.com) | context/source gap; no invoice-channel test |
| [Nick Farrow](https://btcpp.dev/whois/nickfarrow) | Frostsnap/FROST | [frostsnap_repo](https://raw.githubusercontent.com/frostsnap/frostsnap/master/README.md) | signer source context; no invoice carrier tested |
| [Stark](https://btcpp.dev/whois/stark-3k) | OpenSwap | [openswap](https://raw.githubusercontent.com/citadel-foss/openswap/master/README.md), [nostr_event](https://raw.githubusercontent.com/nostr-protocol/nips/master/01.md) | nostr_json_order, timing, amount_pairs |
| [Pacman](https://btcpp.dev/whois/kkdao) | Krux/Sparrow | [krux_repo](https://raw.githubusercontent.com/selfcustody/krux/main/README.md), [silent_payments](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0352.mediawiki) | amount_pairs |
| [Naiyoma](https://btcpp.dev/whois/naiyoma) | Addrman dashboard | [addrman](https://stratospher.github.io/addrman-dashboard/) | context/source gap; no invoice-channel test |
| [KIM CHANGHAK](https://btcpp.dev/whois/gosunuts) | bitcoin-rs | [bitcoin_rs](https://raw.githubusercontent.com/gosuda/bitcoin-rs/main/README.md) | context/source gap; no invoice-channel test |
| [Minseok Song](https://btcpp.dev/whois/metaphorics) | bitcoin-rs | [bitcoin_rs](https://raw.githubusercontent.com/gosuda/bitcoin-rs/main/README.md) | context/source gap; no invoice-channel test |
| [Justin Moeller](https://btcpp.dev/whois/m1sterc001guy) | Fedimint/ROAST | [fedimint](https://raw.githubusercontent.com/fedimint/fedimint/master/README.md) | private_envelope, timing, amount_pairs |

Open items: locate Jin's exact encrypted-note draft and Rose implementation; verify multiparty Silent Payments and ROAST changes against their exact revisions; obtain stable project sources for unresolved entries. CISA is an open draft, so ordinary Testnet4 cannot be assumed to enforce it. No profile association establishes that a project supports covert transfers.

Only the official BOLT12 fixture and formatting test vectors are copied into the experiment. Other source files remain in research scratch, identified by content hashes where available. Links to moving branches describe the captured source and may change later.
