"""Event-driven MAPD execution. This module owns all mutable domain state.

Planning covers the remaining current job, a reserved emergency job if any,
and distinct parking endpoints. UI commands are applied only at tick boundaries.
"""
from copy import deepcopy
from random import Random
from config import (DEFAULT_SEED, LOAD_TICKS, UNLOAD_TICKS, INITIAL_TASKS,
                    AUTO_INTERVAL, PLAN_SECONDS, PLAN_HORIZON, DEFAULT_MAP, FLEET_CBS_SECONDS)
from models import Robot, Task, Waypoint, View, FINISHED
from warehouse import Warehouse
from scheduler import Slot, exact_matching, completion_cost, optimal_parking
from planning.cbs import plan
from planning.prioritized import plan_reserved
from planning.validation import first_conflict


class Simulation:
    def __init__(self, seed=DEFAULT_SEED, initial_tasks=INITIAL_TASKS,
                 map_id=DEFAULT_MAP, map_definition=None, robot_count=None):
        self.warehouse = Warehouse(seed, map_id, map_definition, robot_count)
        self.rng = Random(seed ^ 0xA913)
        self.robots = [Robot(i + 1, p, p, p, path=[p])
                       for i, p in enumerate(self.warehouse.starts)]
        self.tasks = {}
        self.tick = 0
        self.paused = False
        self.auto = False
        self.message = "普通仓库场景 · 任务等待调度"
        self.events = []
        self.frames = []
        self.replay_events = []
        self.replaying = False
        self.next_id = 1
        self.dirty = True
        self.failed_attempts = 0
        self.last_progress = 0
        self.assignment = {}
        self.metrics = {"planning_seconds": 0.0, "last_plan_ms": 0.0,
                        "plans": 0, "cbs_nodes": 0, "preemptions": 0,
                        "collisions": 0, "recovery_attempts": 0,
                        "reservation_plans": 0, "planner": "CBS"}
        for _ in range(initial_tasks):
            self.random_task()

    def record(self, operation, **data):
        self.events.append({"tick": self.tick, "operation": operation, **data})

    def branch_replay(self):
        if self.replaying:
            self.replay_events.clear()
            self.replaying = False
            self.message = "已从场景回放切换为交互运行"

    def add_task(self, pickup, delivery, priority=1, task_id=None, record=True):
        pickup, delivery = tuple(pickup), tuple(delivery)
        if pickup not in self.warehouse.pickups or delivery not in self.warehouse.deliveries:
            raise ValueError("请选择货架作业点和配送作业点")
        if not 1 <= priority <= 5:
            raise ValueError("任务等级必须为 1～5")
        task_id = self.next_id if task_id is None else task_id
        if task_id in self.tasks:
            raise ValueError("任务编号重复")
        self.next_id = max(self.next_id, task_id + 1)
        self.tasks[task_id] = Task(task_id, pickup, delivery, priority, self.tick)
        if record:
            self.record("add", id=task_id, pickup=pickup, delivery=delivery, priority=priority)
        self.dirty = True
        self.message = f"新增 T{task_id:03d} · 等级 {priority}"
        return task_id

    def random_task(self):
        return self.add_task(self.rng.choice(self.warehouse.pickups),
                             self.rng.choice(self.warehouse.deliveries),
                             self.rng.choices((1, 2, 3, 4), (4, 3, 2, 1))[0])

    def copy_task(self, source_task_id, priority=None, task_id=None):
        source = self.tasks[source_task_id]
        level = source.priority if priority is None else priority
        new_id = self.add_task(source.pickup, source.delivery, level, task_id, record=False)
        self.tasks[new_id].copied_from = source_task_id
        self.record("copy", id=new_id, source_task_id=source_task_id, priority=level)
        self.message = f"复制 T{source_task_id:03d} → T{new_id:03d}"
        return new_id

    def assignment_cost(self, slot, task):
        if task.assignment_mode == "forced" and slot.robot_id != task.assignment_robot_id:
            return 10**6
        return completion_cost(self.warehouse, slot, task)

    def preference_cost(self, slots):
        available = {slot.robot_id for slot in slots if not slot.deferred}
        return lambda slot, task: int(task.assignment_mode == "preferred"
            and task.assignment_robot_id in available and slot.robot_id != task.assignment_robot_id)

    def validate_assignment(self, task_id, mode, robot_id=None):
        if isinstance(task_id, bool) or not isinstance(task_id, int):
            raise ValueError("任务编号无效")
        if mode not in ("auto", "forced", "preferred"):
            raise ValueError("分配模式无效")
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("任务不存在")
        if task.status not in ("pending", "reserved", "to_pickup"):
            raise ValueError("仅尚未开始装货的任务可以调整分配方式")
        if mode == "auto":
            if robot_id is not None:
                raise ValueError("恢复自动分配不能指定机器人")
            return
        if isinstance(robot_id, bool) or not isinstance(robot_id, int):
            raise ValueError("机器人编号无效")
        robot = next((r for r in self.robots if r.id == robot_id), None)
        if robot is None:
            raise ValueError("机器人不存在")
        if (task.assignment_mode, task.assignment_robot_id) == (mode, robot_id):
            return
        if mode == "forced":
            if robot.task_id not in (None, task_id) or robot.next_task_id not in (None, task_id) or robot.loaded:
                raise ValueError(f"R{robot_id}忙碌；本版不强制改派或预约指定")
            if any(t.id != task_id and t.status not in FINISHED and t.assignment_mode == "forced"
                   and t.assignment_robot_id == robot_id for t in self.tasks.values()):
                raise ValueError(f"R{robot_id}已有其他人工指定任务")
            # Explicit assignment may trade ETA, but must not bypass priority tiers.
            free = [Slot(r.id, r.position) for r in self.robots if r.task_id in (None, task_id) and r.next_task_id in (None, task_id)]
            pending = [t for t in self.tasks.values() if t.status == "pending" or t.id == task_id]
            _, baseline = exact_matching(free, pending, self.assignment_cost)
            _, remaining = exact_matching([s for s in free if s.robot_id != robot_id],
                [t for t in pending if t.id != task_id], self.assignment_cost)
            constrained = list(remaining[:5])
            constrained[5 - task.priority] -= 1
            if tuple(constrained) > baseline[:5]:
                raise ValueError("本次指定会绕过待分配任务的硬优先级，请先处理更高等级任务")

    def set_assignment(self, task_id, mode, robot_id=None, replay=False):
        task = self.tasks[task_id]
        if not replay:
            self.validate_assignment(task_id, mode, robot_id)
        else:
            # Input replay does not recreate worker/planner calls between same-tick events.
            if mode not in ("auto", "forced", "preferred") or (mode == "auto" and robot_id is not None):
                raise ValueError("回放分配模式无效")
            if mode != "auto" and not any(r.id == robot_id for r in self.robots):
                raise ValueError("回放指定机器人不存在")
            if task.status not in ("pending", "reserved", "to_pickup"):
                raise ValueError("回放不能改派已装货或结束的任务")
            if isinstance(task_id, bool) or not isinstance(task_id, int) or isinstance(robot_id, bool):
                raise ValueError("回放分配编号无效")
        if (task.assignment_mode, task.assignment_robot_id) == (mode, robot_id):
            return
        for robot in self.robots:
            if robot.task_id == task_id:
                robot.task_id = None
                robot.phase = "parking"
                robot.service_left = 0
            if robot.next_task_id == task_id:
                robot.next_task_id = None
        task.status, task.robot_id = "pending", None
        task.assignment_mode, task.assignment_robot_id = mode, robot_id
        if mode == "forced" and not replay:
            self.assign_task(self.robots[robot_id - 1], task_id)
        self.record("assignment", id=task_id, mode=mode, robot_id=robot_id)
        self.dirty = True
        label = {"auto": "自动分配", "forced": "指定执行", "preferred": "优先使用"}[mode]
        self.message = f"T{task_id:03d} · {label}" + (f" R{robot_id}" if robot_id else "")

    def set_priority(self, task_id, priority):
        task = self.tasks[task_id]
        if task.status in FINISHED:
            self.message = "已结束任务不能更改等级"
            return
        if not task.priority <= priority <= 5:
            self.message = "本版支持提升等级，不支持降低等级"
            return
        if task.priority == priority:
            return
        task.priority = priority
        # A first emergency upgrade must actually reconsider the carrier.
        # Once picking/loaded, custody remains atomic and cannot migrate.
        if priority == 5 and task.status == "to_pickup":
            robot = self.robots[task.robot_id - 1]
            robot.task_id = None
            robot.phase = "parking"
            task.status, task.robot_id = "pending", None
        self.record("priority", id=task_id, priority=priority)
        self.dirty = True
        self.message = f"T{task_id:03d} 已升为 {'紧急任务' if priority == 5 else str(priority) + '级'}"

    def cancel_task(self, task_id):
        task = self.tasks[task_id]
        # Loading is atomic; cancellation is still allowed before it starts.
        if task.status not in ("pending", "reserved", "to_pickup"):
            self.message = "仅待分配、等待接手或尚未开始装货的任务可以取消"
            return
        for robot in self.robots:
            if robot.task_id == task_id:
                robot.task_id = None
                robot.phase = "parking"
            if robot.next_task_id == task_id:
                robot.next_task_id = None
        task.status, task.robot_id = "cancelled", None
        self.record("cancel", id=task_id)
        self.dirty = True
        self.message = f"T{task_id:03d} 已取消，释放未来路径预约"

    def task_tail(self, robot):
        """Earliest release estimate for an atomic/current non-preemptible job."""
        task = self.tasks[robot.task_id]
        w = self.warehouse
        if robot.phase == "to_pickup":
            time = (w.distance(robot.position, task.pickup) + LOAD_TICKS
                    + w.distance(task.pickup, task.delivery) + UNLOAD_TICKS)
        elif robot.phase == "picking":
            time = robot.service_left + w.distance(task.pickup, task.delivery) + UNLOAD_TICKS
        elif robot.phase == "to_delivery":
            time = w.distance(robot.position, task.delivery) + UNLOAD_TICKS
        else:
            time = robot.service_left
        return time, task.delivery

    def release_task(self, robot):
        task = self.tasks[robot.task_id]
        task.status, task.robot_id = "pending", None
        task.preemptions += 1
        robot.task_id = None
        robot.phase = "parking"
        robot.service_left = 0
        self.metrics["preemptions"] += 1

    def assign_task(self, robot, task_id):
        task = self.tasks[task_id]
        robot.task_id = task_id
        robot.phase = "to_pickup"
        robot.service_left = 0
        task.status, task.robot_id = "to_pickup", robot.id
        self.start_service_if_arrived(robot)

    def dispatch(self):
        # Future emergency reservations may be improved whenever an event occurs.
        for robot in self.robots:
            if robot.next_task_id is not None:
                task = self.tasks[robot.next_task_id]
                task.status, task.robot_id = "pending", None
                robot.next_task_id = None
        urgent = [t for t in self.tasks.values() if t.status == "pending" and t.priority == 5]
        slots = []
        for robot in self.robots:
            current = self.tasks.get(robot.task_id)
            if current is None or (robot.phase == "to_pickup" and current.priority < 5):
                slots.append(Slot(robot.id, robot.position))
            else:
                release, origin = self.task_tail(robot)
                slots.append(Slot(robot.id, origin, release, True))
        urgent_pairs, urgent_score = exact_matching(
            slots, urgent, self.assignment_cost, self.preference_cost(slots))
        for slot in slots:
            if slot.robot_id not in urgent_pairs:
                continue
            robot = self.robots[slot.robot_id - 1]
            task_id = urgent_pairs[robot.id]
            if slot.deferred:
                robot.next_task_id = task_id
                task = self.tasks[task_id]
                task.status, task.robot_id = "reserved", robot.id
            else:
                if robot.task_id is not None:
                    self.release_task(robot)
                self.assign_task(robot, task_id)
        free = [Slot(r.id, r.position) for r in self.robots if r.task_id is None]
        pending = [t for t in self.tasks.values() if t.status == "pending"]
        pairs, score = exact_matching(free, pending, self.assignment_cost, self.preference_cost(free))
        for robot_id, task_id in pairs.items():
            self.assign_task(self.robots[robot_id - 1], task_id)
        self.assignment = {
            "pairs": {**urgent_pairs, **pairs}, "eta_sum": urgent_score[-2] + score[-2],
            "scope": "本轮 / 人工指定约束 / 硬优先级 / 软偏好 / 给定预计完成时间代价",
            "cost_model": "剩余必要动作 + 网格最短路 + 装卸；不预测未来插单与冲突等待",
        }
        # Parking endpoints are unique, even if service endpoints are shared.
        origins = []
        for robot in self.robots:
            future = self.tasks.get(robot.next_task_id or robot.task_id)
            origins.append(future.delivery if future else robot.position)
        parks = optimal_parking(self.warehouse, origins)
        for robot, parking in zip(self.robots, parks):
            robot.parking = parking
            if robot.task_id is None:
                robot.phase = "idle" if robot.position == parking else "parking"

    def itinerary(self, robot):
        points = []
        task = self.tasks.get(robot.task_id)
        if task:
            urgent = task.priority == 5
            if robot.phase == "to_pickup":
                points.append(Waypoint(task.pickup, LOAD_TICKS))
            elif robot.phase == "picking":
                points.append(Waypoint(task.pickup, robot.service_left))
            if robot.phase == "unloading":
                points.append(Waypoint(task.delivery, robot.service_left, True, urgent))
            else:
                points.append(Waypoint(task.delivery, UNLOAD_TICKS, True, urgent))
        upcoming = self.tasks.get(robot.next_task_id)
        if upcoming:
            points.extend((Waypoint(upcoming.pickup, LOAD_TICKS),
                           Waypoint(upcoming.delivery, UNLOAD_TICKS, True, True)))
        points.append(Waypoint(robot.parking))
        return points

    def ensure_plan(self):
        if not self.dirty:
            return True
        self.dispatch()
        starts = {r.id: r.position for r in self.robots}
        routes = {r.id: self.itinerary(r) for r in self.robots}
        # Longer maps need a horizon covering travel and service, even without conflicts.
        lower_bound = 0
        for robot_id, points in routes.items():
            origin, length = starts[robot_id], 0
            for waypoint in points:
                length += self.warehouse.distance(origin, waypoint.position) + waypoint.hold
                origin = waypoint.position
            lower_bound = max(lower_bound, length)
        horizon = max(PLAN_HORIZON, lower_bound + 40)
        budget = PLAN_SECONDS if len(self.robots)<=3 else FLEET_CBS_SECONDS
        result = plan(self.warehouse, starts, routes, seconds=budget, horizon=horizon)
        self.metrics["plans"] += 1
        self.metrics["planning_seconds"] += result.seconds
        self.metrics["last_plan_ms"] = result.seconds * 1000
        self.metrics["cbs_nodes"] = result.expanded
        if result.status != "success":
            # One bounded retry: longer horizon and a fresh constraint tree.
            self.metrics["recovery_attempts"] += 1
            retry = plan(self.warehouse, starts, routes, budget, horizon * 2)
            self.metrics["planning_seconds"] += retry.seconds
            self.metrics["plans"] += 1
            self.metrics["last_plan_ms"] = retry.seconds * 1000
            result = retry
        if result.status != "success":
            reserved = plan_reserved(self.warehouse,starts,routes,PLAN_SECONDS,horizon*2)
            self.metrics["planning_seconds"] += reserved.seconds
            self.metrics["plans"] += 1
            self.metrics["last_plan_ms"] = reserved.seconds*1000
            result = reserved
        if result.status != "success":
            self.paused = True
            self.failed_attempts += 1
            reason = "计算预算耗尽" if result.status == "timeout" else "搜索时间范围内未找到方案"
            jobs = " / ".join(f"R{r.id}:T{r.task_id or '-'}" for r in self.robots)
            self.message = f"已安全暂停：{reason}（不是无解证明） · {jobs}；可重试或取消未取货任务"
            return False
        for robot in self.robots:
            robot.path = result.paths[robot.id]
        self.metrics["planner"] = result.method
        if result.method == "reservations":
            self.metrics["reservation_plans"] += 1
        self.dirty = False
        self.failed_attempts = 0
        if self.message.startswith(("重新规划中", "已安全暂停", "连续无执行进展")):
            self.message = "安全路线已更新，可继续执行"
        return True

    def start_service_if_arrived(self, robot):
        task = self.tasks.get(robot.task_id)
        if not task:
            if robot.position == robot.parking:
                robot.phase = "idle"
            return
        if robot.phase == "to_pickup" and robot.position == task.pickup:
            robot.phase = task.status = "picking"
            robot.service_left = LOAD_TICKS
        elif robot.phase == "to_delivery" and robot.position == task.delivery:
            robot.phase = task.status = "unloading"
            robot.service_left = UNLOAD_TICKS

    def step(self):
        if self.paused or not self.ensure_plan():
            return False
        before = {r.id: r.position for r in self.robots}
        next_positions = {r.id: r.path[1] if len(r.path) > 1 else r.position for r in self.robots}
        pairs = {r.id: [r.position, next_positions[r.id]] for r in self.robots}
        if first_conflict(pairs):
            self.paused = True
            self.message = "执行安全检查失败，已保留现场"
            raise RuntimeError("Unsafe execution prevented")
        phases = {r.id: r.phase for r in self.robots}
        self.tick += 1
        progress = False
        for robot in self.robots:
            robot.previous = robot.position
            robot.position = next_positions[robot.id]
            if len(robot.path) > 1:
                robot.path = robot.path[1:]
            if robot.position != before[robot.id]:
                robot.distance += 1
                progress = True
            elif phases[robot.id] in ("to_pickup", "to_delivery", "parking"):
                robot.waits += 1
            if phases[robot.id] in ("picking", "unloading"):
                robot.service_left -= 1
                progress = True
                if robot.service_left == 0:
                    task = self.tasks[robot.task_id]
                    if phases[robot.id] == "picking":
                        robot.loaded = True
                        task.picked_at = self.tick
                        robot.phase = task.status = "to_delivery"
                    else:
                        robot.loaded = False
                        task.status = "completed"
                        task.completed_at = self.tick
                        robot.completed += 1
                        robot.task_id = None
                        robot.phase = "parking"
                        self.message = f"T{task.id:03d} 已完成 · R{robot.id} 可接新任务"
                        if robot.next_task_id is not None:
                            upcoming = robot.next_task_id
                            robot.next_task_id = None
                            self.assign_task(robot, upcoming)
                            self.message = f"R{robot.id} 已交付，开始执行紧急任务 T{upcoming:03d}"
                        self.dirty = True
            self.start_service_if_arrived(robot)
        if progress:
            self.last_progress = self.tick
        if self.auto and not self.replaying and self.tick % AUTO_INTERVAL == 0:
            self.random_task()
        self.apply_replay_events()
        if not progress and any(r.task_id is not None for r in self.robots):
            if self.tick - self.last_progress >= 12:
                self.dirty = True
                if self.tick - self.last_progress >= 24:
                    self.paused = True
                    self.message = "连续无执行进展，已安全暂停；可重试规划"
        self.assert_invariants()
        self.frames.append({"tick": self.tick, "robots": [
            {"id": r.id, "position": r.position, "phase": r.phase,
             "task": r.task_id, "loaded": r.loaded} for r in self.robots]})
        return True

    def assert_invariants(self):
        count = self.warehouse.robot_count
        if len(self.robots) != count or [r.id for r in self.robots] != list(range(1,count+1)):
            raise AssertionError("Robot population or IDs disagree with scene configuration")
        positions = [r.position for r in self.robots]
        if len(set(positions)) != len(self.robots):
            raise AssertionError("Robots overlap")
        current = [r.task_id for r in self.robots if r.task_id is not None]
        reserved = [r.next_task_id for r in self.robots if r.next_task_id is not None]
        if len(set(current + reserved)) != len(current + reserved):
            raise AssertionError("Task has more than one owner")
        for robot in self.robots:
            if not self.warehouse.is_open(robot.position):
                raise AssertionError("Robot entered an obstacle")
            if robot.loaded != (robot.phase in ("to_delivery", "unloading")):
                raise AssertionError("Cargo state and execution phase disagree")
            if robot.task_id is not None:
                task = self.tasks[robot.task_id]
                if task.robot_id != robot.id or task.status != robot.phase:
                    raise AssertionError("Task/robot states disagree")
        for task in self.tasks.values():
            if task.assignment_mode not in ("auto", "forced", "preferred"):
                raise AssertionError("Invalid assignment mode")
            if task.assignment_mode == "auto":
                if task.assignment_robot_id is not None:
                    raise AssertionError("Automatic task retains a requested robot")
            elif not any(r.id == task.assignment_robot_id for r in self.robots):
                raise AssertionError("Requested robot does not exist")
            if task.assignment_mode == "forced" and task.robot_id is not None and task.robot_id != task.assignment_robot_id:
                raise AssertionError("Forced assignment changed owner")

    def apply_replay_events(self):
        while self.replay_events and self.replay_events[0]["tick"] <= self.tick:
            event = self.replay_events.pop(0)
            op = event["operation"]
            if op == "add":
                self.add_task(event["pickup"], event["delivery"], event["priority"], event["id"])
            elif op == "priority":
                self.set_priority(event["id"], event["priority"])
            elif op == "cancel":
                self.cancel_task(event["id"])
            elif op == "auto":
                self.auto = event["enabled"]
                self.record("auto", enabled=self.auto)
            elif op == "assignment":
                self.set_assignment(event["id"], event["mode"], event.get("robot_id"), replay=True)
            elif op == "copy":
                self.copy_task(event["source_task_id"], event["priority"], event["id"])
        # Replay stays in replay mode after the last event: no unrecorded auto arrivals.

    def command(self, operation, **data):
        if operation not in ("pause", "retry"):
            self.branch_replay()
        if operation == "random":
            self.random_task()
        elif operation == "add":
            self.add_task(**data)
        elif operation == "priority":
            self.set_priority(**data)
        elif operation == "cancel":
            self.cancel_task(**data)
        elif operation == "assignment":
            self.set_assignment(**data)
        elif operation == "copy":
            self.copy_task(**data)
        elif operation == "auto":
            self.auto = data["enabled"]
            self.record("auto", enabled=self.auto)
        elif operation == "pause":
            self.paused = data["paused"]
        elif operation == "retry":
            self.dirty = True
            self.last_progress = self.tick
            self.message = "重新规划中"
        else:
            raise ValueError("Unknown operation")

    def snapshot(self):
        completed = [t for t in self.tasks.values() if t.status == "completed"]
        duration = [t.completed_at - t.created_at for t in completed]
        waiting = [t.picked_at - t.created_at - LOAD_TICKS for t in completed]
        metrics = {**self.metrics, "completed": len(completed), "total": len(self.tasks),
                   "pending": sum(t.status in ("pending", "reserved") for t in self.tasks.values()),
                   "avg_completion": sum(duration) / len(duration) if duration else 0,
                   "avg_wait": sum(waiting) / len(waiting) if waiting else 0,
                   "distance": sum(r.distance for r in self.robots),
                   "waits": sum(r.waits for r in self.robots)}
        return View(self.warehouse, deepcopy(self.robots), deepcopy(self.tasks), self.tick,
                    self.paused, self.auto, self.message, metrics, deepcopy(self.assignment), self.replaying)
