import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena import Arena, Config, SCENARIOS, campaign, run, verify, write_html

class ArenaTests(unittest.TestCase):
    def test_deterministic(self):
        c=Config(steps=25)
        self.assertEqual(run(c),run(c))

    def test_seed_changes_state(self):
        self.assertNotEqual(Arena(Config(seed=1)).state_hash(),Arena(Config(seed=2)).state_hash())

    def test_population_conserved(self):
        a=Arena(Config(steps=80,bots=10,beads=20))
        for _ in range(80):
            a.step()
            self.assertEqual((len(a.bodies),len(a.beads)),(10,20))

    def test_passive_is_stationary(self):
        r=run(Config(mode="passive",steps=30))
        self.assertEqual(r["metrics"]["mean_path"],0)
        self.assertEqual(r["metrics"]["bead_displacement"],0)

    def test_active_moves(self):
        self.assertGreater(run(Config(scenario="open",steps=40))["metrics"]["mean_path"],1)

    def test_reset_replays(self):
        a=Arena(Config(steps=4));start=a.state_hash();a.step();a.reset()
        self.assertEqual(start,a.state_hash())

    def test_action_rejection_is_atomic(self):
        a=Arena();before=a.state_hash()
        for action in ({999:(1,0)},{0:(1,float('nan'))},{0:(2,0)},{0:[1]},[] ):
            with self.assertRaises(ValueError):a.step(action)
            self.assertEqual(before,a.state_hash())

    def test_zero_throttle(self):
        a=Arena(Config(scenario="open",bots=1,steps=20))
        for _ in range(20):a.step({0:(0,1)})
        self.assertEqual(a.metrics()["mean_path"],0)

    def test_termination(self):
        a=Arena(Config(steps=1));_,_,done=a.step();self.assertTrue(done)
        with self.assertRaises(RuntimeError):a.step()

    def test_finite_and_bounded(self):
        for scenario in SCENARIOS:
            a=Arena(Config(scenario=scenario,steps=60))
            for _ in range(60):a.step()
            for b in a.bodies:
                self.assertTrue(.8<=b.x<=a.config.width-.8)
                self.assertTrue(.8<=b.y<=a.config.height-.8)
            self.assertTrue(all(math.isfinite(v) for v in a.metrics().values()))

    def test_obstacles_exclude_bots(self):
        a=Arena(Config(scenario="obstacles",steps=160))
        for _ in range(160):
            a.step()
            for b in a.bodies:
                for x,y,r in a.obstacles:self.assertGreaterEqual(math.hypot(b.x-x,b.y-y),r+.8-1e-10)

    def test_bead_contact_moves_inert_particle(self):
        a=Arena(Config(bots=1,beads=1,steps=1,noise=0))
        b=a.bodies[0];b.x=10;b.y=10;b.angle=0;b.spin=0
        a.beads[0]=[11.1,10.];a.initial_beads=[[11.1,10.]]
        a.step();self.assertGreater(a.beads[0][0],11.1)
        self.assertEqual(len(a.beads),1)

    def test_recorder_does_not_change_motion(self):
        c=Config(scenario="recorder",steps=80)
        on,off=run(c),run(replace(c,stimulus=False))
        self.assertEqual(on["metrics"]["mean_path"],off["metrics"]["mean_path"])

    def test_recorder_latches(self):
        a=Arena(Config(scenario="recorder",bots=1,steps=2))
        a.bodies[0].x=.5*a.config.width;a.step();self.assertTrue(a.bodies[0].recorder)
        a.bodies[0].x=2;a.step();self.assertTrue(a.bodies[0].recorder)

    def test_memory_is_planted_and_persistent(self):
        c=Config(scenario="memory",steps=60)
        on,off=run(c),run(replace(c,memory=False))
        self.assertGreater(on["metrics"]["mean_memory"],0)
        self.assertEqual(off["metrics"]["mean_memory"],0)
        self.assertLess(on["metrics"]["mean_path"],off["metrics"]["mean_path"])

    def test_no_stimulus_no_memory(self):
        self.assertEqual(run(Config(scenario="memory",stimulus=False,steps=60))["metrics"]["mean_memory"],0)

    def test_recovery_ablation(self):
        c=Config(scenario="recovery",steps=100)
        self.assertGreater(run(c)["metrics"]["mean_integrity"],.25)
        self.assertEqual(run(replace(c,repair=False))["metrics"]["mean_integrity"],.25)

    def test_replay_serialized(self):
        self.assertTrue(verify(json.loads(json.dumps(run(Config(steps=20),stride=3)))))

    def test_tampered_frame_fails(self):
        r=run(Config(steps=5));r["frames"][0]["bots"][0]["x"]+=1
        self.assertFalse(verify(r))

    def test_invalid_config(self):
        for change in ({"steps":0},{"noise":float("inf")},{"bots":True},{"seed":-1},
                       {"scenario":"replication"},{"bots":48,"beads":192,"steps":4000}):
            with self.assertRaises(ValueError):Arena(replace(Config(),**change))

    def test_html_embeds_data(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"replay.html";write_html(run(Config(steps=1)),p)
            text=p.read_text();self.assertNotIn("__EPISODE_JSON__",text)
            self.assertIn("xenobotarena.episode.v1",text)

    def test_campaign_pair_counts(self):
        r=campaign(steps=2,seeds=(11,23))
        self.assertEqual(len(r["rows"]),48)
        self.assertEqual(len(r["paired_ablations"]),4)

if __name__=="__main__":unittest.main()
