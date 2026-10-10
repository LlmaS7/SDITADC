"""Warehouse and smooth robot interpolation; planner coordinates remain integers."""
import pygame
from config import CELL, ROBOT_COLORS, WAIT_WARNING
from models import ROBOT_LABELS
from ui.widgets import BG, CARD, TEXT, MUTED, ACCENT, RED, text

ORIGIN = (24, 150)


def center(p):
    return (ORIGIN[0] + (p[0] + .5) * CELL, ORIGIN[1] + (p[1] + .5) * CELL)


def map_cell(position):
    return ((position[0] - ORIGIN[0]) // CELL, (position[1] - ORIGIN[1]) // CELL)


def render(surface, fonts, view, alpha=1.0, selected=None, busy=False):
    surface.fill(BG)
    text(surface, fonts.title, "SDITADC  /  三机仓库协作", (24, 16))
    text(surface, fonts.body, "v0.1 preview   ·   普通场景   ·   精确任务匹配 + CBS 路径协调", (25, 55), MUTED)
    text(surface, fonts.body, f"时刻 {view.tick:04d}  ·  种子 {view.warehouse.seed}", (900, 25), ACCENT)
    status = "规划中，操作可继续" if busy else ("已暂停" if view.paused else "运行中")
    text(surface, fonts.body, status + ("  /  输入回放" if view.replaying else ""), (900, 55), MUTED)
    w = view.warehouse
    for y in range(w.height):
        for x in range(w.width):
            p = (x, y)
            rect = pygame.Rect(ORIGIN[0] + x * CELL, ORIGIN[1] + y * CELL, CELL, CELL)
            if p in w.shelves:
                color = (72, 89, 112)
            elif p in w.obstacles:
                color = (156, 128, 98)
            elif p in w.blocked:
                color = (43, 57, 75)
            else:
                color = (229, 237, 244)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (204, 215, 226) if w.is_open(p) else BG, rect, 1)
            if p in w.obstacles:
                pygame.draw.line(surface, (89, 69, 53), rect.topleft, rect.bottomright, 2)
                pygame.draw.line(surface, (89, 69, 53), rect.topright, rect.bottomleft, 2)
    for index, p in enumerate(w.pickups):
        r = pygame.Rect(0, 0, CELL - 5, CELL - 5)
        r.center = center(p)
        pygame.draw.rect(surface, (165, 210, 226), r, border_radius=3)
        text(surface, fonts.small, f"{index + 1}", (r.x + 3, r.y + 2), (34, 91, 117))
    for index, p in enumerate(w.deliveries):
        r = pygame.Rect(0, 0, CELL - 4, CELL - 4)
        r.center = center(p)
        pygame.draw.rect(surface, (164, 216, 190), r, border_radius=3)
        text(surface, fonts.small, f"D{index + 1}", (r.x + 2, r.y + 2), (33, 99, 70))
    for p in w.parking:
        r = pygame.Rect(0, 0, CELL - 5, CELL - 5)
        r.center = center(p)
        pygame.draw.rect(surface, (177, 182, 215), r, border_radius=3)
        text(surface, fonts.small, "P", (r.x + 5, r.y + 2), (71, 69, 117))
    for robot in view.robots:
        color = ROBOT_COLORS[robot.id - 1]
        if len(robot.path) > 1:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.lines(overlay, (*color, 135), False,
                              [center(p) for p in robot.path], 3)
            surface.blit(overlay, (0, 0))
    task = view.tasks.get(selected)
    if task and task.status != "cancelled":
        for p, color, marker in ((task.pickup, (26, 140, 202), "取"),
                                  (task.delivery, (27, 158, 99), "送")):
            pygame.draw.circle(surface, color, center(p), CELL // 2 + 2, 3)
            if marker != "取":
                text(surface, fonts.small, marker, (center(p)[0] - 6, center(p)[1] - 8), color)
    for robot in view.robots:
        px = robot.previous[0] + (robot.position[0] - robot.previous[0]) * alpha
        py = robot.previous[1] + (robot.position[1] - robot.previous[1]) * alpha
        c = center((px, py))
        color = ROBOT_COLORS[robot.id - 1]
        pygame.draw.circle(surface, (38, 50, 64), (c[0] + 1, c[1] + 2), 12)
        pygame.draw.circle(surface, color, c, 10)
        label = fonts.small.render(str(robot.id), True, BG)
        surface.blit(label, label.get_rect(center=c))
        if robot.loaded:
            pygame.draw.rect(surface, (248, 239, 193), (c[0] + 4, c[1] - 13, 8, 7), border_radius=2)
        current = view.tasks.get(robot.task_id)
        if current and current.priority == 5:
            pygame.draw.circle(surface, RED, c, 14, 2)
    if task and task.status != "cancelled":
        # Keep the pickup number readable and draw its label above the marker,
        # after routes/robots so the badge itself is not covered.
        c = center(task.pickup)
        label = fonts.small.render("取", True, (26, 140, 202))
        badge = label.get_rect(midbottom=(round(c[0]), round(c[1]) - CELL // 2 - 5))
        background = badge.inflate(8, 4)
        pygame.draw.rect(surface, (240, 247, 251), background, border_radius=4)
        pygame.draw.rect(surface, (26, 140, 202), background, 1, border_radius=4)
        surface.blit(label, badge)
    # Robot strip beneath the map.
    for index, robot in enumerate(view.robots):
        rect = pygame.Rect(24 + index * 280, 790, 270, 43)
        pygame.draw.rect(surface, CARD, rect, border_radius=7)
        color = ROBOT_COLORS[index]
        text(surface, fonts.body, f"R{robot.id}  {ROBOT_LABELS[robot.phase]}", (rect.x + 10, rect.y + 5), color)
        current = f"T{robot.task_id:03d}" if robot.task_id else "—"
        upcoming = f" · 接手 T{robot.next_task_id:03d}" if robot.next_task_id else ""
        text(surface, fonts.small, f"{current}{upcoming} · 完成 {robot.completed}", (rect.x + 10, rect.y + 25), MUTED, 250)
    # Compact, readable legend and status above the map.
    text(surface, fonts.small, "蓝格：取货点   绿格：配送点   紫格：停车位   棕色：随机障碍", (24, 124), MUTED)
    text(surface, fonts.small, view.message, (24, 106), ACCENT, 820)
