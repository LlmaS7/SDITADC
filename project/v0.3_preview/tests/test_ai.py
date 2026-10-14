"""State-changing boundaries and actual HTTP/SSE integration, without a real key."""
from concurrent.futures import TimeoutError
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread, Event
from time import monotonic, sleep
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Controller
from ai.configuration import Configuration
from ai.conversation import Conversation
from ai.provider import DeepSeek, CancelToken, ProviderError
from ai.service import AIService
from ai.tools import normalize
from server import start_server


class MemoryCredentials:
    def __init__(self):
        self.values = {}
    def read(self, address):
        return self.values.get(address, "")
    def write(self, address, key):
        self.values[address] = key
    def delete(self, address):
        self.values.pop(address, None)


class MockUpstream(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *_):
        pass
    def do_GET(self):
        body = json.dumps({"data": [{"id": "mock-deepseek", "name": "Mock DeepSeek", "context_window": 64000, "effort": {"supported_levels": ["low", "high", "max"]}}]}).encode()
        self.send_response(200);self.send_header("Content-Length", str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(value)
        self.send_response(200);self.send_header("Content-Type", "text/event-stream");self.end_headers()
        def chunk(delta, finish=None):
            self.wfile.write(("data: "+json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]}, ensure_ascii=False)+"\n\n").encode())
        if value["messages"][-1]["role"] == "tool":
            chunk({"content": "工具结果已收到，操作以真实回执为准。"}, "stop")
        else:
            text = value["messages"][-1]["content"]
            if "只读协议测试" in value["messages"][0]["content"]:
                name, args = "get_locations", {}
            elif "取消" in text:
                name, args = "cancel_tasks", {"task_ids": ["T010"]}
            elif "升级" in text:
                name, args = "raise_task_priorities", {"changes": [{"task_id": "T010", "mode": "set", "priority": 5}]}
            else:
                name, args = "create_tasks", {"tasks": [{"pickup_id": "P04", "delivery_id": "D2", "priority": 5}]}
            chunk({"reasoning_content": "INTERNAL_REASONING_ONLY"})
            encoded = json.dumps(args)
            chunk({"tool_calls": [{"index": 0, "id": "mock-call", "type": "function", "function": {"name": name, "arguments": encoded[:5]}}]})
            chunk({"tool_calls": [{"index": 0, "function": {"arguments": encoded[5:]}}]}, "tool_calls")
        self.wfile.write(b"data: [DONE]\n\n")


