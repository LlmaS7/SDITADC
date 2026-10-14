"""Loopback-only static HTML and JSON commands, using Python's standard library."""
from concurrent.futures import TimeoutError
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import unquote, urlsplit, parse_qs
import json
import mimetypes
from config import FRONTEND
from map_format import catalog
from ai.service import AIService


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, controller=None, ai=None, **kwargs):
        self.controller = controller
        self.ai = ai
        super().__init__(*args, **kwargs)

    def log_message(self, *_):
        pass

    def local_host(self):
        try:
            host = urlsplit("http://" + self.headers.get("Host", ""))
            return host.hostname in ("127.0.0.1", "localhost", "::1") and host.port == self.server.server_port
        except ValueError:
            return False

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.local_host():
            self.send(403, {"error": "只接受本机服务地址"})
            return
        path = unquote(urlsplit(self.path).path)
        if path == "/api/ai/settings":
            self.send(200, self.ai.public())
            return
        if path == "/api/ai/events":
            try:
                after = int(parse_qs(urlsplit(self.path).query).get("after", ["0"])[0])
                self.send(200, self.ai.event_page(max(0, after)))
            except ValueError:
                self.send(400, {"error": "事件编号无效"})
            return
        if path == "/api/state":
            self.send(200, self.controller.state())
            return
        if path == "/api/maps":
            self.send(200, {"maps": catalog()})
            return
        if path == "/api/health":
            self.send(200, {"ok": True, "version": self.controller.state()["version"]})
            return
        if path == "/favicon.ico":
            self.send(204, b"")
            return
        target = (FRONTEND / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if not target.is_relative_to(FRONTEND.resolve()) or not target.is_file():
            self.send(404, {"error": "文件不存在"})
            return
        content_type = "text/javascript" if target.suffix == ".js" else mimetypes.guess_type(target)[0]
        self.send(200, target.read_bytes(), (content_type or "application/octet-stream") + "; charset=utf-8")

    def do_POST(self):
        if not self.local_host():
            self.send(403, {"error": "只接受本机服务地址"})
            return
        path = urlsplit(self.path).path
        if path != "/api/command" and not path.startswith("/api/ai/"):
            self.send(404, {"error": "接口不存在"})
            return
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.send(403, {"error": "只接受本窗口的操作"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768 or not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("请求格式无效")
            value = json.loads(self.rfile.read(length))
            if path.startswith("/api/ai/"):
                if not isinstance(value, dict):
                    raise ValueError("请求格式无效")
                if path == "/api/ai/settings":
                    self.send(200, self.ai.save_settings(value))
                elif path in ("/api/ai/models", "/api/ai/test", "/api/ai/messages"):
                    kind = {"/api/ai/models": "models", "/api/ai/test": "test", "/api/ai/messages": "message"}[path]
                    self.send(202, self.ai.launch(kind, value))
                elif path == "/api/ai/stop":
                    self.ai.stop(value.get("request_id"))
                    self.send(200, {"ok": True})
                elif path == "/api/ai/clear":
                    self.ai.clear()
                    self.send(200, {"ok": True})
                else:
                    self.send(404, {"error": "接口不存在"})
                return
            if not isinstance(value, dict) or not isinstance(value.get("operation"), str):
                raise ValueError("操作格式无效")
            if value["operation"].startswith("_"):
                raise ValueError("操作不可从界面调用")
            data = value.get("data", {})
            if not isinstance(data, dict):
                raise ValueError("操作参数无效")
            state = self.controller.submit(value["operation"], data).result(timeout=10)
            self.send(200, {"ok": True, "state": state})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send(400, {"error": str(exc)})
        except TimeoutError:
            self.send(503, {"error": "当前规划尚未完成，请等待状态更新"})
        except Exception as exc:
            self.send(500, {"error": str(exc)})


class LocalServer(ThreadingHTTPServer):
    def server_close(self):
        if hasattr(self, "ai"):
            self.ai.close()
        super().server_close()


def start_server(controller, port=0, ai=None):
    ai = ai or AIService(controller)
    try:
        server = LocalServer(("127.0.0.1", port), partial(Handler, controller=controller, ai=ai))
    except Exception:
        ai.close()
        raise
    server.ai = ai
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, name="local-html-server", daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}/"

