# Pixie Folded Cavern v1

The folded cavern is a genuine product-space habitat presented through a stable
two-dimensional room. The visible world is always 8x8. Every added dimension
is a binary hidden axis, so each visible position has 1 chamber in 2-D, 4 in
4-D, 16 in 6-D, 64 in 8-D, and 512 in 11-D.

The Pixie sees hidden-coordinate zero plus an activity shadow that aggregates
the other chambers. This gives higher-dimensional behavior a playable reading:
critters can burrow out of sight, store a field scar, travel through parallel
routes, or fail to resurface.

## Mechanics taxonomy

| Axis | Implemented cells | Player meaning |
| --- | --- | --- |
| Dimension | 2, 4, 6, 8, 11 | Increasing hidden habitat depth behind the same viewport |
| Fixed neighborhood | Degree 16 at every dimension | Bounded local bandwidth that spans every axis |
| Dense diagnostic | Product-Moore at dimensions 2, 4, 6 | Highly connected control; capped before neighborhood explosion |
| Surface-local | Radius-two visible disc | Touch what the Pixie can see |
| Fiber-column | Radius-one disc through every hidden coordinate | Push through the whole folded column |
| Axis-probe | Radius-two disc one chamber deep, invisible at application | Reach through a seam and wait for resurfacing |

Product-Moore degree is 8 in 2-D, 35 in 4-D, and 143 in 6-D. It would reach
575 in 8-D and 4,607 in 11-D, so those cells are deliberately outside the v1
resource contract.

## Frozen results

The campaign retained all 288 paired episodes and all 216 split-aware mechanics
cells. Every action produced an exact substrate change; every summary, event
cause, geometry declaration, and trajectory hash was independently re-derived.

| Registered question | Confirmation | Holdout | Result |
| --- | --- | --- | --- |
| Do deep probes reliably resurface at least two critters? | Bitlichen 8/8; Moss 8/8; Wyrm 3/8 | Bitlichen 4/4; Moss 4/4; Wyrm 2/4 | Supported for two critters |
| Does a whole-fiber action improve visible control? | Lower for all three critters | Lower for all three critters | Not supported; excessive depth dilutes visible control |
| Do fixed-degree actions always avoid globalization? | Six globalizations | Two globalizations | Not supported as written; every failure was in 2-D and none occurred in dimensions 4-11 |
| Does response class depend on intervention depth? | 0.67350 bits mutual information | 0.62924 bits | Supported within sample |

The strongest encounter hooks are therefore asymmetric:

- Bitlichen: reliable hidden burrow and later surface wound/growth pattern.
- Mitosis Moss: reliable hidden nutrient reservoir and visible leakage scar.
- Prism Wyrm: an unreliable deep singer that can remain lost at dimensions 8
  and 11, creating a rescue or investigation mechanic rather than a dependable
  care action.
- Fiber columns: useful as a hazardous blunt tool, not an upgrade over precise
  surface interaction.

## Run and verify

```powershell
python src\pixie_folded_cavern.py --manifest experiments\pixie_folded_cavern_v1\manifest.json --demo --dimension 6 --critter prism_wyrm --intervention-depth axis_probe
python src\pixie_folded_cavern.py --manifest experiments\pixie_folded_cavern_v1\manifest.json --output results\pixie_folded_cavern_v1 --splits all
python src\verify_pixie_folded_cavern_artifacts.py results\pixie_folded_cavern_v1 --portable --replay-samples 3
```

## Claim boundary and next mechanic

This is model-only control/design evidence. It does not establish physical
extra dimensions, emotion, cognition, life, or player enjoyment. Total habitat
capacity grows with dimension and fiber-column dosage grows with hidden depth;
both are intentional game-mechanics factors, not controlled dimension-only
causal estimates.

The next prototype should add axis-selective notes and a second tomographic
projection. That is a higher-information repair for the lost Prism Wyrm than
making every Pixie action stronger.
