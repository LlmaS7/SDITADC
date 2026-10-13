"""Configurable fleets, exact parking assignment and complete safe fallback routes."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import ROOT
from controller import Controller
from map_format import load_map, validate_map, robot_limits
from models import Task, Waypoint
from persistence import save, load, write_json
from planning.prioritized import plan_reserved
from planning.validation import first_conflict
from scheduler import Slot, exact_matching, minimum_assignment, optimal_parking
from simulation import Simulation
from warehouse import Warehouse


class FleetTests(unittest.TestCase):
    def test_counts_follow_map_caps_and_distinct_adjacent_spawn_prefixes(self):
        for map_id,cap in (("warehouse",6),("warehouse_64x48",8),("movingai_warehouse",6)):
            definition=load_map(map_id)
            self.assertEqual(robot_limits(definition),(3,cap))
            for count in (1,2,3,cap):
                with self.subTest(map=map_id,count=count):
                    s=Simulation(initial_tasks=0,map_id=map_id,robot_count=count)
                    self.assertEqual(len(s.robots),count)
                    self.assertEqual(s.warehouse.starts,[tuple(p) for p in definition["points"]["starts"][:count]])
                    self.assertEqual(len({r.position for r in s.robots}),count)
                    s.assert_invariants()
                    self.assertTrue(s.step(),s.message)

    def test_bad_counts_and_oversized_map_capacity_are_rejected(self):
        for count in (0,-1,7,True,1.5,"3"):
            with self.subTest(count=count),self.assertRaises(ValueError):
                Simulation(robot_count=count)
        for limits in ({"max_count":7},{"max_count":13},{"max_count":5,"default_count":6},True):
            definition=load_map("warehouse")
            definition["robots"]=limits
            with self.subTest(limits=limits),self.assertRaises(ValueError):
                validate_map(definition)
        definition=load_map("warehouse")
        definition["points"]["starts"][3:5]=reversed(definition["points"]["starts"][3:5])
        with self.assertRaisesRegex(ValueError,"起点池"):
            validate_map(definition)
        s=Simulation(initial_tasks=0,robot_count=2)
        s.robots.pop()
        with self.assertRaises(AssertionError):
            s.assert_invariants()

    def test_reset_rejects_over_capacity_without_mutation_then_changes_fleet(self):
        c=Controller(paused=True)
        c.start()
        try:
            c.submit("pause",{"paused":True}).result(timeout=10)
            before=c.state()
            for count in (0,7,True):
                with self.assertRaises(ValueError):
                    c.submit("reset",{"seed":9,"robot_count":count}).result(timeout=10)
                after=c.state()
                for key in ("tick","generation","revision","robots","map"):
                    self.assertEqual(before[key],after[key])
            after=c.submit("reset",{"seed":9,"robot_count":2}).result(timeout=10)
            self.assertEqual(after["robot_count"],2)
            self.assertEqual(after["map"]["max_robots"],6)
            self.assertTrue(after["paused"])
            self.assertEqual(after["tick"],0)
            self.assertEqual(len(after["robots"]),2)
            self.assertEqual(c.submit("step").result(timeout=10)["tick"],1)
        finally:
            c.stop(save_on_exit=False)

    def test_solo_fleet_completes_jobs_and_retains_atomic_cargo_for_emergency(self):
        s=Simulation(initial_tasks=0,robot_count=1)
        first=s.add_task(s.warehouse.pickups[0],s.warehouse.deliveries[0])
        for _ in range(120):
            self.assertTrue(s.step(),s.message)
            if s.robots[0].loaded:
                break
        self.assertTrue(s.robots[0].loaded)
        urgent=s.add_task(s.warehouse.pickups[1],s.warehouse.deliveries[1],5)
        self.assertTrue(s.ensure_plan(),s.message)
        self.assertEqual(s.robots[0].task_id,first)
        self.assertEqual(s.robots[0].next_task_id,urgent)
        for _ in range(240):
            self.assertTrue(s.step(),s.message)
        self.assertTrue(all(t.status=="completed" for t in s.tasks.values()))
        self.assertEqual(s.metrics["collisions"],0)

    def test_nondefault_count_survives_snapshot_replay_and_legacy_defaults(self):
        with TemporaryDirectory(dir=ROOT/"outputs",prefix="fleet-test-") as tmp:
            s=Simulation(initial_tasks=2,map_id="warehouse_64x48",robot_count=4)
            for _ in range(15):
                self.assertTrue(s.step(),s.message)
            with patch("persistence.OUTPUTS",Path(tmp)):
                path=save(s)
                replay=load(path)
            self.assertEqual(len(replay.robots),4)
            self.assertEqual(replay.warehouse.max_robots,8)
            for _ in range(15):
                self.assertTrue(replay.step(),replay.message)
            self.assertEqual([r.position for r in s.robots],[r.position for r in replay.robots])
            self.assertEqual([(t.id,t.status,t.robot_id) for t in s.tasks.values()],
                             [(t.id,t.status,t.robot_id) for t in replay.tasks.values()])
            # Pre-upgrade snapshots have three starts and no fleet settings.
            old=deepcopy(load_map("warehouse"));old.pop("robots")
            old["points"]["starts"]=old["points"]["starts"][:3]
            path=Path(tmp)/"old.json"
            write_json(path,{"version":"0.2.1_preview","seed":1,"map_definition":old,"events":[]})
            legacy=load(path)
            self.assertEqual(len(legacy.robots),3)
            self.assertEqual(legacy.warehouse.max_robots,3)


class FleetAssignmentTests(unittest.TestCase):
    def test_parking_matching_equals_bruteforce_with_deterministic_ties(self):
        rng=random.Random(17)
        for count in (1,2,3,4):
            parks=[(i,0) for i in range(count+2)]
            origins=[(i,1) for i in range(count)]
            for _ in range(12):
                matrix={(p,q):rng.randrange(5) for p in origins for q in parks}
                w=SimpleNamespace(parking=parks,distance=lambda p,q:matrix[p,q])
                expected=min(itertools.permutations(range(len(parks)),count),
                             key=lambda indices:(sum(matrix[p,parks[j]] for p,j in zip(origins,indices)),indices))
                self.assertEqual(optimal_parking(w,origins),[parks[j] for j in expected])
        matrix=[[abs(i-j) for j in range(15)] for i in range(12)]
        self.assertEqual(minimum_assignment(matrix),list(range(12)))
        with self.assertRaises(ValueError):
            minimum_assignment([[0],[0]])

    def test_task_matching_remains_exact_for_different_fleet_sizes(self):
        rng=random.Random(5)
        for count in (1,2,4):
            slots=[Slot(i+1,(0,0)) for i in range(count)]
            for _ in range(8):
                tasks=[Task(i+1,(1,1),(2,2),rng.randint(1,5),i) for i in range(4)]
                costs={(s.robot_id,t.id):rng.randint(1,20) for s in slots for t in tasks}
                pairs,score=exact_matching(slots,tasks,lambda s,t:costs[s.robot_id,t.id])
                oracle=[]
                for choice in itertools.product([None]+tasks,repeat=count):
                    used=[t.id for t in choice if t is not None]
                    if len(set(used))!=len(used):
                        continue
                    value=[0]*7
                    for slot,t in zip(slots,choice):
                        if t is not None:
                            value[5-t.priority]-=1
                            value[5]+=costs[slot.robot_id,t.id]
                            value[6]+=t.created_at
                    oracle.append(tuple(value))
                self.assertEqual(score,min(oracle))
                self.assertEqual(len(set(pairs.values())),len(pairs))


class ReservationPlanningTests(unittest.TestCase):
    def test_complete_routes_preserve_shared_service_holds_and_persistent_parking(self):
        w=Warehouse(1,robot_count=4)
        starts={i+1:p for i,p in enumerate(w.starts)}
        routes={r:[Waypoint(w.pickups[0],2),Waypoint(w.deliveries[0],2,True,r==1),
                   Waypoint(w.parking[r-1])] for r in starts}
        result=plan_reserved(w,starts,routes,2,200)
        self.assertEqual(result.status,"success")
        self.assertEqual(set(result.paths),set(starts))
        self.assertIsNone(first_conflict(result.paths))
        for robot,path in result.paths.items():
            self.assertEqual(path[-1],w.parking[robot-1])
            for endpoint in (w.pickups[0],w.deliveries[0]):
                self.assertTrue(any(path[t:t+3]==[endpoint]*3 for t in range(len(path)-2)))

    def test_swap_is_avoided_and_timeout_never_returns_partial_routes(self):
        w=Warehouse(1)
        starts={1:(2,2),2:(3,2)}
        routes={1:[Waypoint((3,2))],2:[Waypoint((2,2))]}
        result=plan_reserved(w,starts,routes,2,40)
        self.assertEqual(result.status,"success")
        self.assertIsNone(first_conflict(result.paths))
        failed=plan_reserved(w,starts,routes,0,40)
        self.assertNotEqual(failed.status,"success")
        self.assertEqual(failed.paths,{})


if __name__ == "__main__":
    unittest.main()
