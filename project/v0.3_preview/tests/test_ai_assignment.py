"""Scheduling constraints, cargo custody, replay and AI write receipts."""
import itertools
import json
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.configuration import Configuration
from ai.service import AIService
from ai.tools import normalize, task_view, TOOLS
from controller import Controller
from models import Task
from persistence import save, load
from scheduler import Slot, exact_matching
from simulation import Simulation
from test_ai import MemoryCredentials


class ConstrainedMatchingTests(unittest.TestCase):
    def test_priority_preference_eta_against_exhaustive_oracle(self):
        rng = random.Random(413)
        for _ in range(25):
            slots = [Slot(i, (0, 0), deferred=rng.choice((True, False))) for i in (1, 2, 3)]
            tasks = [Task(i, (1, 1), (2, 2), rng.randint(1, 5), i,
                          assignment_mode=rng.choice(("auto", "forced", "preferred")),
                          assignment_robot_id=rng.randint(1, 3)) for i in range(1, 5)]
            matrix = {(s.robot_id, t.id): rng.randint(1, 50) for s in slots for t in tasks}
            available = {s.robot_id for s in slots if not s.deferred}
            def cost(s, t):
                return 10**6 if t.assignment_mode == "forced" and s.robot_id != t.assignment_robot_id else matrix[s.robot_id, t.id]
            def preference(s, t):
                return int(t.assignment_mode == "preferred" and t.assignment_robot_id in available and s.robot_id != t.assignment_robot_id)
            pairs, score = exact_matching(slots, tasks, cost, preference)
            best = None
            for choices in itertools.product([None] + tasks, repeat=3):
                ids = [t.id for t in choices if t]
                if len(set(ids)) != len(ids):
                    continue
                value = [0] * 8
                for s, t in zip(slots, choices):
                    if t:
                        if cost(s, t) >= 10**6:
                            break
                        value[5 - t.priority] -= 1
                        value[5] += preference(s, t)
                        value[6] += cost(s, t)
                        value[7] += t.created_at
                else:
                    if best is None or tuple(value) < best:
                        best = tuple(value)
            self.assertEqual(score, best)
            for robot, task_id in pairs.items():
                t = next(t for t in tasks if t.id == task_id)
                if t.assignment_mode == "forced":
                    self.assertEqual(robot, t.assignment_robot_id)


