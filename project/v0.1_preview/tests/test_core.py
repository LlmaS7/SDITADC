"""Domain checks. These are tests, not selectable demonstration scenarios."""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ROOT, LOAD_TICKS, UNLOAD_TICKS
from models import Task, Waypoint
from warehouse import Warehouse
from scheduler import Slot, exact_matching
from planning.astar import search
from planning.cbs import plan
from planning.validation import first_conflict
from simulation import Simulation
from persistence import write_json, load
from time import monotonic


class AssignmentTests(unittest.TestCase):
    def test_exact_against_exhaustive_oracle(self):
        rng = random.Random(7)
        slots = [Slot(i, (0, 0)) for i in range(3)]
        for _ in range(30):
            tasks = [Task(i, (1, 1), (2, 2), rng.randint(1, 5), i) for i in range(5)]
            matrix = {(r.robot_id, t.id): rng.randint(1, 40) for r in slots for t in tasks}
            cost = lambda r, t: matrix[r.robot_id, t.id]
            actual, score = exact_matching(slots, tasks, cost)
            best = None
            for choice in itertools.product([None] + tasks, repeat=3):
                chosen = [t for t in choice if t is not None]
                if len({t.id for t in chosen}) != len(chosen):
                    continue
                value = [0] * 7
                for slot, task in zip(slots, choice):
                    if task is not None:
                        value[5 - task.priority] -= 1
                        value[5] += cost(slot, task)
                        value[6] += task.created_at
                value = tuple(value)
                if best is None or value < best:
                    best = value
            self.assertEqual(score, best)
            self.assertEqual(len(set(actual.values())), len(actual))


class PlanningTests(unittest.TestCase):
    def test_final_occupancy_constraint(self):
        w = Warehouse(10)
        start, end = w.starts[0], w.starts[1]
        path, _ = search(w, start, [Waypoint(end)], [("v", 5, end)], monotonic() + 2, 40)
        self.assertEqual(path[-1], end)
        self.assertGreater(len(path) - 1, 5)
        self.assertNotEqual(path[5], end)

    def test_service_holds_and_shared_service_point(self):
        w = Warehouse(10)
        starts = {i + 1: p for i, p in enumerate(w.starts)}
        itineraries = {i: [Waypoint(w.pickups[0], 2), Waypoint(w.deliveries[0], 2, True),
                            Waypoint(w.parking[i - 1])] for i in starts}
        result = plan(w, starts, itineraries, seconds=5)
        self.assertEqual(result.status, "success")
        self.assertIsNone(first_conflict(result.paths))
        for path in result.paths.values():
            for endpoint in (w.pickups[0], w.deliveries[0]):
                self.assertTrue(any(path[t:t + 3] == [endpoint] * 3 for t in range(len(path) - 2)))

    def test_swap_rejected_and_cbs_routes_around(self):
        w = Warehouse(1)
        starts = {1: (2, 2), 2: (3, 2), 3: (4, 2)}
        goals = {1: (3, 2), 2: (2, 2), 3: (4, 2)}
        self.assertIsNotNone(first_conflict({r: [p, goals[r]] for r, p in starts.items()}))
        result = plan(w, starts, {r: [Waypoint(goals[r])] for r in starts})
        self.assertEqual(result.status, "success")
        self.assertIsNone(first_conflict(result.paths))


