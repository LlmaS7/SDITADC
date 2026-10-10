"""Single launch entry. Planning runs in one worker; Pygame stays on main thread."""
import argparse
import json
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic

from config import DEFAULT_SEED, OUTPUTS, ROOT, WINDOW
from persistence import load, save
from simulation import Simulation


def headless(args):
    sim = load(Path(args.load)) if args.load else Simulation(args.seed)
    sim.auto = args.auto
    if args.auto:
        sim.record("auto", enabled=True)
    for _ in range(args.ticks):
        if not sim.step():
            raise RuntimeError(sim.message)
    save(sim)
    print(json.dumps({"tick": sim.tick, **sim.snapshot().metrics}, ensure_ascii=False, indent=2))


def graphical(args):
    import pygame
    from ui.widgets import Fonts, button, text, BG, CARD, TEXT, MUTED, ACCENT
    from ui.renderer import render, map_cell
    from ui.task_panel import TaskPanel

    pygame.init()
    pygame.display.set_caption("SDITADC · v0.1_preview · 三机仓库协作")
    screen = pygame.display.set_mode(WINDOW)
    fonts = Fonts()
    panel = TaskPanel()
    sim = load(Path(args.load)) if args.load else Simulation(args.seed)
    if args.auto:
        sim.command("auto", enabled=True)
    view = sim.snapshot()
    commands = deque()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-planner")
    future = None
    clock = pygame.time.Clock()
    running = True
    paused = False
    speeds = (1, 2, 4, 8)
    speed_index = 1
    last_frame = monotonic()
    notice = ""
    modal = None
    toolbar_boxes = []
    modal_boxes = []
    need_initial_plan = True

    def worker(batch, advance):
        nonlocal sim
        error = ""
        try:
            for operation, data in batch:
                if operation == "reset":
                    sim = Simulation(args.seed)
                elif operation == "load":
                    sim = load()
                elif operation == "save":
                    save(sim)
                    sim.message = "已保存场景输入和运行报告至 outputs/"
                else:
                    sim.command(operation, **data)
            if advance:
                sim.step()
            else:
                sim.ensure_plan()
        except Exception as exc:
            sim.paused = True
            sim.message = f"操作未完成：{exc}"
            error = str(exc)
            OUTPUTS.mkdir(parents=True, exist_ok=True)
            (OUTPUTS / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        return sim.snapshot(), error

    def enqueue(operation, **data):
        commands.append((operation, data))

    def action(name):
        nonlocal paused, speed_index, modal, last_frame, notice
        if name == "pause":
            paused = not paused
            enqueue("pause", paused=paused)
        elif name == "step":
            paused = True
            enqueue("pause", paused=False)
            commands.append(("_step", {}))
        elif name == "speed":
            speed_index = (speed_index + 1) % len(speeds)
        elif name == "manual":
            modal = {"pickup": 0, "delivery": 0, "priority": 1}
            paused = True
            enqueue("pause", paused=True)
        elif name == "auto":
            enqueue("auto", enabled=not view.auto)
        elif name == "reset":
            paused = True
            panel.selected, panel.scroll = None, 0
            enqueue("reset")
            enqueue("pause", paused=True)
        else:
            enqueue(name)

    try:
        while running:
            now = monotonic()
            if future and future.done():
                view, error = future.result()
                future = None
                last_frame = now
                paused = view.paused
                notice = error
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        modal = None
                    elif event.key == pygame.K_SPACE and modal is None:
                        action("pause")
                    elif event.key == pygame.K_n and modal is None:
                        action("step")
                    elif event.key == pygame.K_a and modal is None:
                        action("random")
                    elif event.key == pygame.K_s and modal is None:
                        action("save")
                    elif event.key == pygame.K_r and modal is None:
                        action("retry")
                if modal is not None:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for rect, name in modal_boxes:
                            if not rect.collidepoint(event.pos):
                                continue
                            if name == "close":
                                modal = None
                            elif name == "create":
                                enqueue("add", pickup=view.warehouse.pickups[modal["pickup"]],
                                        delivery=view.warehouse.deliveries[modal["delivery"]], priority=modal["priority"])
                                modal = None
                            else:
                                key, delta = name
                                length = len(view.warehouse.pickups) if key == "pickup" else len(view.warehouse.deliveries)
                                if key == "priority":
                                    modal[key] = (modal[key] - 1 + delta) % 5 + 1
                                else:
                                    modal[key] = (modal[key] + delta) % length
                        if modal is not None:
                            p = map_cell(event.pos)
                            if p in view.warehouse.pickups:
                                modal["pickup"] = view.warehouse.pickups.index(p)
                            if p in view.warehouse.deliveries:
                                modal["delivery"] = view.warehouse.deliveries.index(p)
                    continue
                panel_command = panel.handle(event, view)
                if panel_command:
                    enqueue(panel_command[0], **panel_command[1])
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, name in toolbar_boxes:
                        if rect.collidepoint(event.pos):
                            action(name)

            if future is None:
                should_step = not paused and modal is None and now - last_frame >= 1 / speeds[speed_index]
                if args.screenshot:
                    should_step = view.tick < args.screenshot_tick and not paused
                if commands or should_step or need_initial_plan:
                    batch = list(commands)
                    commands.clear()
                    single_step = any(op == "_step" for op, _ in batch)
                    batch = [(op, data) for op, data in batch if op != "_step"]
                    if single_step:
                        # Execute one step with an explicit post-step pause in worker.
                        def one_step(items=batch):
                            result, error = worker(items, True)
                            sim.paused = True
                            return sim.snapshot(), error
                        future = executor.submit(one_step)
                    else:
                        future = executor.submit(worker, batch, should_step and not batch)
                    need_initial_plan = False

            alpha = 1 if paused or args.screenshot else min(1, (now - last_frame) * speeds[speed_index])
            render(screen, fonts, view, alpha, panel.selected, future is not None)
            toolbar_boxes = []
            x = 24
            definitions = [
                ("pause", "继续" if paused else "暂停", 72), ("step", "单步", 65),
                ("speed", f"速度 {speeds[speed_index]}×", 89), ("random", "新增随机任务", 120),
                ("manual", "自定义任务", 105), ("auto", "自动生成 开" if view.auto else "自动生成 关", 120),
                ("retry", "重试规划", 95), ("save", "保存", 66), ("load", "加载回放", 95),
                ("reset", "重置", 66),
            ]
            for name, label, width in definitions:
                r = button(screen, fonts, (x, 78, width, 29), label,
                           active=name == "auto" and view.auto)
                toolbar_boxes.append((r, name))
                x += width + 7
            panel.draw(screen, fonts, view)
            if notice:
                text(screen, fonts.small, notice, (26, 834), (253, 109, 113), 1220)
            modal_boxes = []
            if modal is not None:
                shade = pygame.Surface(WINDOW, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 180))
                screen.blit(shade, (0, 0))
                box = pygame.Rect(424, 255, 448, 316)
                pygame.draw.rect(screen, CARD, box, border_radius=14)
                text(screen, fonts.title, "新增搬运任务", (449, 276))
                text(screen, fonts.small, "选择货架作业点、配送点和任务等级", (449, 317), MUTED)
                for row, key, title in ((0, "pickup", "取货点"), (1, "delivery", "配送点"), (2, "priority", "任务等级")):
                    y = 350 + row * 49
                    value = modal[key] if key == "priority" else modal[key] + 1
                    text(screen, fonts.body, f"{title}：{value}", (451, y + 7), TEXT)
                    for delta, label, bx in ((-1, "上一项", 663), (1, "下一项", 759)):
                        r = button(screen, fonts, (bx, y, 87, 33), label)
                        modal_boxes.append((r, (key, delta)))
                for name, label, bx in (("close", "返回", 451), ("create", "创建任务", 696)):
                    r = button(screen, fonts, (bx, 515, 150, 35), label, active=name == "create")
                    modal_boxes.append((r, name))
            pygame.display.flip()
            if args.screenshot:
                # Wait for initial planning before exporting an actual UI frame.
                if not need_initial_plan and future is None and view.tick >= args.screenshot_tick:
                    target = Path(args.screenshot)
                    if not target.is_absolute():
                        target = ROOT / target
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pygame.image.save(screen, target)
                    running = False
            clock.tick(60)
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
        save(sim)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="SDITADC three-robot warehouse preview")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--headless", action="store_true", help="Run without Pygame")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--load", help="Replay a saved scenario JSON")
    parser.add_argument("--screenshot", help="Export one UI frame and exit")
    parser.add_argument("--screenshot-tick", type=int, default=0, help="Advance ordinary simulation before screenshot")
    args = parser.parse_args()
    if args.headless:
        headless(args)
    else:
        graphical(args)


if __name__ == "__main__":
    main()
