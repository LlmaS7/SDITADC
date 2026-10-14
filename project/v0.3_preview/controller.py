"""One authoritative simulation actor, shared by desktop and browser views.

Only the actor thread mutates the simulator. HTTP handlers read immutable JSON
snapshots and enqueue commands; planning never blocks reading/rendering state.
"""
from concurrent.futures import Future
from dataclasses import asdict
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic
import traceback
from uuid import uuid4
from ai.executor import BusinessExecutor

from config import DEFAULT_SEED, DEFAULT_MAP, OUTPUTS, VERSION, WAIT_WARNING, MAX_ROBOTS
from models import TASK_LABELS, ROBOT_LABELS
from persistence import load, save
from simulation import Simulation


class Controller:
    def __init__(self, seed=DEFAULT_SEED, paused=False, auto=False, scenario=None,
                 map_id=DEFAULT_MAP, robot_count=None):
        self.sim = load(scenario) if scenario else Simulation(seed, map_id=map_id, robot_count=robot_count)
        self.seed = self.sim.warehouse.seed
        self.sim.paused = paused
        if auto:
            self.sim.command("auto", enabled=True)
        self.speed = 2
        self.generation = 0
        self.run_id = uuid4().hex
        self.business = BusinessExecutor(self)
        self.revision = 0
        self.last_step = monotonic()
        self._planning = False
        self._lock = Lock()
        self._commands = Queue(maxsize=64)
        self._closed = Event()
        self._wake = Event()
        self._view = {}
        self._map = self._serialize_map()
        self._publish()
        self._thread = Thread(target=self._run, name="simulation-owner", daemon=True)

    def _serialize_map(self):
        w = self.sim.warehouse
        return {"id": w.map_id, "name": w.name, "seed": w.seed, "width": w.width, "height": w.height,
                "walls": sorted(w.walls), "starts": w.starts, "random_count": w.random_count,
                "start_pool": w.start_pool, "max_robots": w.max_robots, "default_robots": w.default_robots,
                "shelves": sorted(w.shelves), "obstacles": sorted(w.obstacles),
                "blocked": sorted(w.blocked), "pickups": w.pickups,
                "deliveries": w.deliveries, "parking": w.parking}

    def _publish(self):
        view = self.sim.snapshot()
        tasks = []
        for task in sorted(view.tasks.values(), key=lambda t: t.id):
            if task.status == "cancelled":
                continue
            value = asdict(task)
            value.update(label=TASK_LABELS[task.status],
                         pickup_number=view.warehouse.pickups.index(task.pickup) + 1,
                         delivery_number=view.warehouse.deliveries.index(task.delivery) + 1)
            tasks.append(value)
        robots = []
        for robot in view.robots:
            value = asdict(robot)
            value["label"] = ROBOT_LABELS[robot.phase]
            current = view.tasks.get(robot.task_id)
            value["urgent"] = current is not None and current.priority == 5
            robots.append(value)
        self.revision += 1
        data = {"version": VERSION, "generation": self.generation,
                "revision": self.revision, "tick": view.tick, "speed": self.speed,
                "paused": view.paused, "planning": self._planning, "auto": view.auto,
                "message": view.message, "replaying": view.replaying,
                "map": self._map, "robots": robots, "robot_count": len(robots), "tasks": tasks,
                "metrics": {**view.metrics, "visible_total": len(tasks)},
                "assignment": view.assignment, "wait_warning": WAIT_WARNING}
        with self._lock:
            self._view = data

    def state(self):
        with self._lock:
            return {**self._view, "seconds_since_step": monotonic() - self.last_step}

    def start(self):
        self._thread.start()

    def submit(self, operation, data=None):
        if self._closed.is_set():
            raise RuntimeError("仿真已关闭")
        future = Future()
        self._commands.put_nowait((operation, data or {}, future))
        self._wake.set()
        return future

    def stop(self, save_on_exit=True):
        if not self._thread.is_alive():
            return
        self.submit("_close", {"save": save_on_exit}).result(timeout=12)
        self._thread.join(timeout=2)

    def _plan(self):
        if not self.sim.dirty:
            return
        self._planning = True
        self._publish()
        try:
            self.sim.ensure_plan()
        finally:
            self._planning = False
            self._publish()

    @staticmethod
    def integer(data, key, low, high):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{key} 参数无效")
        return value

    def _execute(self, op, data):
        if op == "pause":
            if not isinstance(data.get("paused"), bool):
                raise ValueError("暂停参数无效")
            self.sim.command(op, paused=data["paused"])
        elif op == "step":
            self.sim.paused = False
            try:
                self._plan()
                self.sim.step()
                self.last_step = monotonic()
            finally:
                self.sim.paused = True
        elif op == "speed":
            speed = self.integer(data, "value", 1, 8)
            if speed not in (1, 2, 4, 8):
                raise ValueError("支持 1、2、4、8 倍速度")
            self.speed = speed
        elif op in ("priority", "cancel"):
            task_id = self.integer(data, "task_id", 1, 10**9)
            if task_id not in self.sim.tasks:
                raise ValueError("任务不存在")
            if op == "priority":
                self.sim.command(op, task_id=task_id,
                                 priority=self.integer(data, "priority", 1, 5))
            else:
                self.sim.command(op, task_id=task_id)
        elif op == "add":
            pickup = self.integer(data, "pickup", 1, len(self.sim.warehouse.pickups))
            delivery = self.integer(data, "delivery", 1, len(self.sim.warehouse.deliveries))
            self.sim.command(op, pickup=self.sim.warehouse.pickups[pickup - 1],
                             delivery=self.sim.warehouse.deliveries[delivery - 1],
                             priority=self.integer(data, "priority", 1, 5))
        elif op == "auto":
            if not isinstance(data.get("enabled"), bool):
                raise ValueError("自动任务开关无效")
            self.sim.command(op, enabled=data["enabled"])
        elif op in ("random", "retry"):
            self.sim.command(op)
        elif op == "save":
            save(self.sim)
            self.sim.message = "已保存场景和运行报告到本版本 outputs/"
        elif op in ("reset", "load"):
            if op == "reset":
                seed = self.integer(data, "seed", 0, 2**31 - 1) if "seed" in data else self.seed
                map_id = data.get("map_id", self.sim.warehouse.map_id)
                count = self.integer(data, "robot_count", 1, MAX_ROBOTS) if "robot_count" in data else len(self.sim.robots)
                replacement = Simulation(seed, map_id=map_id, robot_count=count)
                self.sim = replacement
                self.seed = seed
                self.sim.message = f"已应用{self.sim.warehouse.name} · {len(self.sim.robots)} 台机器人，点击继续开始"
            else:
                self.sim = load()
                self.seed = self.sim.warehouse.seed
            self.sim.paused = True
            self.generation += 1
            self.last_step = monotonic()
            self._map = self._serialize_map()
        elif op == "_close":
            if data.get("save"):
                save(self.sim)
            self._closed.set()
            return
        else:
            raise ValueError("不支持的操作")
        self._publish()
        self._plan()
        self.sim.assert_invariants()

    def _run(self):
        try:
            self._plan()
        except Exception as exc:
            self._error(exc)
        next_step = monotonic() + 1 / self.speed
        while not self._closed.is_set():
            self._wake.wait(timeout=max(0, min(.1, next_step - monotonic())))
            self._wake.clear()
            handled = False
            while not self._closed.is_set():
                try:
                    operation, data, future = self._commands.get_nowait()
                except Empty:
                    break
                handled = True
                try:
                    if operation == "_ai_business":
                        future.set_result(self.business.run(data))
                    else:
                        self._execute(operation, data)
                        future.set_result(self.state())
                except (ValueError, KeyError) as exc:
                    future.set_exception(ValueError(str(exc)))
                except Exception as exc:
                    self._error(exc)
                    future.set_exception(exc)
            if handled:
                next_step = monotonic() + 1 / self.speed
            if self._closed.is_set():
                break
            if monotonic() >= next_step:
                if not self.sim.paused:
                    try:
                        self._plan()
                        if self.sim.step():
                            self.last_step = monotonic()
                        self._publish()
                    except Exception as exc:
                        self._error(exc)
                next_step = monotonic() + 1 / self.speed

    def _error(self, exc):
        self.sim.paused = True
        self._planning = False
        self.sim.message = f"已安全暂停：{exc}"
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        (OUTPUTS / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        self._publish()