class SimulationTests(unittest.TestCase):
    def test_ordinary_tasks_complete_and_park(self):
        for seed in (20261010, 17, 91):
            s = Simulation(seed)
            for _ in range(450):
                self.assertTrue(s.step(), s.message)
            self.assertTrue(all(t.status == "completed" for t in s.tasks.values()))
            self.assertTrue(all(r.phase == "idle" and r.position in s.warehouse.parking for r in s.robots))
            self.assertEqual(s.snapshot().metrics["collisions"], 0)

    def test_emergency_preempts_only_unpicked_job(self):
        s = Simulation()
        self.assertTrue(s.ensure_plan())
        previous = {r.task_id for r in s.robots}
        urgent = s.add_task(s.warehouse.pickups[0], s.warehouse.deliveries[0], 5)
        self.assertTrue(s.ensure_plan(), s.message)
        self.assertEqual(s.tasks[urgent].status, "to_pickup")
        self.assertEqual(s.metrics["preemptions"], 1)
        displaced = [s.tasks[t] for t in previous if s.tasks[t].preemptions]
        self.assertEqual(len(displaced), 1)
        self.assertEqual(displaced[0].status, "pending")
        for _ in range(450):
            self.assertTrue(s.step(), s.message)
        self.assertTrue(all(t.status == "completed" for t in s.tasks.values()))

    def test_all_loaded_reserve_without_losing_cargo(self):
        s = Simulation(initial_tasks=0)
        for r in s.robots:
            tid = s.add_task(s.warehouse.pickups[r.id], s.warehouse.deliveries[r.id - 1])
            r.task_id = tid
            r.position = s.tasks[tid].pickup
            r.previous = r.position
            r.phase = s.tasks[tid].status = "to_delivery"
            r.loaded = True
            s.tasks[tid].robot_id = r.id
            s.tasks[tid].picked_at = 0
        urgent = s.add_task(s.warehouse.pickups[0], s.warehouse.deliveries[0], 5)
        self.assertTrue(s.ensure_plan(), s.message)
        self.assertEqual(s.tasks[urgent].status, "reserved")
        self.assertTrue(all(r.loaded for r in s.robots))
        self.assertEqual(s.metrics["preemptions"], 0)
        for _ in range(300):
            self.assertTrue(s.step(), s.message)
        self.assertTrue(all(t.status == "completed" for t in s.tasks.values()))

    def test_existing_task_upgrade_reconsiders_carrier(self):
        s = Simulation()
        self.assertTrue(s.ensure_plan())
        task = s.tasks[s.robots[0].task_id]
        # R2 is now immediately adjacent to the upgraded pickup; R1 is distant.
        neighbor = next(p for p in s.warehouse.neighbors(task.pickup)
                        if p not in [r.position for r in s.robots])
        s.robots[1].position = s.robots[1].previous = neighbor
        s.set_priority(task.id, 5)
        self.assertTrue(s.ensure_plan(), s.message)
        self.assertEqual(task.robot_id, 2)
        self.assertEqual(s.robots[1].task_id, task.id)
        s.assert_invariants()

    def test_cancel_releases_task_and_paths(self):
        s = Simulation()
        self.assertTrue(s.ensure_plan())
        task = s.robots[0].task_id
        s.cancel_task(task)
        self.assertTrue(s.ensure_plan())
        self.assertEqual(s.tasks[task].status, "cancelled")
        self.assertTrue(all(r.task_id != task and r.next_task_id != task for r in s.robots))

    def test_pause_and_input_replay(self):
        s = Simulation(initial_tasks=3)
        for _ in range(10):
            self.assertTrue(s.step())
        task = s.random_task()
        s.set_priority(task, 5)
        s.command("pause", paused=True)
        positions, tick = [r.position for r in s.robots], s.tick
        self.assertTrue(s.ensure_plan())
        self.assertFalse(s.step())
        self.assertEqual([r.position for r in s.robots], positions)
        self.assertEqual(s.tick, tick)
        s.command("pause", paused=False)
        for _ in range(100):
            self.assertTrue(s.step())
        path = ROOT / "work" / "test_replay.json"
        write_json(path, {"version": "0.1_preview", "seed": s.warehouse.seed, "events": s.events})
        replay = load(path)
        for _ in range(110):
            self.assertTrue(replay.step(), replay.message)
        self.assertEqual([r.position for r in s.robots], [r.position for r in replay.robots])
        self.assertEqual([(t.id, t.status, t.robot_id) for t in s.tasks.values()],
                         [(t.id, t.status, t.robot_id) for t in replay.tasks.values()])
        path.unlink()

    def test_map_generation_preserves_all_free_cell_connectivity(self):
        for seed in range(15):
            w = Warehouse(seed)
            connected = w.reachable(w.starts[0])
            self.assertEqual(len(connected), w.width * w.height - len(w.blocked))
            self.assertEqual(len(w.obstacles), 20)
            self.assertTrue(all(p in connected for p in w.parking + w.pickups + w.deliveries))


if __name__ == "__main__":
    unittest.main()
