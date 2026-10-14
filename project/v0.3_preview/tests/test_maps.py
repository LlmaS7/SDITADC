"""Map interchange, rejection before reset, and self-contained event replay."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ROOT
from controller import Controller
from map_format import validate_map, catalog, load_map
from map_tools import import_movingai
from persistence import save, load
from simulation import Simulation
from warehouse import Warehouse


def small_map():
    # An L-shaped rack and an internal wall; there is no mandatory border wall.
    return {"format": "sditadc-map", "version": 1, "name": "测试布局",
            "grid": {"width": 11, "height": 9,
                     "rows": ["...........", "...........", "....#......",
                              "...........", ".....RRR...", ".....R.....",
                              "...........", "...........", "..........."]},
            "points": {"starts": [[1,1],[2,1],[3,1]],
                       "parking": [[1,1],[2,1],[3,1],[9,1],[1,7],[9,7]],
                       "pickups": [[4,4],[7,3]], "deliveries": [[7,7]]},
            "random_obstacles": {"count": 0}}


class MapTests(unittest.TestCase):
    def test_irregular_grid_and_no_implicit_border(self):
        w = Warehouse(1, "test", small_map())
        self.assertTrue(w.is_open((0,0)))
        self.assertTrue(w.is_open((6,5)))  # Hole beside L-shaped rack remains open.
        self.assertFalse(w.is_open((5,5)))
        self.assertEqual(w.walls, {(4,2)})
        s = Simulation(1, initial_tasks=2, map_id="test", map_definition=small_map())
        for _ in range(70):
            self.assertTrue(s.step(), s.message)
        self.assertTrue(all(t.status == "completed" for t in s.tasks.values()))
        crowded=small_map()
        crowded["random_obstacles"]={"count":200}
        limited=Warehouse(1,"limited",crowded)
        self.assertLess(limited.random_count,200)
        self.assertEqual(len(limited.reachable(limited.starts[0])),
                         limited.width*limited.height-len(limited.blocked))

    def test_bad_geometry_points_and_disconnection_are_rejected(self):
        bad = []
        d=small_map();d["grid"]["rows"][0]="short";bad.append(d)
        d=small_map();d["grid"]["rows"][0]="?..........";bad.append(d)
        d=small_map();d["points"]["pickups"]=[[4,2]];bad.append(d)
        d=small_map();d["points"]["deliveries"]=[[11,7]];bad.append(d)
        d=small_map();d["points"]["starts"][2]=[9,1];bad.append(d)
        d=small_map();d["points"]["deliveries"]=d["points"]["pickups"];bad.append(d)
        d=small_map();d["grid"]["rows"][6]="###########";bad.append(d)
        for d in bad:
            with self.subTest(definition=d), self.assertRaises(ValueError):
                validate_map(d)
        for map_id in ("../config", "C:/tmp/test", "warehouse.json", None):
            with self.subTest(map_id=map_id), self.assertRaises(ValueError):
                load_map(map_id)

    def test_builtin_maps_and_seeded_clutter(self):
        maps = catalog()
        self.assertTrue(all(m["available"] for m in maps), maps)
        self.assertIn("movingai_warehouse", [m["id"] for m in maps])
        a,b = Warehouse(20261010),Warehouse(20261010)
        self.assertEqual(a.blocked,b.blocked)
        self.assertEqual(len(a.obstacles),20)
        self.assertNotEqual(a.obstacles,Warehouse(42).obstacles)
        large=Warehouse(1,"movingai_warehouse")
        self.assertEqual((large.width,large.height),(161,63))
        self.assertEqual(large.random_count,0)

    def test_replay_survives_missing_or_changed_source_map(self):
        with TemporaryDirectory(dir=ROOT / "outputs",prefix="map-test-") as tmp:
            s=Simulation(7,initial_tasks=2,map_id="deleted_map",map_definition=small_map())
            for _ in range(10):
                self.assertTrue(s.step())
            s.random_task()
            for _ in range(35):
                self.assertTrue(s.step())
            with patch("persistence.OUTPUTS",Path(tmp)):
                path=save(s)
                replay=load(path)  # There is deliberately no deleted_map.json.
            self.assertEqual(replay.warehouse.blocked,s.warehouse.blocked)
            for _ in range(s.tick):
                self.assertTrue(replay.step(),replay.message)
            self.assertEqual([r.position for r in s.robots],[r.position for r in replay.robots])
            self.assertEqual([(t.id,t.status,t.robot_id) for t in s.tasks.values()],
                             [(t.id,t.status,t.robot_id) for t in replay.tasks.values()])
            realized=Warehouse(42)
            frozen=Warehouse(42,"missing",realized.export_map())
            self.assertEqual(realized.blocked,frozen.blocked)

    def test_catalog_and_failed_reset_preserve_current_scene(self):
        c=Controller(paused=True)
        c.start()
        try:
            c.submit("pause",{"paused":True}).result(timeout=10)
            with TemporaryDirectory(dir=ROOT / "outputs",prefix="map-test-") as tmp:
                folder=Path(tmp)
                (folder/"test.json").write_text(json.dumps(small_map()),encoding="utf-8")
                (folder/"broken.json").write_text("{}",encoding="utf-8")
                with patch("map_format.MAPS",folder):
                    entries=catalog()
                    self.assertFalse(next(m for m in entries if m["id"]=="broken")["available"])
                    before=c.state()
                    with self.assertRaises(ValueError):
                        c.submit("reset",{"seed":9,"map_id":"broken"}).result(timeout=10)
                    unchanged=c.state()
                    for key in ("revision", "generation", "tick", "map", "tasks", "robots"):
                        self.assertEqual(unchanged[key],before[key])
                    self.assertEqual(c.seed,before["map"]["seed"])
                    after=c.submit("reset",{"seed":9,"map_id":"test"}).result(timeout=10)
                    self.assertEqual(after["map"]["id"],"test")
                    self.assertEqual(after["map"]["width"],11)
                    self.assertEqual(after["generation"],before["generation"]+1)
                    self.assertEqual(after["tick"],0)
                    self.assertTrue(after["paused"])
        finally:
            c.stop(save_on_exit=False)

    def test_movingai_conversion_requires_explicit_business_points(self):
        with TemporaryDirectory(dir=ROOT / "outputs",prefix="map-test-") as tmp:
            path=Path(tmp)/"test.map"
            definition=small_map()
            rows=[row.replace("R","T").replace("#","@") for row in definition["grid"]["rows"]]
            path.write_text("type octile\nheight 9\nwidth 11\nmap\n"+"\n".join(rows)+"\n",encoding="utf-8")
            converted=import_movingai(path,definition["points"],"Converted","shelves")
            self.assertEqual(converted["grid"]["rows"][5][6],".")
            self.assertEqual(converted["grid"]["rows"][5][5],"R")
            with self.assertRaises(ValueError):
                import_movingai(path,{},"Missing metadata")
            path.write_text(path.read_text().replace("...........","S..........",1),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"地形"):
                import_movingai(path,definition["points"],"Unsupported terrain")


if __name__ == "__main__":
    unittest.main()
