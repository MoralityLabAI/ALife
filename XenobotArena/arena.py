"""Xenobot-inspired, dimensionless active-disk sandbox. Python 3.10+, stdlib only.

This is a phenomenological ALife model, not a calibrated biological simulator.
All particles are inert, population sizes are fixed, and internal states are
explicitly planted rules. No culture, genetic, or fabrication model is included.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
from typing import Any

VERSION = "0.1.0"
SCENARIOS = ("open", "obstacles", "debris", "recorder", "memory", "recovery")
MODES = ("passive", "persistent", "orbit", "mixed")
RADIUS, BEAD_RADIUS, DT = 0.8, 0.3, 0.1


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    scenario: str = "debris"
    mode: str = "mixed"
    seed: int = 7
    steps: int = 300
    bots: int = 12
    beads: int = 40
    width: float = 60.0
    height: float = 40.0
    noise: float = 0.35
    memory: bool = True
    stimulus: bool = True
    repair: bool = True

    def validate(self) -> None:
        if self.scenario not in SCENARIOS or self.mode not in MODES:
            raise ValueError("unknown scenario or motion mode")
        for name, low, high in (("steps", 1, 4000), ("bots", 1, 48), ("beads", 0, 192)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("seed must be an integer in [0, 2**32)")
        for name in ("width", "height"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 20 <= value <= 100:
                raise ValueError(f"{name} must be finite and in [20, 100]")
        if not math.isfinite(self.noise) or not 0 <= self.noise <= 2:
            raise ValueError("noise must be finite and in [0, 2]")
        for name in ("memory", "stimulus", "repair"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be Boolean")
        size = self.bots + (self.beads if self.scenario == "debris" else 0)
        if self.steps * size * size > 25_000_000:
            raise ValueError("pair-work budget exceeded; reduce steps or population")


@dataclass
class Body:
    x: float
    y: float
    angle: float
    spin: float
    memory: float = 0.0
    recorder: bool = False
    integrity: float = 1.0
    path: float = 0.0


class Arena:
    """reset(seed), observe(), step(actions): bounded, model-agnostic control API.

    Actions map integer bot IDs to (throttle in [0,1], turn in [-1,1]).
    They represent an external digital controller, not a biological interface.
    Observations expose locations and headings; internal memory stays in logs.
    """

    def __init__(self, config: Config = Config()):
        config.validate()
        self.config = config
        self.reset()

    def reset(self, seed: int | None = None) -> dict:
        if seed is not None:
            self.config = replace(self.config, seed=seed)
            self.config.validate()
        c = self.config
        self.tick = 0
        self.events: list[dict] = []
        self.contacts = 0
        self.rng = random.Random(c.seed ^ 0x5391)
        init = random.Random(c.seed)
        self.obstacles = ([(c.width * .5, c.height * .32, 3.0),
                           (c.width * .5, c.height * .68, 3.0)]
                          if c.scenario == "obstacles" else [])
        self.bodies: list[Body] = []
        self.beads: list[list[float]] = []
        occupied: list[tuple[float, float, float]] = []
        for i in range(c.bots):
            x, y = self._spawn(init, RADIUS, occupied)
            angle = init.uniform(-math.pi, math.pi)
            spin = .65 if c.mode == "orbit" or (c.mode == "mixed" and i % 2) else 0.0
            spin *= 1 if i % 4 < 2 else -1
            self.bodies.append(Body(x, y, angle, spin))
            occupied.append((x, y, RADIUS))
        for _ in range(c.beads if c.scenario == "debris" else 0):
            x, y = self._spawn(init, BEAD_RADIUS, occupied)
            self.beads.append([x, y])
            occupied.append((x, y, BEAD_RADIUS))
        self.origins = [(b.x, b.y) for b in self.bodies]
        self.initial_beads = [p[:] for p in self.beads]
        self.visited: set[tuple[int, int]] = set()
        self._visit()
        return self.observe()

    def _spawn(self, rng, radius, occupied):
        c = self.config
        for _ in range(10000):
            x = rng.uniform(radius + .1, c.width - radius - .1)
            y = rng.uniform(radius + .1, c.height - radius - .1)
            if all(math.hypot(x - a, y - b) > radius + r + .05
                   for a, b, r in occupied + self.obstacles):
                return x, y
        raise ValueError("cannot place nonoverlapping population; reduce counts")

    def _project(self, x, y, radius):
        c = self.config
        return min(c.width-radius, max(radius, x)), min(c.height-radius, max(radius, y))

    def _visit(self):
        for b in self.bodies:
            self.visited.add((min(19, int(20*b.x/self.config.width)),
                              min(19, int(20*b.y/self.config.height))))

    def observe(self) -> dict:
        return {"tick": self.tick, "bots": [[b.x, b.y, b.angle] for b in self.bodies],
                "beads": [p[:] for p in self.beads], "obstacles": list(self.obstacles)}

    def snapshot(self) -> dict:
        return {"tick": self.tick, "bots": [asdict(b) for b in self.bodies],
                "beads": [p[:] for p in self.beads]}

    def state_hash(self) -> str:
        # RNG state and coverage are included: equal positions alone do not imply replay identity.
        return digest({"config": asdict(self.config), "state": self.snapshot(),
                       "rng": self.rng.getstate(), "visited": sorted(self.visited),
                       "contacts": self.contacts, "events": self.events})

    def _validate_actions(self, actions):
        result = {}
        if actions is None:
            return result
        if not isinstance(actions, dict):
            raise ValueError("actions must map bot IDs to (throttle, turn)")
        for i, pair in actions.items():
            if type(i) is not int or not 0 <= i < len(self.bodies):
                raise ValueError("unknown bot ID")
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("action needs throttle and turn")
            a, b = pair
            if (type(a) not in (int, float) or type(b) not in (int, float)
                    or not math.isfinite(a) or not math.isfinite(b)
                    or not 0 <= a <= 1 or not -1 <= b <= 1):
                raise ValueError("action outside finite bounds")
            result[i] = (a, b)
        return result

    def step(self, actions: dict | None = None) -> tuple[dict, dict, bool]:
        controls = self._validate_actions(actions)  # Atomic validation before RNG/state changes.
        if self.tick >= self.config.steps:
            raise RuntimeError("episode finished; call reset")
        c = self.config
        before = [(b.x, b.y) for b in self.bodies]
        pulse = c.stimulus and c.scenario == "memory" and 30 <= self.tick < 50
        if c.scenario == "recovery" and self.tick == 40:
            for b in self.bodies:
                b.integrity = .25
            self.events.append({"tick": self.tick, "kind": "planted_integrity_drop"})
        if c.scenario == "memory" and self.tick in (30, 50) and c.stimulus:
            self.events.append({"tick": self.tick, "kind": "pulse_on" if self.tick == 30 else "pulse_off"})
        for i, b in enumerate(self.bodies):
            # A draw per bot per tick is consumed in every arm for common random numbers.
            rotation_noise = self.rng.gauss(0, 1)
            if c.memory:
                b.memory = .96*b.memory + .04*float(pulse)
            else:
                b.memory = 0.0
            in_strip = .43*c.width <= b.x <= .57*c.width
            if c.scenario == "recorder" and c.stimulus and in_strip:
                b.recorder = True
            if c.scenario == "recovery" and c.repair and self.tick > 40:
                b.integrity += .025*(1-b.integrity)
            throttle, turn = controls.get(i, (1.0, 0.0))
            b.angle += (b.spin + turn)*DT + c.noise*math.sqrt(DT)*rotation_noise
            b.angle = (b.angle + math.pi) % (2*math.pi) - math.pi
            # Explicit toy response, not a fitted acoustic or biochemical mechanism.
            speed = (0.0 if c.mode == "passive" else 1.5)*throttle*b.integrity
            speed *= max(.1, 1-.45*float(pulse)-.3*b.memory)
            x, y = b.x + DT*speed*math.cos(b.angle), b.y + DT*speed*math.sin(b.angle)
            nx, ny = self._project(x, y, RADIUS)
            if nx != x:
                b.angle = math.pi-b.angle
                self.contacts += 1
            if ny != y:
                b.angle = -b.angle
                self.contacts += 1
            b.x, b.y = nx, ny
        # Bounded positional contact solver. Residual penetration is reported.
        for _ in range(4):
            for i, a in enumerate(self.bodies):
                for b in self.bodies[i+1:]:
                    dx, dy = b.x-a.x, b.y-a.y
                    d = math.hypot(dx, dy)
                    if d < 2*RADIUS:
                        ux, uy = (dx/d, dy/d) if d > 1e-12 else (1., 0.)
                        correction = (2*RADIUS-d)/2
                        a.x -= correction*ux
                        a.y -= correction*uy
                        b.x += correction*ux
                        b.y += correction*uy
                        self.contacts += 1
                for p in self.beads:
                    dx, dy = p[0]-a.x, p[1]-a.y
                    d = math.hypot(dx, dy)
                    if d < RADIUS+BEAD_RADIUS:
                        ux, uy = (dx/d, dy/d) if d > 1e-12 else (1., 0.)
                        correction = RADIUS+BEAD_RADIUS-d
                        a.x -= .1*correction*ux
                        a.y -= .1*correction*uy
                        p[0] += .9*correction*ux
                        p[1] += .9*correction*uy
                        self.contacts += 1
            for i, p in enumerate(self.beads):
                for q in self.beads[i+1:]:
                    dx, dy = q[0]-p[0], q[1]-p[1]
                    d = math.hypot(dx, dy)
                    if d < 2*BEAD_RADIUS:
                        ux, uy = (dx/d, dy/d) if d > 1e-12 else (1., 0.)
                        correction = (2*BEAD_RADIUS-d)/2
                        p[0] -= correction*ux
                        p[1] -= correction*uy
                        q[0] += correction*ux
                        q[1] += correction*uy
            for b in self.bodies:
                for x, y, radius in self.obstacles:
                    dx, dy = b.x-x, b.y-y
                    d = math.hypot(dx, dy)
                    if d < radius+RADIUS:
                        ux, uy = (dx/d, dy/d) if d > 1e-12 else (1., 0.)
                        b.x, b.y = x+(radius+RADIUS)*ux, y+(radius+RADIUS)*uy
                        vx, vy = math.cos(b.angle), math.sin(b.angle)
                        dot = vx*ux+vy*uy
                        if dot < 0:
                            b.angle = math.atan2(vy-2*dot*uy, vx-2*dot*ux)
                        self.contacts += 1
                b.x, b.y = self._project(b.x, b.y, RADIUS)
            for p in self.beads:
                p[:] = self._project(p[0], p[1], BEAD_RADIUS)
        for b, (x, y) in zip(self.bodies, before):
            b.path += math.hypot(b.x-x, b.y-y)
        self.tick += 1
        self._visit()
        return self.observe(), {"events": [e for e in self.events if e["tick"] == self.tick-1]}, self.tick >= c.steps

    def metrics(self) -> dict:
        c = self.config
        parents = list(range(len(self.beads)))
        def root(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]
                i = parents[i]
            return i
        for i, p in enumerate(self.beads):
            for j in range(i+1, len(self.beads)):
                if math.dist(p, self.beads[j]) <= 2*BEAD_RADIUS+.1:
                    parents[root(j)] = root(i)
        sizes: dict[int, int] = {}
        for i in range(len(parents)):
            r = root(i)
            sizes[r] = sizes.get(r, 0)+1
        all_disks = [(b.x, b.y, RADIUS) for b in self.bodies]
        all_disks += [(p[0], p[1], BEAD_RADIUS) for p in self.beads]
        overlap = max((max(0., a[2]+b[2]-math.dist(a[:2], b[:2]))
                       for i, a in enumerate(all_disks) for b in all_disks[i+1:]), default=0.)
        return {"coverage_fraction_20x20": len(self.visited)/400,
                "mean_path": statistics.fmean(b.path for b in self.bodies),
                "mean_displacement": statistics.fmean(math.dist((b.x,b.y), p) for b,p in zip(self.bodies,self.origins)),
                "bead_displacement": statistics.fmean(math.dist(p,q) for p,q in zip(self.beads,self.initial_beads)) if self.beads else 0.,
                "largest_bead_cluster_fraction": max(sizes.values(), default=0)/len(self.beads) if self.beads else 0.,
                "recorded_fraction": statistics.fmean(b.recorder for b in self.bodies),
                "mean_memory": statistics.fmean(b.memory for b in self.bodies),
                "mean_integrity": statistics.fmean(b.integrity for b in self.bodies),
                "contact_solver_corrections": self.contacts,
                "max_residual_overlap": overlap, "bot_count": len(self.bodies), "bead_count": len(self.beads)}


def run(config: Config, stride: int = 5) -> dict:
    if type(stride) is not int or stride < 1:
        raise ValueError("stride must be positive")
    env = Arena(config)
    frames = [env.snapshot()]
    initial = env.metrics()
    # At most 1002 frames including endpoints.
    stride = max(stride, math.ceil(config.steps/1000))
    for _ in range(config.steps):
        env.step()
        if env.tick % stride == 0 or env.tick == config.steps:
            frames.append(env.snapshot())
    return {"schema": "xenobotarena.episode.v1", "version": VERSION,
            "fidelity": "uncalibrated_dimensionless_active_disks", "config": asdict(config),
            "config_sha256": digest(asdict(config)), "python": platform.python_version(),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "frame_stride": stride, "obstacles": env.obstacles, "initial_metrics": initial, "metrics": env.metrics(),
            "state_sha256": env.state_hash(), "events": env.events, "frames": frames}


def verify(record: dict) -> bool:
    """Replay autonomous episodes. External-action traces need a separate action log."""
    c = Config(**record["config"])
    if digest(asdict(c)) != record["config_sha256"]:
        return False
    fresh = run(c, stride=record["frame_stride"])
    fields = ("schema", "version", "fidelity", "config", "config_sha256", "code_sha256",
              "frame_stride", "obstacles", "initial_metrics", "metrics", "state_sha256", "events", "frames")
    return all(canonical(fresh[k]) == canonical(record[k]) for k in fields)


def campaign(steps: int = 180, seeds: tuple[int, ...] = (11, 23, 47)) -> dict:
    """Fixed matched-seed diagnostic suite; neither selection nor biological validation."""
    if not 1 <= steps <= 500 or not 1 <= len(seeds) <= 8 or len(set(seeds)) != len(seeds):
        raise ValueError("campaign bound: 1..500 steps, 1..8 distinct seeds")
    rows = []
    for scenario in SCENARIOS:
        for mode in ("passive", "persistent", "orbit", "mixed"):
            for seed in seeds:
                r = run(Config(scenario=scenario, mode=mode, seed=seed, steps=steps), stride=steps)
                rows.append({"scenario": scenario, "mode": mode, "seed": seed,
                             "metrics": r["metrics"], "state_sha256": r["state_sha256"]})
    contrasts = []
    for scenario, field, metric in (("memory", "memory", "mean_path"),
                                     ("recovery", "repair", "mean_integrity")):
        diffs = []
        for seed in seeds:
            c = Config(scenario=scenario, seed=seed, steps=steps)
            treated = run(c, stride=steps)
            control = run(replace(c, **{field: False}), stride=steps)
            delta = treated["metrics"][metric]-control["metrics"][metric]
            diffs.append(delta)
            contrasts.append({"scenario": scenario, "seed": seed, "ablated_rule": field,
                              "metric": metric, "treated": treated["metrics"][metric],
                              "control": control["metrics"][metric], "delta": delta})
    return {"schema": "xenobotarena.campaign.v1", "steps": steps, "seeds": list(seeds),
            "interpretation": "descriptive model diagnostics; effects of planted rules",
            "rows": rows, "paired_ablations": contrasts}


def write_html(record: dict, path: Path) -> None:
    template = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
    path.write_text(template.replace("__EPISODE_JSON__", canonical(record).replace("<", "\\u003c")), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scenario", choices=SCENARIOS, default="debris")
    p.add_argument("--mode", choices=MODES, default="mixed")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--bots", type=int, default=12)
    p.add_argument("--beads", type=int, default=40)
    p.add_argument("--output", type=Path, default=Path("XenobotArena/results"))
    p.add_argument("--campaign", action="store_true")
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    try:
        if args.verify:
            ok = verify(json.loads(args.verify.read_text(encoding="utf-8")))
            print(canonical({"replay_verified": ok}))
            raise SystemExit(0 if ok else 1)
        if args.campaign:
            record = campaign(steps=args.steps)
            filename = "campaign.json"
        else:
            record = run(Config(scenario=args.scenario, mode=args.mode, seed=args.seed,
                                steps=args.steps, bots=args.bots, beads=args.beads))
            filename = "episode.json"
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/filename).write_text(json.dumps(record, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        if not args.campaign:
            write_html(record, args.output/"replay.html")
        print(canonical({"output": str(args.output/filename),
                         "episodes": len(record["rows"])+2*len(record["paired_ablations"]) if args.campaign else 1,
                         "metrics": record.get("metrics")}))
    except (ValueError, OSError, KeyError, TypeError) as error:
        p.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
