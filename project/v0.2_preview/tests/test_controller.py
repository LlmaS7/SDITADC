"""Exercise shared state, serialized commands and the actual local HTTP contract."""
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Controller
from server import start_server


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller(paused=True)
        self.controller.start()
        self.controller.submit("pause", {"paused": True}).result(timeout=8)

    def tearDown(self):
        self.controller.stop(save_on_exit=False)

    def command(self, op, data=None):
        return self.controller.submit(op, data).result(timeout=8)

    def test_step_and_paused_commands_keep_one_clock(self):
        before = self.controller.state()
        value = self.command("step")
        self.assertEqual(value["tick"], before["tick"] + 1)
        self.assertTrue(value["paused"])
        positions = [r["position"] for r in value["robots"]]
        value = self.command("random")
        self.assertEqual(value["tick"], 1)
        self.assertEqual(positions, [r["position"] for r in value["robots"]])
        self.assertEqual(len(value["tasks"]), 10)

    def test_upgrade_cancel_and_ascending_serialized_tasks(self):
        value = self.command("priority", {"task_id": 1, "priority": 5})
        task = next(t for t in value["tasks"] if t["id"] == 1)
        self.assertEqual(task["priority"], 5)
        self.assertIsNotNone(task["robot_id"])
        value = self.command("cancel", {"task_id": 1})
        self.assertEqual([t["id"] for t in value["tasks"]], list(range(2, 10)))
        self.assertEqual(value["metrics"]["visible_total"], 8)
        self.assertEqual(self.controller.sim.tasks[1].status, "cancelled")

    def test_invalid_operation_does_not_advance_or_break_actor(self):
        for op, data in (("speed", {"value": 3}), ("add", {"pickup": 999, "delivery": 1, "priority": 1})):
            with self.assertRaises(ValueError):
                self.command(op, data)
        self.assertEqual(self.command("step")["tick"], 1)

    def test_reset_generation_prevents_reusing_old_view_state(self):
        self.command("step")
        old = self.controller.state()
        value = self.command("reset", {"seed": 17})
        self.assertEqual(value["tick"], 0)
        self.assertGreater(value["generation"], old["generation"])
        self.assertEqual(value["map"]["seed"], 17)
        self.assertTrue(value["paused"])

    def test_http_same_state_static_assets_and_commands(self):
        server, url = start_server(self.controller)
        try:
            first = json.loads(urlopen(url + "api/state").read())
            second = json.loads(urlopen(url + "api/state").read())
            self.assertEqual(first["tick"], second["tick"])
            self.assertEqual(first["robots"], second["robots"])
            html = urlopen(url).read().decode()
            self.assertIn('id="scene3d"', html)
            self.assertIn('id="map2d"', html)
            self.assertIn('id="tasks"', html)
            with urlopen(url + "vendor/three.module.js") as response:
                self.assertTrue(response.headers["Content-Type"].startswith("text/javascript"))
            request = Request(url + "api/command", data=b'{"operation":"step"}', headers={"Content-Type":"application/json"})
            value = json.loads(urlopen(request).read())
            self.assertEqual(value["state"]["tick"], 1)
            with self.assertRaises(HTTPError) as caught:
                urlopen(url + "../config.py")
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

