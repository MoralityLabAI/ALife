# Agent mechinterp harness

This package instruments an agent decision without assigning mental-state or
cognition semantics to it. A decision record binds a deterministic observation,
named activation layers, ordered logits, selected output, and hashes. The v1
campaign uses a fixed NumPy canary whose first three hidden units encode critter
identity by construction; it exists to prove that capture, probes, ablations,
patches, and tamper detection are wired correctly.

The editor path has a separate structural firewall:

1. The policy proposes one typed action.
2. The action resolves to one critter-specific, allowlisted scalar.
3. Bounds, maximum delta, integer constraints, target identity, and immutable
   parent-profile hash are checked.
4. A copied profile is changed and an exact one-path receipt is emitted.
5. The edited episode is replayed and response hazards determine promotion.

Identity-probe accuracy, activation attribution, patching, representation drift,
complexity, delight, and response diversity are never authorization gates. The
public capture schema can wrap a learned agent later, but canary results cannot be
transferred into claims about that learned model.

Run and verify:

```powershell
python src\run_agent_mechinterp_campaign.py --manifest experiments\agent_mechinterp_harness_v1\manifest.json --output results\agent_mechinterp_harness_v1
python src\verify_agent_mechinterp_artifacts.py results\agent_mechinterp_harness_v1 --portable --replay-samples 6
```

Primary APIs are exported by `agent_mechinterp`: `capture_decision`,
`verify_decision`, `authorize_edit`, `apply_authorized_edit`,
`verify_edit_receipt`, `verify_harness_row`, and `analyze_decisions`.
