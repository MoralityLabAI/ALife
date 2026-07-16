# Pixie Sanctuary v1

This is a deterministic mechanics prototype for asking what a Pixie can do
with physics-native critters. It is not a pet-emotion simulator and it does not
rank interactions by a single fun, delight, or complexity score.

## Implemented mechanics matrix

Every row/column cell below is implemented and retained. Each treated world is
paired with an exact untreated copy, so a response means a verifiable field
difference caused by the scheduled local action.

| Critter / substrate | Observe | Touch | Sing | Feed | Cool | Shield |
| --- | --- | --- | --- | --- | --- | --- |
| Bitlichen / binary totalistic CA | exact no-op | flip a local disc | flip a radius-two ring | set a local disc alive | local neighbor majority | freeze a disc for four ticks |
| Prism Wyrm / six-phase cyclic CA | exact no-op | advance a local disc one phase | advance a radius-two ring | advance a local disc two phases | local phase consensus | freeze a disc for four ticks |
| Mitosis Moss / Gray-Scott field | exact no-op | move local V one display bin | pulse V on a radius-two ring | inject local U and V | local diffusive average | freeze a disc for four ticks |

The machine-readable taxonomy additionally indexes coupling shape, memory
carrier, readable response, gameplay role, hazards, and four backlog world
mechanics: portal ecology, a moving Pixie surface, cross-critter ecology, and
portable seed lineage.

## Frozen run

The v1 campaign contains 162 paired episodes:

- discovery: 36 episodes on 24x24 worlds for 40 ticks;
- confirmation: 72 episodes on 32x32 worlds for 48 ticks;
- holdout: 54 episodes on 40x40 worlds for 64 ticks;
- three scheduled actions per production episode, fixed degree 12, periodic
  boundaries, and no random draws after initialization.

All 135 non-observe episodes executed an exact substrate change; none of the 27
observe controls diverged. On confirmation and holdout seeds, every preferred
interaction was visible without globalizing:

| Preferred encounter hook | Confirmatory response | Holdout response | Design reading |
| --- | --- | --- | --- |
| Bitlichen + touch | 4/4 visible, 4/4 persistent; morphology/wave | 3/3 visible and persistent; morphology | Touch creates a colony-scale wound or seed, but the binary rule amplifies it far beyond the Pixie's hand. |
| Prism Wyrm + sing | 4/4 visible, 1/4 persistent; transient recovery | 3/3 visible, 2/3 persistent; recovery/waves | Song is timing-sensitive and often self-healing, making it suitable for resonance and shepherding puzzles. |
| Mitosis Moss + feed | 4/4 visible and persistent; localized scar | 3/3 visible and persistent; localized scar | Feeding leaves the clearest bounded, inspectable trace and is the strongest care/ecological-engineering candidate. |

The frozen hypotheses were supported within this sample. The result does not
show that critters feel, prefer, bond, learn, or understand the Pixie. “Memory”
here means persistence in a field configuration only.

## Run

```powershell
python src\pixie_sanctuary.py --manifest experiments\pixie_sanctuary_v1\manifest.json --demo --critter prism_wyrm --action sing --seed 42
python src\pixie_sanctuary.py --manifest experiments\pixie_sanctuary_v1\manifest.json --output results\pixie_sanctuary_v1 --splits all
python src\verify_pixie_sanctuary_artifacts.py results\pixie_sanctuary_v1 --portable --replay-samples 3
```

Artifacts are written through the repository's `results` junction to D: and
are intentionally ignored by Git. The next experiment should add bounded
cavern walls and Pixie motion before mixing critters or making a playability
claim.