@contextmanager
def upstream():
    MockUpstream.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockUpstream)
    thread = Thread(target=server.serve_forever, daemon=True);thread.start()
    try:
        yield "http://127.0.0.1:"+str(server.server_port)
    finally:
        server.shutdown();server.server_close()


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.c = Controller(paused=True)
        self.c.start();self.c.submit("pause", {"paused": True}).result(10)
    def tearDown(self):
        self.c.stop(save_on_exit=False)
    def run_tool(self, name, args, key="test", generation=None, valid=None):
        return self.c.submit("_ai_business", {"name": name, "arguments": args, "operation_id": key,
             "generation": self.c.generation if generation is None else generation, "valid": valid or (lambda: True)}).result(15)
    def create(self, **kwargs):
        return self.run_tool("create_tasks", {"tasks": [{"pickup_id": "P04", "delivery_id": "D2"}]}, **kwargs)
    def test_create_paused_deduplicates_and_defaults(self):
        before = self.c.state()
        first = self.create()
        self.assertEqual(first, self.create())
        self.assertEqual(len(self.c.sim.tasks), 10)
        self.assertEqual(first["actions"][0]["priority"], 2)
        self.assertEqual(first["actions"][0]["outcome"], "applied")
        self.assertTrue(self.c.state()["paused"])
        self.assertEqual(self.c.state()["tick"], before["tick"])
    def test_invalid_batch_has_zero_changes(self):
        value = self.run_tool("create_tasks", {"tasks": [{"pickup_id": "P01", "delivery_id": "D1"}, {"pickup_id": "P999", "delivery_id": "D1"}]})
        self.assertIn("error", value)
        self.assertEqual(len(self.c.sim.tasks), 9)
    def test_increment_uses_sequential_current_grade(self):
        result = self.run_tool("raise_task_priorities", {"changes": [{"task_id": "T001", "mode": "increment"}, {"task_id": "T001", "mode": "increment"}]})
        self.assertEqual([a["priority"] for a in result["actions"]], [3, 4])
    def test_cancel_hides_record_and_refuses_loading(self):
        self.create()
        value = self.run_tool("cancel_tasks", {"task_ids": ["T010"]}, key="cancel")
        self.assertEqual(value["actions"][0]["outcome"], "applied")
        self.assertEqual(self.c.sim.tasks[10].status, "cancelled")
        self.assertNotIn(10, [t["id"] for t in self.c.state()["tasks"]])
        for _ in range(100):
            self.c.submit("step").result(15)
            loading = next((t for t in self.c.sim.tasks.values() if t.status in ("picking", "to_delivery", "unloading")), None)
            if loading:
                break
        value = self.run_tool("cancel_tasks", {"task_ids": [f"T{loading.id:03}"]}, key="reject")
        self.assertIn("error", value)
        self.assertNotEqual(self.c.sim.tasks[loading.id].status, "cancelled")
    def test_stale_and_stopped_envelopes_do_not_write(self):
        self.c.submit("reset").result(15)
        self.assertIn("error", self.create(generation=0))
        self.assertIn("error", self.create(key="stop", valid=lambda: False))
        self.assertEqual(len(self.c.sim.tasks), 9)
    def test_dto_has_no_debug_data(self):
        result = self.run_tool("get_status", {})
        raw = json.dumps(result)
        for word in ('"paused"', '"tick"', '"seed"', '"generation"', '"revision"', '"path"', '"speed"'):
            self.assertNotIn(word, raw)
        self.assertEqual(len(result["robots"]), 3)
    def test_tool_schema_rejects_numeric_ids_and_unknown_fields(self):
        with self.assertRaises(ValueError):normalize("get_status",{"task_id":1})
        with self.assertRaises(ValueError):normalize("create_tasks",{"tasks":[{"pickup_id":"P01","delivery_id":"D1","extra":True}]})
    def test_committed_creation_survives_planning_exception(self):
        with patch.object(self.c, "_plan", side_effect=RuntimeError("planned failure")):
            value = self.create()
            self.assertEqual(value["actions"][0]["outcome"], "applied")
            self.assertEqual(value["actions"][0]["planning"], "unavailable")
            self.assertEqual(value, self.create())
        self.assertEqual(len(self.c.sim.tasks), 10)
    def test_unknown_and_boolean_parameters_rejected(self):
        for name, args in (("pause", {}), ("create_tasks", {"tasks": [{"pickup_id": True, "delivery_id": "D1"}]}), ("get_status", {"paused": True})):
            with self.assertRaises(ValueError):
                normalize(name, args)
    def test_partial_batch_stops_after_committed_planning_failure(self):
        with patch.object(self.c, "_plan", side_effect=RuntimeError("planned failure")):
            value = self.run_tool("create_tasks", {"tasks": [{"pickup_id": "P01", "delivery_id": "D1"}, {"pickup_id": "P02", "delivery_id": "D2"}]})
        self.assertEqual([a["outcome"] for a in value["actions"]], ["applied", "not_executed"])
        self.assertEqual(len(self.c.sim.tasks), 10)
    def test_same_id_different_args_is_rejected(self):
        self.create()
        with self.assertRaises(ValueError):
            self.run_tool("create_tasks", {"tasks": [{"pickup_id": "P01", "delivery_id": "D1"}]})


