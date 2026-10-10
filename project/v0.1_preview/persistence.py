"""Portable input-event replay and reports, always under this version directory."""
import json
from dataclasses import asdict
from datetime import datetime
from config import OUTPUTS, ROOT
from simulation import Simulation


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def save(sim):
    scenario = {"version": "0.1_preview", "seed": sim.warehouse.seed,
                "events": sim.events + sim.replay_events}
    write_json(OUTPUTS / "last_scenario.json", scenario)
    view = sim.snapshot()
    report = {"saved_at": datetime.now().astimezone().isoformat(), "tick": sim.tick,
              "seed": sim.warehouse.seed, "metrics": view.metrics,
              "assignment": sim.assignment, "tasks": [asdict(t) for t in sim.tasks.values()],
              "robots": [asdict(r) for r in sim.robots], "frames": sim.frames,
              "events": sim.events}
    write_json(OUTPUTS / "last_run.json", report)
    return OUTPUTS / "last_scenario.json"


def load(path=None):
    path = path or (OUTPUTS / "last_scenario.json")
    if not path.exists():
        path = ROOT / "scenarios" / "ordinary.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != "0.1_preview":
        raise ValueError("场景版本不匹配")
    sim = Simulation(int(data["seed"]), initial_tasks=0)
    events = data.get("events", [])
    if any(not isinstance(e.get("tick"), int) or e["tick"] < 0 for e in events):
        raise ValueError("场景事件时间无效")
    if any(e.get("operation") not in ("add", "priority", "cancel", "auto") for e in events):
        raise ValueError("场景包含不支持的操作")
    sim.replay_events = sorted(events, key=lambda e: e["tick"])
    sim.replaying = True
    sim.apply_replay_events()
    sim.message = "已加载场景输入回放 · 新的手动操作将转为交互运行"
    return sim
