"""Deterministic, offline checks of the toy model and its evidence contract."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim import Config, Tissue, campaign, dice, mask, run, topology, verify, viewer


class XenobotsTest(unittest.TestCase):
    def short(self, **kwargs):
        params = dict(size=17, steps=150, cue_off_tick=42, wound_tick=95, sample_every=30)
        params.update(kwargs)
        return Config(**params)

    def test_deterministic(self):
        self.assertEqual(run(self.short()), run(self.short()))

    def test_seed_is_sensitive(self):
        self.assertNotEqual(run(self.short(seed=3))['result_sha256'],
                            run(self.short(seed=4))['result_sha256'])

    def test_manifest_has_model_hash(self):
        self.assertEqual(len(run(self.short())['model_sha256']), 64)

    def test_verify_roundtrip(self):
        self.assertTrue(verify(json.loads(json.dumps(run(self.short())))))

    def test_verify_rejects_tamper(self):
        rec = run(self.short())
        rec['final']['dice'] = -1
        self.assertFalse(verify(rec))

    def test_verify_rejects_unknown_schema(self):
        rec = run(self.short())
        rec['schema'] = 'untrusted.v2'
        self.assertFalse(verify(rec))

    def test_verify_rejects_malformed_config(self):
        rec = run(self.short())
        rec['config']['size'] = 10000
        self.assertFalse(verify(rec))

    def test_targets_are_distinct(self):
        shapes = [mask(25, name) for name in ('plus','ring','two_lobes')]
        self.assertEqual(len(set(shapes)), 3)

    def test_targets_are_nonempty_and_not_full(self):
        for name in ('plus','ring','two_lobes'):
            m = mask(25, name)
            self.assertGreater(sum(m), 0)
            self.assertLess(sum(m), len(m))

    def test_dice_bounds(self):
        for name in ('plus','ring','two_lobes'):
            m = mask(17, name)
            self.assertEqual(dice(m,m), 1)
            self.assertEqual(dice([False]*len(m),m), 0)

    def test_no_channel_has_no_edges(self):
        self.assertEqual(sum(map(len, topology(17, 'none', 4))), 0)

    def test_graphs_are_undirected_and_no_self_loops(self):
        for t in ('intact','split','rewired','none'):
            g = topology(17,t,3)
            for i,adj in enumerate(g):
                self.assertNotIn(i,adj)
                for j in adj:
                    self.assertIn(i,g[j])

    def test_rewired_differs(self):
        self.assertNotEqual(topology(17,'intact',3), topology(17,'rewired',3))

    def test_split_removes_midline_bridges(self):
        n = 17
        g = topology(n,'split',3)
        for i, adj in enumerate(g):
            for j in adj:
                self.assertFalse(i%n==n//2-1 and j%n==n//2)

    def test_memory_control_causal_effect(self):
        a=run(self.short(retain_memory=True))
        b=run(self.short(retain_memory=False))
        self.assertGreater(a['final']['dice'],b['final']['dice']+.15)

    def test_gap_channel_causal_effect(self):
        a=run(self.short())
        b=run(self.short(topology='none'))
        self.assertGreater(a['final']['dice'],b['final']['dice']+.15)

    def test_wound_occurs_and_recovery(self):
        r=run(self.short())
        self.assertGreater(r['wound']['count'],0)
        self.assertLess(r['wound']['post_dice'],r['wound']['pre_dice'])
        self.assertGreater(r['final']['dice'],r['wound']['post_dice'])
        self.assertIsInstance(r['wound']['recovery_latency_steps'], int)

    def test_no_wound(self):
        r=run(self.short(wound_tick=None))
        self.assertEqual(r['events'][-1]['event'],'cue_withdrawal')
        self.assertIsNone(r['wound']['recovery_fraction'])

    def test_no_lesion_means_no_direct_effect(self):
        a=run(self.short(wound_tick=None))
        b=run(self.short(wound_tick=95))
        self.assertEqual(a['final']['dice'],b['final']['dice'])

    def test_goal_rewrite_is_reported(self):
        r=run(self.short(next_target='ring',switch_tick=60))
        self.assertEqual(r['final']['goal'],'ring')
        self.assertEqual([e['event'] for e in r['events']],
                         ['cue_withdrawal','program_switch','wound'])

    def test_goal_rewrite_moves_toward_new_goal(self):
        a=run(self.short(next_target='ring',switch_tick=60))
        b=run(self.short())
        self.assertGreater(a['final']['dice'], .3)
        self.assertNotEqual(a['final']['goal'],b['final']['goal'])

    def test_competing_organizer_programs(self):
        a=Tissue(self.short())
        b=Tissue(self.short(rival_target='ring'))
        self.assertNotEqual(a.anchor, b.anchor)
        self.assertEqual(a.organizers, b.organizers)
        r=run(self.short(rival_target='ring'))
        self.assertIsNotNone(r['final']['rival_dice'])
        self.assertEqual(r['final']['rival'], 'ring')

    def test_program_only_changes_anchors(self):
        t=Tissue(self.short())
        v=t.voltage[:]
        t.set_program('ring')
        self.assertEqual(v,t.voltage)

    def test_frames_capture_event_ticks(self):
        r=run(self.short(next_target='ring',switch_tick=60))
        ticks={f['tick'] for f in r['frames']}
        self.assertTrue({0,42,60,95,150}<=ticks)

    def test_viewer_standalone(self):
        html=viewer(run(self.short()))
        self.assertIn('<canvas',html)
        self.assertIn('frames=',html)
        self.assertNotIn('src="http',html)

    def test_input_validation(self):
        for fields in (dict(size=100), dict(noise=float('nan')),
                       dict(next_target='ring'), dict(switch_tick=6),
                       dict(rival_target='caterpillar'),
                       dict(retain_memory='yes'),dict(topology='worm'),
                       dict(cue_off_tick=1000),dict(seed=-1)):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                Config(**fields).validate()

    def test_input_does_not_read_global_target_in_actuator(self):
        t=Tissue(self.short())
        # Rewriting the target program does not immediately rewrite all fates.
        initial=t.fate[:]
        t.set_program('two_lobes')
        self.assertEqual(t.fate,initial)

    def test_campaign_bounded(self):
        r=campaign(seeds=(11,),size=17,steps=150)
        self.assertEqual(len(r['rows']),7)
        self.assertEqual(len(r['paired']),4)
        self.assertEqual(r['schema'],'alife.xenobots.campaign.v1')

    def test_campaign_duplicate_seed_rejected(self):
        with self.assertRaises(ValueError):
            campaign(seeds=(1,1),size=17,steps=150)

    def test_canonical_json_roundtrip(self):
        r=run(self.short())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'record.json'
            p.write_text(json.dumps(r),encoding='utf-8')
            self.assertTrue(verify(json.loads(p.read_text(encoding='utf-8'))))


if __name__ == '__main__':
    unittest.main()
