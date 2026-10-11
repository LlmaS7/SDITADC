"""Launch the independent HTML desktop window, browser mode, or headless core."""
import argparse
import json
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import webbrowser

from config import DEFAULT_SEED, OUTPUTS, VERSION
from controller import Controller
from persistence import load, save, write_json
from server import start_server
from simulation import Simulation


def headless(args):
    sim = load(Path(args.load)) if args.load else Simulation(args.seed)
    if args.auto:
        sim.command("auto", enabled=True)
    for _ in range(args.ticks):
        if not sim.step():
            raise RuntimeError(sim.message)
    if not args.no_save:
        save(sim)
    print(json.dumps({"tick": sim.tick, **sim.snapshot().metrics}, ensure_ascii=False, indent=2))


def graphical(args):
    native = not (args.serve or args.browser)
    controller = Controller(args.seed, paused=args.paused or native, auto=args.auto,
                            scenario=Path(args.load) if args.load else None)
    server, url = start_server(controller, args.port)
    controller.start()
    print(f"SDITADC v{VERSION}: {url}", flush=True)
    try:
        if args.serve or args.browser:
            if args.browser:
                webbrowser.open(url)
            while True:
                sleep(.25)
        else:
            import webview
            smoke = args.smoke_test
            window = webview.create_window("SDITADC · v0.2_preview · 三机仓库协作",
                                           url, width=1460, height=940, min_size=(1080, 720),
                                           hidden=smoke, maximized=not smoke, background_color="#101820")
            result = {"ok": False}

            def inspect_window():
                deadline = monotonic() + 35
                try:
                    while monotonic() < deadline:
                        try:
                            value = window.evaluate_js("window.previewDebug ? window.previewDebug.inspect() : null")
                            if value and value.get("ready") and all(t is not None for t in value.get("viewTicks", [])):
                                result.update(value)
                                coordinates = value.get("positions", [])
                                canvas = value.get("canvas2d", [])
                                same_positions = len(coordinates) == len(canvas) == 3 and all(
                                    abs(a["x"] - b["x"]) < 1e-6 and abs(a["y"] - b["y"]) < 1e-6
                                    for a, b in zip(coordinates, canvas))
                                result["ok"] = bool(value.get("webgl2") and value.get("robotCount") == 3
                                                    and value.get("drawCalls", 0) > 0 and same_positions
                                                    and all(int(t) == value["tick"] for t in value["viewTicks"]))
                                if not smoke and not args.paused:
                                    controller.submit("pause", {"paused": False}).result(timeout=10)
                                break
                        except Exception:
                            pass
                        sleep(.15)
                finally:
                    if smoke:
                        write_json(OUTPUTS / "desktop_check.json", result)
                        window.destroy()

            with TemporaryDirectory(prefix="sditadc-webview-", ignore_cleanup_errors=True) as profile:
                webview.start(inspect_window, gui="edgechromium", debug=args.debug,
                              private_mode=True, storage_path=profile)
            if smoke and not result["ok"]:
                raise RuntimeError(f"独立窗口渲染检查未通过：{result}")
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop(save_on_exit=not args.no_save and not args.smoke_test)
        server.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="SDITADC HTML + Three.js three-robot preview")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--ticks", type=int, default=1200)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--paused", action="store_true")
    parser.add_argument("--load")
    parser.add_argument("--browser", action="store_true", help="Open the same UI in a browser")
    parser.add_argument("--serve", action="store_true", help="Serve locally without opening a window")
    parser.add_argument("--port", type=int, default=0, help="0 selects a free local port")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help="Check hidden native WebView2 rendering")
    parser.add_argument("--no-save", action="store_true", help="Do not overwrite saved runs on exit")
    args = parser.parse_args()
    headless(args) if args.headless else graphical(args)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        (OUTPUTS / "startup_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if sys.stderr is None:
            if "--smoke-test" not in sys.argv:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, "启动未完成，请查看本版本 outputs/startup_error.log。", "SDITADC", 16)
            sys.exit(1)
        raise