class PolicySimulationTests(unittest.TestCase):
    def sim(self, count=3):
        return Simulation(initial_tasks=0, robot_count=count)

    def add(self, sim, priority=2, pickup=0):
        return sim.add_task(sim.warehouse.pickups[pickup], sim.warehouse.deliveries[0], priority)

    def test_preloading_task_can_migrate_to_free_robot_and_binding_persists(self):
        s = self.sim()
        task = self.add(s)
        self.assertTrue(s.ensure_plan())
        original = s.tasks[task].robot_id
        target = next(r.id for r in s.robots if r.task_id is None)
        s.set_assignment(task, "forced", target)
        self.assertTrue(s.ensure_plan())
        self.assertNotEqual(original, target)
        self.assertEqual(s.tasks[task].robot_id, target)
        self.add(s, 3, 4)
        self.assertTrue(s.ensure_plan())
        self.assertEqual(s.tasks[task].robot_id, target)
        for _ in range(250):
            self.assertTrue(s.step(), s.message)
        self.assertEqual(s.tasks[task].status, "completed")
        self.assertEqual(s.tasks[task].robot_id, target)
        s.assert_invariants()

    def test_current_owner_can_be_locked_without_other_task_preemption(self):
        s = self.sim()
        task = self.add(s)
        s.ensure_plan()
        owner = s.tasks[task].robot_id
        s.set_assignment(task, "forced", owner)
        s.ensure_plan()
        self.assertEqual(s.tasks[task].robot_id, owner)
        self.assertEqual(s.metrics["preemptions"], 0)

    def test_emergency_temporarily_preempts_bound_job_but_does_not_change_owner(self):
        s = self.sim()
        ordinary = self.add(s, pickup=19)
        s.set_assignment(ordinary, "forced", 3)
        s.ensure_plan()
        emergency = self.add(s, 5)
        self.assertTrue(s.ensure_plan())
        self.assertEqual(s.tasks[emergency].robot_id, 3)
        self.assertEqual(s.tasks[ordinary].status, "pending")
        self.assertEqual(s.tasks[ordinary].assignment_robot_id, 3)
        self.assertTrue(all(r.task_id != ordinary for r in s.robots))
        for _ in range(400):
            self.assertTrue(s.step(), s.message)
        self.assertEqual(s.tasks[ordinary].status, "completed")
        self.assertEqual(s.tasks[ordinary].robot_id, 3)

    def test_emergency_upgrade_keeps_manual_owner(self):
        s = self.sim()
        task = self.add(s)
        s.set_assignment(task, "forced", 1)
        s.ensure_plan()
        s.set_priority(task, 5)
        self.assertTrue(s.ensure_plan())
        self.assertEqual(s.tasks[task].robot_id, 1)

    def test_binding_cannot_bypass_higher_priority(self):
        s = self.sim(1)
        higher, lower = self.add(s, 5), self.add(s, 2)
        before = list(s.events)
        with self.assertRaisesRegex(ValueError, "硬优先级"):
            s.set_assignment(lower, "forced", 1)
        self.assertEqual(s.events, before)
        self.assertEqual(s.tasks[lower].assignment_mode, "auto")
        s.ensure_plan()
        self.assertEqual(s.robots[0].task_id, higher)

    def test_busy_robot_is_not_stolen(self):
        s = self.sim()
        first, second = self.add(s), self.add(s, pickup=4)
        s.ensure_plan()
        owner = s.tasks[first].robot_id
        before = [(r.id, r.task_id) for r in s.robots]
        with self.assertRaisesRegex(ValueError, "忙碌"):
            s.set_assignment(second, "forced", owner)
        self.assertEqual(before, [(r.id, r.task_id) for r in s.robots])
        s.assert_invariants()

    def test_release_restores_unconstrained_matching(self):
        s = self.sim()
        task = self.add(s)
        s.set_assignment(task, "forced", 1)
        s.ensure_plan()
        s.set_assignment(task, "auto")
        s.ensure_plan()
        self.assertEqual(s.tasks[task].assignment_mode, "auto")
        self.assertIsNone(s.tasks[task].assignment_robot_id)
        self.assertEqual(s.tasks[task].robot_id, 3)

    def test_soft_preference_accepts_longer_eta_and_can_replace_binding(self):
        s = self.sim()
        task = self.add(s)
        s.set_assignment(task, "forced", 3)
        s.ensure_plan()
        s.set_assignment(task, "preferred", 1)
        s.ensure_plan()
        self.assertEqual(s.tasks[task].assignment_mode, "preferred")
        self.assertEqual(s.tasks[task].robot_id, 1)

    def test_busy_preferred_robot_falls_back_without_preemption(self):
        s = self.sim()
        first = self.add(s, pickup=4)
        s.set_assignment(first, "forced", 1)
        s.ensure_plan()
        second = self.add(s)
        s.set_assignment(second, "preferred", 1)
        s.ensure_plan()
        self.assertEqual(s.tasks[first].robot_id, 1)
        self.assertNotEqual(s.tasks[second].robot_id, 1)
        self.assertEqual(s.tasks[second].assignment_robot_id, 1)
        self.assertEqual(s.metrics["preemptions"], 0)

    def test_atomic_service_rejects_all_policy_changes(self):
        s = self.sim()
        task = self.add(s)
        for _ in range(120):
            self.assertTrue(s.step())
            if s.tasks[task].status == "picking":
                break
        self.assertEqual(s.tasks[task].status, "picking")
        before = (s.tasks[task].robot_id, list(s.events))
        for mode, robot in (("forced", 1), ("preferred", 2), ("auto", None)):
            with self.assertRaisesRegex(ValueError, "装货"):
                s.set_assignment(task, mode, robot)
        self.assertEqual((s.tasks[task].robot_id, s.events), before)
        s.assert_invariants()

    def test_copy_inherits_route_and_priority_but_not_policy_or_status(self):
        s = self.sim()
        source = self.add(s, 4)
        s.set_assignment(source, "forced", 1)
        copied = s.copy_task(source)
        lower = s.copy_task(source, 2)
        self.assertEqual(s.tasks[copied].priority, 4)
        self.assertEqual(s.tasks[lower].priority, 2)
        self.assertEqual(s.tasks[copied].pickup, s.tasks[source].pickup)
        self.assertEqual(s.tasks[copied].delivery, s.tasks[source].delivery)
        self.assertEqual(s.tasks[copied].copied_from, source)
        self.assertEqual(s.tasks[copied].status, "pending")
        self.assertEqual(s.tasks[copied].assignment_mode, "auto")
        self.assertIsNone(s.tasks[copied].assignment_robot_id)
        s.cancel_task(source)
        after_cancel = s.copy_task(source)
        self.assertNotEqual(after_cancel, source)
        self.assertEqual(s.tasks[source].status, "cancelled")

    def test_policy_copy_save_and_input_replay_without_ai(self):
        with TemporaryDirectory() as tmp:
            s = self.sim()
            source = self.add(s, 3)
            s.set_assignment(source, "forced", 1)
            s.ensure_plan()
            copied = s.copy_task(source)
            s.set_assignment(copied, "preferred", 2)
            with patch("persistence.OUTPUTS", Path(tmp)):
                path = save(s)
            replay = load(path)
            self.assertTrue(replay.ensure_plan(), replay.message)
            self.assertEqual(replay.tasks[source].assignment_mode, "forced")
            self.assertEqual(replay.tasks[source].robot_id, 1)
            self.assertEqual(replay.tasks[copied].assignment_mode, "preferred")
            self.assertEqual(replay.tasks[copied].assignment_robot_id, 2)
            self.assertEqual(replay.tasks[copied].copied_from, source)
            for _ in range(250):
                self.assertTrue(replay.step(), replay.message)
            self.assertTrue(all(t.status == "completed" for t in replay.tasks.values()))


