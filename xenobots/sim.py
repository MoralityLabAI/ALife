"""Xenobot-inspired pattern regulation on a cellular lattice.

This is a dimensionless, deliberately planted morphogenetic-memory surrogate,
not a biological xenobot, electrophysiology, tissue, or movement model.
Standard-library Python 3.10+; see README.md for evidence boundaries.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

VERSION = "0.1.0"
TARGETS = ("plus", "ring", "two_lobes")
TOPOLOGIES = ("intact", "split", "rewired", "none")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def model_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Config:
    size: int = 25
    steps: int = 220
    seed: int = 7
    target: str = "plus"
    next_target: str | None = None
    rival_target: str | None = None
    switch_tick: int | None = None
    cue_off_tick: int = 65
    wound_tick: int | None = 120
    topology: str = "intact"
    retain_memory: bool = True
    gap_strength: float = 0.60
    leak: float = 0.014
    fate_rate: float = 0.16
    noise: float = 0.008
    organizer_spacing: int = 3
    sample_every: int = 10

    def validate(self) -> None:
        for name, lo, hi in (("size", 13, 41), ("steps", 20, 600),
                             ("seed", 0, 2**32 - 1), ("organizer_spacing", 2, 8),
                             ("sample_every", 1, 100)):
            v = getattr(self, name)
            if type(v) is not int or not lo <= v <= hi:
                raise ValueError(f"{name}: expected integer in [{lo},{hi}]")
        if self.target not in TARGETS or (self.next_target is not None and self.next_target not in TARGETS):
            raise ValueError("unknown target")
        if self.rival_target is not None and self.rival_target not in TARGETS:
            raise ValueError("unknown rival target")
        if self.topology not in TOPOLOGIES:
            raise ValueError("unknown topology")
        if type(self.retain_memory) is not bool:
            raise ValueError("retain_memory must be Boolean")
        if type(self.cue_off_tick) is not int or not 1 <= self.cue_off_tick < self.steps:
            raise ValueError("cue_off_tick must be inside the episode")
        if self.next_target is None and self.switch_tick is not None:
            raise ValueError("switch_tick requires next_target")
        if self.next_target is not None and (type(self.switch_tick) is not int or not 1 <= self.switch_tick < self.steps):
            raise ValueError("next_target requires in-range switch_tick")
        if self.wound_tick is not None and (type(self.wound_tick) is not int or not 1 <= self.wound_tick < self.steps):
            raise ValueError("wound_tick must be inside the episode")
        for name, lo, hi in (("gap_strength", 0, 1), ("leak", 0, .2),
                             ("fate_rate", 0, 1), ("noise", 0, .1)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError(f"{name}: expected finite [{lo},{hi}]")
        if self.steps * self.size * self.size > 1_000_000:
            raise ValueError("CPU work limit exceeded")


def mask(size: int, name: str) -> tuple[bool, ...]:
    """Only organizer encoding and scoring read this ground-truth shape."""
    c = (size - 1) / 2
    out = []
    for y in range(size):
        for x in range(size):
            dx, dy = (x - c) / size, (y - c) / size
            if name == "plus":
                present = ((abs(dx) < .075 and abs(dy) < .34) or
                           (abs(dy) < .075 and abs(dx) < .34))
            elif name == "ring":
                present = .22 < math.hypot(dx, dy) < .34
            elif name == "two_lobes":
                present = (math.hypot(dx + .18, dy) < .16 or
                           math.hypot(dx - .18, dy) < .16)
            else:
                raise ValueError(name)
            out.append(present)
    return tuple(out)


def topology(size: int, mode: str, seed: int) -> tuple[tuple[int, ...], ...]:
    """Frozen gap-junction graph. Degree/communication is an explicit intervention."""
    n = size * size
    edges: list[set[int]] = [set() for _ in range(n)]
    if mode == "none":
        return tuple(() for _ in range(n))
    rng = random.Random(seed ^ 0x41E11)
    for y in range(size):
        for x in range(size):
            a = y * size + x
            for dx, dy in ((1, 0), (0, 1)):
                xx, yy = x + dx, y + dy
                if xx >= size or yy >= size:
                    continue
                if mode == "split" and (x < size // 2 <= xx):
                    continue
                b = yy * size + xx
                edges[a].add(b)
                edges[b].add(a)
    if mode == "rewired":
        # Remove a fifth of local edges and replace each with one undirected
        # distant edge. This is a graph perturbation, not anatomical remodeling.
        local_edges = [(a, b) for a in range(n) for b in edges[a] if a < b]
        rng.shuffle(local_edges)
        for a, b in local_edges[:len(local_edges) // 5]:
            edges[a].discard(b)
            edges[b].discard(a)
            other = rng.randrange(n - 1)
            if other >= a:
                other += 1
            edges[a].add(other)
            edges[other].add(a)
    return tuple(tuple(sorted(e)) for e in edges)


def dice(pred: list[bool] | tuple[bool, ...], truth: tuple[bool, ...]) -> float:
    both = sum(a and b for a, b in zip(pred, truth))
    denominator = sum(pred) + sum(truth)
    return 2 * both / denominator if denominator else 1.0


def phenotype(voltage: list[float]) -> list[bool]:
    # Fate itself is tracked as a continuous state; this helper only diagnoses
    # the field threshold and is not the actuator's target oracle.
    return [v > .10 for v in voltage]


class Tissue:
    """Fixed scaffold of cells with local voltages and a binary fate readout.

    Sparse organizer sites carry an externally specified voltage program.
    All other cells update from neighboring voltages and local state alone.
    The fate actuator reads only its own voltage, with no access to the target.
    """

    def __init__(self, config: Config):
        config.validate()
        self.config = config
        self.rng = random.Random(config.seed)
        self.graph = topology(config.size, config.topology, config.seed)
        n = config.size * config.size
        self.voltage = [self.rng.uniform(-.015, .015) for _ in range(n)]
        self.fate = [0.0] * n
        self.organizers = tuple(i for i in range(n)
                                if (i // config.size) % config.organizer_spacing == 1
                                and (i % config.size) % config.organizer_spacing == 1)
        self.program = config.target
        self.anchor = [0.0] * n
        self.set_program(config.target)
        self.tick = 0
        self.events: list[dict] = []
        self.wound_cells: set[int] = set()
        self.wound_baseline: float | None = None
        self.wound_instant: float | None = None
        self.recovery_score: float | None = None

    def set_program(self, target: str) -> None:
        self.program = target
        truth = mask(self.config.size, target)
        rival = mask(self.config.size, self.config.rival_target) if self.config.rival_target else None
        for i in self.organizers:
            # Right-side organizers can carry a competing anatomical program.
            # The left/right boundary is imposed by the experimenter.
            program = rival if rival is not None and i % self.config.size >= self.config.size // 2 else truth
            self.anchor[i] = 1.0 if program[i] else -1.0

    def _lesion(self) -> int:
        size = self.config.size
        truth = mask(size, self.program)
        # Localized damage of selected differentiated cells; organizer
        # voltage memory and gap connections remain intact by construction.
        cx, cy = .64 * (size - 1), .49 * (size - 1)
        radius = .21 * size
        self.wound_cells = {i for i in range(size * size)
                            if truth[i]
                            and math.hypot(i % size - cx, i // size - cy) <= radius}
        self.wound_baseline = dice(self.shape(), truth)
        for i in self.wound_cells:
            self.fate[i] = 0.0
        self.wound_instant = dice(self.shape(), truth)
        return len(self.wound_cells)

    def shape(self) -> list[bool]:
        return [v >= .5 for v in self.fate]

    def metrics(self) -> dict:
        truth = mask(self.config.size, self.program)
        shape = self.shape()
        rival = mask(self.config.size, self.config.rival_target) if self.config.rival_target else None
        return {"tick": self.tick,
                "goal": self.program,
                "rival": self.config.rival_target,
                "rival_dice": round(dice(shape,rival),8) if rival is not None else None,
                "dice": round(dice(shape, truth), 8),
                "fate_positive": sum(shape),
                "goal_positive": sum(truth),
                "mean_abs_voltage": round(sum(map(abs, self.voltage)) / len(self.voltage), 8),
                "mean_fate": round(sum(self.fate) / len(self.fate), 8)}

    def frame(self) -> dict:
        size = self.config.size
        return {"tick": self.tick,
                "goal": self.program,
                "fate": "".join("1" if f >= .5 else "0" for f in self.fate),
                "voltage": [round(v, 3) for v in self.voltage],
                "organizers": list(self.organizers),
                "metrics": self.metrics()}

    def step(self) -> None:
        c = self.config
        t = self.tick + 1
        if t == c.switch_tick:
            assert c.next_target is not None
            self.set_program(c.next_target)
            self.events.append({"tick": t, "event": "program_switch", "target": self.program})
        # Before cue_off_tick, external stimulation clamps organizer voltage.
        # Afterwards only the explicitly planted retention rule does so.
        # A late target switch is another external programming intervention.
        clamp = t < c.cue_off_tick or c.retain_memory
        if t == c.cue_off_tick:
            self.events.append({"tick": t, "event": "cue_withdrawal"})
        old = self.voltage
        new: list[float] = []
        for i, v in enumerate(old):
            if i in self._organizer_set and clamp:
                new.append(self.anchor[i])
                # Fixed noise draw per site/tick across all matched interventions.
                self.rng.uniform(-c.noise, c.noise)
                continue
            adjacent = self.graph[i]
            neighbor = sum(old[j] for j in adjacent) / len(adjacent) if adjacent else v
            disturbance = self.rng.uniform(-c.noise, c.noise)
            new.append(max(-1.0, min(1.0, v + c.gap_strength * (neighbor-v)
                                      - c.leak*v + disturbance)))
        self.voltage = new
        # Local physiology -> phenotype, with no target lookup or coordinate.
        for i, v in enumerate(new):
            actuator = 1 / (1 + math.exp(-9 * (v - .10)))
            self.fate[i] += c.fate_rate * (actuator - self.fate[i])
        self.tick += 1
        if c.wound_tick is not None and self.tick == c.wound_tick:
            count = self._lesion()
            self.events.append({"tick": self.tick, "event": "wound", "affected": count})

    @property
    def _organizer_set(self) -> set[int]:
        # Kept as a property to preserve a simple inspectable state layout.
        if not hasattr(self, "_organizer_cache"):
            self._organizer_cache = set(self.organizers)
        return self._organizer_cache


def run(config: Config) -> dict:
    config.validate()
    tissue = Tissue(config)
    frames = [tissue.frame()]
    timeseries = [tissue.metrics()]
    for _ in range(config.steps):
        tissue.step()
        timeseries.append(tissue.metrics())
        if tissue.tick % config.sample_every == 0 or tissue.tick == config.steps or tissue.tick in {
            config.wound_tick, config.switch_tick, config.cue_off_tick}:
            frames.append(tissue.frame())
    truth = mask(config.size, tissue.program)
    last = tissue.metrics()
    recovery_latency = None
    if tissue.wound_baseline is not None and tissue.wound_instant is not None:
        # Fraction of lost pre-wound Dice recovered; can be negative or >1.
        lost = tissue.wound_baseline - tissue.wound_instant
        tissue.recovery_score = ((last["dice"] - tissue.wound_instant) / lost
                                 if lost > 1e-12 else None)
        if lost > .02:
            recovery_latency = next((row["tick"] - config.wound_tick
                                     for row in timeseries if row["tick"] > config.wound_tick
                                     and row["dice"] >= tissue.wound_baseline - .02), None)
    result = {"schema": "alife.xenobots.pattern.v1",
              "model_sha256": model_sha(),
              "config": asdict(config),
              "organizers": list(tissue.organizers),
              "edges": sum(map(len, tissue.graph)) // 2,
              "events": tissue.events,
              "final": last,
              "wound": {"count": len(tissue.wound_cells),
                        "pre_dice": tissue.wound_baseline,
                        "post_dice": tissue.wound_instant,
                        "recovery_fraction": round(tissue.recovery_score, 8) if tissue.recovery_score is not None else None,
                        "recovery_latency_steps": recovery_latency},
              "timeseries": timeseries,
              "frames": frames}
    result["result_sha256"] = sha(result)
    return result


def verify(record: dict) -> bool:
    if record.get("schema") != "alife.xenobots.pattern.v1":
        return False
    claimed = record.get("result_sha256")
    unsigned = {k: v for k, v in record.items() if k != "result_sha256"}
    if sha(unsigned) != claimed or record.get("model_sha256") != model_sha():
        return False
    try:
        cfg = Config(**record["config"])
        return run(cfg) == record
    except (TypeError, ValueError, KeyError):
        return False


def viewer(record: dict) -> str:
    """Offline interactive fate/voltage replay, all input from a local record."""
    data = canonical({"frames": record["frames"], "size": record["config"]["size"],
                      "events": record["events"]}).replace("</", "<\\/")
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Xenobots: tissue memory toy model</title>
<style>body{font:15px system-ui,sans-serif;margin:2rem auto;max-width:850px;background:#101820;color:#e9f0f2}
canvas{width:min(100%,575px);image-rendering:pixelated;border:1px solid #5b7080}
input{width:min(100%,570px)}select{padding:.4rem}a{color:#a6dcfb}
small{color:#a2b5c0}pre{white-space:pre-wrap}</style>
<h1>Xenobots / pattern memory</h1>
<p><small>Planted voltage-organizer/fate model. Tissue shape and all parameters are dimensionless.</small></p>
<select id="mode"><option value="fate">Phenotype</option><option value="voltage">Voltage field</option></select>
<div><canvas id="plot"></canvas></div>
<input id="frame" type="range" min="0" value="0"><p id="status"></p>
<script>
const data=DATA_HERE, frames=data.frames, n=data.size, plot=document.querySelector('#plot');
plot.width=n;plot.height=n;const ctx=plot.getContext('2d');
const bar=document.querySelector('#frame'),mode=document.querySelector('#mode');bar.max=frames.length-1;
function draw(){const f=frames[+bar.value], pic=ctx.createImageData(n,n);
for(let i=0;i<n*n;i++){let rgb;
if(mode.value==='fate')rgb=f.fate[i]==='1'?[84,211,188]:[27,49,65];
else{const v=Math.max(-1,Math.min(1,f.voltage[i]));rgb=v>=0?[48+Math.round(190*v),55+Math.round(90*v),88]:[36,65+Math.round(80*(-v)),92+Math.round(160*(-v))];}
for(let k=0;k<3;k++)pic.data[i*4+k]=rgb[k];pic.data[i*4+3]=255;}
ctx.putImageData(pic,0,0);
document.querySelector('#status').textContent=`tick ${f.tick} | goal ${f.goal} | Dice ${f.metrics.dice} | rival ${f.metrics.rival_dice ?? "n/a"} | differentiated cells ${f.metrics.fate_positive}`;
}
bar.addEventListener('input',draw);mode.addEventListener('change',draw);draw();
</script></html>'''.replace("DATA_HERE", data)


def campaign(seeds: tuple[int, ...] = (11, 23, 47), size: int = 25,
             steps: int = 220) -> dict:
    """Common-random-number exploratory paired controls. Seeds are replicates."""
    if not 1 <= len(seeds) <= 12 or len(set(seeds)) != len(seeds):
        raise ValueError("1..12 distinct seeds required")
    rows = []
    for seed in seeds:
        base = dict(size=size, steps=steps, seed=seed, cue_off_tick=65,
                    wound_tick=120, sample_every=20)
        if steps <= 120:
            raise ValueError("campaign needs >120 steps")
        arms = {
            "retained_intact": Config(**base),
            "memory_ablated": Config(**base, retain_memory=False),
            "communication_ablated": Config(**base, topology="none"),
            "split_contact": Config(**base, topology="split"),
            "rewired_contact": Config(**base, topology="rewired"),
            "retarget_ring": Config(**base, next_target="ring", switch_tick=85),
            "competing_goals": Config(**base, rival_target="ring"),
        }
        for arm, cfg in arms.items():
            r = run(cfg)
            rows.append({"seed": seed, "arm": arm,
                         "final_dice": r["final"]["dice"],
                         "rival_dice": r["final"]["rival_dice"],
                         "recovery_fraction": r["wound"]["recovery_fraction"],
                         "recovery_latency_steps": r["wound"]["recovery_latency_steps"],
                         "edges": r["edges"],
                         "result_sha256": r["result_sha256"]})
    paired = []
    for seed in seeds:
        r = {row["arm"]: row for row in rows if row["seed"] == seed}
        for other in ("memory_ablated", "communication_ablated", "split_contact", "rewired_contact"):
            paired.append({"seed": seed, "comparison": f"retained_intact - {other}",
                           "dice_delta": round(r["retained_intact"]["final_dice"] - r[other]["final_dice"], 8)})
    report = {"schema": "alife.xenobots.campaign.v1", "model_sha256": model_sha(),
              "registration": "exploratory; protocol.md provides holdout plan",
              "seeds": list(seeds), "steps": steps, "size": size,
              "rows": rows, "paired": paired}
    report["result_sha256"] = sha(report)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", choices=TARGETS, default="plus")
    p.add_argument("--next-target", choices=TARGETS)
    p.add_argument("--rival-target", choices=TARGETS)
    p.add_argument("--switch-tick", type=int)
    p.add_argument("--topology", choices=TOPOLOGIES, default="intact")
    p.add_argument("--memory-off", action="store_true")
    p.add_argument("--wound-tick", type=int, default=120)
    p.add_argument("--cue-off", type=int, default=65)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--steps", type=int, default=220)
    p.add_argument("--size", type=int, default=25)
    p.add_argument("--output", default="xenobots/results")
    p.add_argument("--campaign", action="store_true")
    p.add_argument("--verify", metavar="EPISODE_JSON")
    args = p.parse_args(argv)
    if args.verify:
        ok = verify(json.loads(Path(args.verify).read_text(encoding="utf-8")))
        print("VERIFIED" if ok else "REPLAY MISMATCH")
        return 0 if ok else 1
    output = Path(args.output)
    if args.campaign:
        report = campaign(steps=args.steps, size=args.size)
        output.mkdir(parents=True, exist_ok=True)
        path = output / "campaign.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{len(report['rows'])} episodes, {len(report['paired'])} paired deltas: {path}")
        return 0
    cfg = Config(size=args.size, steps=args.steps, seed=args.seed, target=args.target,
                 next_target=args.next_target, rival_target=args.rival_target, switch_tick=args.switch_tick,
                 cue_off_tick=args.cue_off, wound_tick=args.wound_tick,
                 topology=args.topology, retain_memory=not args.memory_off)
    record = run(cfg)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "episode.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (output / "replay.html").write_text(viewer(record), encoding="utf-8")
    print(f"Dice {record['final']['dice']:.4f} | repair {record['wound']['recovery_fraction']} | {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