class IntegrationTests(unittest.TestCase):
    def test_host_and_origin_checks_protect_local_ai_settings(self):
        with TemporaryDirectory() as tmp:
            c=Controller(paused=True);c.start()
            service=AIService(c,Configuration(Path(tmp)/"settings.json",MemoryCredentials()))
            server,url=start_server(c,ai=service)
            try:
                requests=[Request(url+'api/ai/settings',headers={'Host':'other.example'}),Request(url+'api/ai/settings',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://other.example'})]
                for request in requests:
                    with self.assertRaises(HTTPError) as caught:urlopen(request)
                    self.assertEqual(caught.exception.code,403);caught.exception.close()
                with self.assertRaises(HTTPError) as caught:urlopen(url+'../local_settings.json')
                self.assertEqual(caught.exception.code,404);caught.exception.close()
            finally:
                server.shutdown();server.server_close();c.stop(save_on_exit=False)
    def test_real_mock_sse_roundtrip_models_test_create_upgrade_cancel(self):
        with TemporaryDirectory() as tmp, upstream() as base:
            c = Controller(paused=True);c.start();c.submit("pause", {"paused": True}).result(10)
            cfg = Configuration(Path(tmp)/"settings.json", MemoryCredentials())
            cfg.save({"base_url": base, "api_key": "MOCK_TEST_KEY", "model": "mock-deepseek"})
            service = AIService(c, cfg)
            server, local = start_server(c, ai=service)
            def post(path, body):
                req = Request(local+"api/ai/"+path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                return json.loads(urlopen(req, timeout=10).read())
            def wait():
                deadline = monotonic()+20
                while service.public()["busy"] and monotonic()<deadline:sleep(.04)
                self.assertFalse(service.public()["busy"])
                errors = [e for e in service.events if e["kind"] == "error"]
                self.assertEqual(errors, [])
            try:
                post("models", {});wait();self.assertEqual(service.models[0]["name"], "Mock DeepSeek")
                post("test", {});wait();self.assertTrue(service.verified)
                for message in ("创建紧急任务", "升级任务", "取消任务"):
                    post("messages", {"text": message, "generation": c.generation, "task_id": None});wait()
                self.assertEqual(c.sim.tasks[10].status, "cancelled")
                self.assertEqual(len(c.sim.tasks), 10)
                public = urlopen(local+"api/ai/settings").read().decode()
                events = urlopen(local+"api/ai/events").read().decode()
                self.assertNotIn("MOCK_TEST_KEY", public+events+Path(tmp,"settings.json").read_text())
                self.assertNotIn("INTERNAL_REASONING_ONLY", events)
                second = next(v for v in MockUpstream.calls if v["messages"][-1]["role"] == "tool")
                self.assertEqual(second["messages"][-2]["reasoning_content"], "INTERNAL_REASONING_ONLY")
                self.assertEqual(second["reasoning_effort"], "high")
            finally:
                service.close();server.shutdown();server.server_close();c.stop(save_on_exit=False)
    def test_settings_rebind_and_persistence_never_save_key(self):
        with TemporaryDirectory() as tmp:
            store = MemoryCredentials();path=Path(tmp)/"settings.json"
            cfg = Configuration(path, store)
            cfg.save({"api_key": "MOCK_PRIVATE", "remember": True, "model": "test-model"})
            self.assertNotIn("MOCK_PRIVATE", path.read_text())
            self.assertTrue(Configuration(path, store).public()["has_key"])
            cfg.save({"base_url": "https://other.example/v1", "remember": False})
            self.assertFalse(cfg.public()["has_key"])
            self.assertEqual(store.values, {})
    def test_summary_failure_crops_complete_turns(self):
        class FailedProvider:
            def chat(self, *a):raise ProviderError("test timeout")
        conv = Conversation()
        conv.turns = [[{"role": "user", "content": "旧消息"*3000}, {"role": "assistant", "content": "结果"*3000, "reasoning_content": "隐藏"}] for _ in range(5)]
        notices=[]
        conv.prepare(FailedProvider(), {"context_window": 24000}, CancelToken(), notices.append)
        self.assertEqual(len(conv.turns), 1)
        self.assertTrue(notices)
        self.assertIn("裁剪", conv.summary)
    def test_scene_change_and_stop_block_late_model_writes(self):
        class SlowProvider:
            def __init__(self):self.entered=Event();self.release=Event()
            def chat(self, *args):
                self.entered.set();self.release.wait(5)
                return {"role":"assistant","content":"","reasoning_content":"", "tool_calls":[{"id":"late","type":"function","function":{"name":"create_tasks","arguments":json.dumps({"tasks":[{"pickup_id":"P01","delivery_id":"D1"}]})}}]}, None
        for mode in ("scene", "stop"):
            with self.subTest(mode=mode), TemporaryDirectory() as tmp:
                c=Controller(paused=True);c.start();c.submit("pause",{"paused":True}).result(10)
                cfg=Configuration(Path(tmp)/"settings.json",MemoryCredentials());cfg.save({"api_key":"MOCK_TEST","model":"mock"})
                provider=SlowProvider();service=AIService(c,cfg,provider)
                try:
                    service.launch("message",{"text":"创建任务","task_id":None,"generation":0})
                    self.assertTrue(provider.entered.wait(3))
                    with self.assertRaises(ValueError):service.launch("message",{"text":"再创建","generation":0})
                    if mode=="scene":c.submit("reset").result(10);service.sync_scene()
                    else:service.stop()
                    provider.release.set()
                    deadline=monotonic()+5
                    while service.public()["busy"] and monotonic()<deadline:sleep(.02)
                    self.assertFalse(service.public()["busy"])
                    self.assertEqual(len(c.sim.tasks),9)
                finally:
                    provider.release.set();service.close();c.stop(save_on_exit=False)
    def test_previous_version_records_remain_readable(self):
        from persistence import load
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"old.json";path.write_text(json.dumps({"version":"0.2.1_preview","seed":20261010,"events":[]}),encoding="utf-8")
            self.assertEqual(len(load(path).robots),3)


if __name__ == "__main__":
    unittest.main()