class PolicyActorTests(unittest.TestCase):
    def setUp(self):
        self.c = Controller(paused=True)
        # Replace the initial input before the actor starts; no concurrent state mutation.
        self.c.sim = Simulation(initial_tasks=0)
        self.c.sim.paused = True
        self.c._publish()
        self.c.start()
        self.c.submit("pause", {"paused": True}).result(10)
        self.c.submit("add", {"pickup": 1, "delivery": 1, "priority": 3}).result(15)

    def tearDown(self):
        self.c.stop(save_on_exit=False)

    def tool(self, name, args, operation=None, generation=None, valid=None):
        return self.c.submit("_ai_business", {"name": name, "arguments": args,
            "operation_id": operation or name, "generation": self.c.generation if generation is None else generation,
            "valid": valid or (lambda: True)}).result(15)

    def test_all_four_tools_real_actor_receipts_and_pause(self):
        assigned = self.tool("assign_task", {"task_id": "T001", "robot_id": "R1"})
        self.assertEqual(assigned["actions"][0]["assigned_robot"], "R1")
        self.assertEqual(assigned["actions"][0]["requested_robot"], "R1")
        self.assertEqual(assigned["actions"][0]["assignment_mode"], "forced")
        self.assertEqual(assigned, self.tool("assign_task", {"task_id": "T001", "robot_id": "R1"}))
        self.assertEqual(self.tool("release_task_assignment", {"task_id": "T001"})["actions"][0]["assignment_mode"], "auto")
        preferred = self.tool("set_task_preference", {"task_id": "T001", "robot_id": "R2"})
        self.assertEqual(preferred["actions"][0]["assigned_robot"], "R2")
        copied = self.tool("copy_task", {"task_id": "T001", "count": 2})
        self.assertEqual([a["task_id"] for a in copied["actions"]], ["T002", "T003"])
        self.assertTrue(all(a["outcome"] == "applied" and a["copied_from"] == "T001" for a in copied["actions"]))
        self.assertEqual(copied, self.tool("copy_task", {"task_id": "T001", "count": 2}))
        self.assertEqual(len(self.c.sim.tasks), 3)
        self.assertTrue(self.c.state()["paused"])
        self.assertEqual(self.c.state()["tick"], 0)

    def test_policy_no_change_and_bad_ids_have_no_effect(self):
        first = self.tool("assign_task", {"task_id": "T001", "robot_id": "R1"})
        again = self.tool("assign_task", {"task_id": "T001", "robot_id": "R1"}, "again")
        self.assertEqual(again["actions"][0]["outcome"], "no_change")
        bad = self.tool("set_task_preference", {"task_id": "T001", "robot_id": "R99"})
        self.assertIn("error", bad)
        self.assertEqual(self.c.sim.tasks[1].assignment_mode, "forced")
        self.assertEqual(first["actions"][0]["assigned_robot"], "R1")

    def test_copy_invalid_source_and_count_stop_before_writes(self):
        self.assertIn("error", self.tool("copy_task", {"task_id": "T999", "count": 2}))
        for count in (0, 21, True, "2"):
            with self.assertRaises(ValueError):
                normalize("copy_task", {"task_id": "T001", "count": count})
        with self.assertRaises(ValueError):
            normalize("assign_task", {"task_id": "T001", "robot_id": 1})
        self.assertEqual(len(self.c.sim.tasks), 1)

    def test_copy_partial_planning_failure_is_not_rolled_back_or_duplicated(self):
        with patch.object(self.c, "_plan", side_effect=RuntimeError("test planner failure")):
            result = self.tool("copy_task", {"task_id": "T001", "count": 3})
        self.assertEqual([a["outcome"] for a in result["actions"]], ["applied", "not_executed", "not_executed"])
        self.assertEqual(len(self.c.sim.tasks), 2)
        self.assertEqual(result, self.tool("copy_task", {"task_id": "T001", "count": 3}))

    def test_assignment_committed_before_planning_failure(self):
        with patch.object(self.c, "_plan", side_effect=RuntimeError("test planner failure")):
            result = self.tool("assign_task", {"task_id": "T001", "robot_id": "R1"})
        self.assertEqual(result["actions"][0]["outcome"], "applied")
        self.assertEqual(result["actions"][0]["planning"], "unavailable")
        self.assertEqual(self.c.sim.tasks[1].assignment_robot_id, 1)

    def test_stopped_and_stale_new_tools_cannot_write(self):
        before = len(self.c.sim.tasks)
        for name, args in (("copy_task", {"task_id": "T001"}), ("assign_task", {"task_id": "T001", "robot_id": "R1"})):
            self.assertIn("error", self.tool(name, args, name + "-stop", valid=lambda: False))
            self.assertIn("error", self.tool(name, args, name + "-stale", generation=-1))
        self.assertEqual(len(self.c.sim.tasks), before)
        self.assertEqual(self.c.sim.tasks[1].assignment_mode, "auto")

    def test_model_roundtrip_new_tools_and_duplicate_copy_with_scripted_provider(self):
        class ScriptedProvider:
            def chat(self, cfg, messages, tools, token, on_text=None):
                self_names = {t["function"]["name"] for t in tools}
                assert {"assign_task", "release_task_assignment", "set_task_preference", "copy_task"} <= self_names
                if messages[-1]["role"] == "tool":
                    return {"role": "assistant", "content": "操作以真实回执为准。", "reasoning_content": ""}, None
                plan = [("assign_task", {"task_id": "T001", "robot_id": "R1"}),
                        ("release_task_assignment", {"task_id": "T001"}),
                        ("set_task_preference", {"task_id": "T001", "robot_id": "R2"}),
                        ("copy_task", {"task_id": "T001", "count": 2}),
                        ("copy_task", {"task_id": "T001", "count": 2})]
                return {"role": "assistant", "content": "", "reasoning_content": "",
                    "tool_calls": [{"id": f"call-{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}} for i, (name, args) in enumerate(plan)]}, None
        with TemporaryDirectory() as tmp:
            cfg = Configuration(Path(tmp) / "settings.json", MemoryCredentials())
            cfg.save({"api_key": "MOCK_POLICY_KEY", "model": "mock"})
            service = AIService(self.c, cfg, ScriptedProvider())
            try:
                service.launch("message", {"text": "执行测试计划", "generation": self.c.generation})
                deadline = monotonic() + 20
                while service.public()["busy"] and monotonic() < deadline:
                    sleep(.03)
                self.assertFalse(service.public()["busy"])
                self.assertFalse([e for e in service.events if e["kind"] == "error"])
                self.assertEqual(len(self.c.sim.tasks), 3)
                tools = [e["tool"] for e in service.events if e["kind"] == "result"]
                self.assertEqual(tools, ["assign_task", "release_task_assignment", "set_task_preference", "copy_task"])
                view = task_view(self.c.sim.tasks[1], self.c.sim.warehouse)
                self.assertEqual(view["assignment_mode"], "preferred")
                self.assertEqual(view["requested_robot"], "R2")
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
