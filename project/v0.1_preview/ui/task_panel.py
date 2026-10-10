"""Scrollable complete task list, selection detail and command hitboxes."""
import pygame
from config import WAIT_WARNING
from models import TASK_LABELS, FINISHED
from ui.widgets import CARD, TEXT, MUTED, ACCENT, RED, button, text


class TaskPanel:
    def __init__(self):
        self.selected = None
        self.scroll = 0
        self.filter = "all"
        self.hitboxes = []
        self.list_rect = pygame.Rect(880, 198, 392, 363)

    def tasks(self, view):
        values = [t for t in view.tasks.values() if t.status != "cancelled"]
        if self.filter == "active":
            values = [t for t in values if t.status not in FINISHED]
        elif self.filter == "completed":
            values = [t for t in values if t.status in FINISHED]
        return sorted(values, key=lambda t: t.id)

    def draw(self, surface, fonts, view):
        self.hitboxes = []
        rect = pygame.Rect(868, 116, 416, 717)
        pygame.draw.rect(surface, CARD, rect, border_radius=12)
        text(surface, fonts.medium, "任务中心", (884, 131))
        total = sum(t.status != "cancelled" for t in view.tasks.values())
        text(surface, fonts.small, f"完成 {view.metrics['completed']} / {total} · 待接手 {view.metrics['pending']}",
             (984, 135), MUTED)
        for index, (key, label) in enumerate((("all", "全部"), ("active", "未完成"), ("completed", "已结束"))):
            r = button(surface, fonts, (882 + index * 95, 163, 86, 28), label, active=self.filter == key)
            self.hitboxes.append((r, ("filter", key)))
        values = self.tasks(view)
        if self.selected not in {t.id for t in values}:
            self.selected = values[0].id if values else None
        row_height = 82
        self.scroll = max(0, min(self.scroll, max(0, len(values) * row_height - self.list_rect.height)))
        old_clip = surface.get_clip()
        surface.set_clip(self.list_rect)
        for index, task in enumerate(values):
            row = pygame.Rect(884, self.list_rect.y + index * row_height - self.scroll, 380, 75)
            if not row.colliderect(self.list_rect):
                continue
            selected = task.id == self.selected
            pygame.draw.rect(surface, (43, 64, 83) if selected else (34, 47, 66), row, border_radius=7)
            if selected:
                pygame.draw.rect(surface, ACCENT, row, 1, border_radius=7)
            color = RED if task.priority == 5 else ACCENT
            owner = f"R{task.robot_id}" if task.robot_id else "—"
            text(surface, fonts.body, f"T{task.id:03d}  {'紧急' if task.priority == 5 else '等级 ' + str(task.priority)}", (row.x + 10, row.y + 7), color)
            text(surface, fonts.small, f"{TASK_LABELS[task.status]} · {owner}", (row.x + 211, row.y + 10), TEXT, 155)
            p = view.warehouse.pickups.index(task.pickup) + 1
            d = view.warehouse.deliveries.index(task.delivery) + 1
            text(surface, fonts.small, f"取货点 {p:02d} → 配送点 D{d}", (row.x + 10, row.y + 31), MUTED)
            age = (task.completed_at or view.tick) - task.created_at
            warning = task.status in ("pending", "reserved") and age >= WAIT_WARNING
            tail = " · 等待较久" if warning else ""
            text(surface, fonts.small, f"已用时 {age} 步{tail}", (row.x + 10, row.y + 53), RED if warning else MUTED)
            self.hitboxes.append((row.clip(self.list_rect), ("select", task.id)))
        surface.set_clip(old_clip)
        if len(values) * row_height > self.list_rect.height:
            bar_height = max(24, int(self.list_rect.height ** 2 / (len(values) * row_height)))
            offset = int((self.list_rect.height - bar_height) * self.scroll /
                         (len(values) * row_height - self.list_rect.height))
            pygame.draw.rect(surface, (111, 137, 164), (1268, self.list_rect.y + offset, 3, bar_height), border_radius=2)
        task = view.tasks.get(self.selected)
        pygame.draw.line(surface, (64, 81, 101), (884, 571), (1267, 571))
        if task:
            text(surface, fonts.body, f"选中 T{task.id:03d} · {TASK_LABELS[task.status]}", (884, 583))
            text(surface, fonts.small, f"取 {task.pickup} → 送 {task.delivery} · 抢占 {task.preemptions} 次", (884, 608), MUTED)
            if task.status == "reserved":
                text(surface, fonts.small, f"R{task.robot_id} 完成当前搬运后接手", (884, 630), ACCENT)
            elif task.priority == 5 and task.status == "pending":
                text(surface, fonts.small, "暂无可接手机器人，等待安全释放", (884, 630), RED)
            else:
                text(surface, fonts.small, "点击任务可高亮取送位置", (884, 630), MUTED)
            for rect, label, action, disabled, danger in (
                ((884, 655, 106, 33), "提升一级", "raise", task.priority == 5 or task.status in FINISHED, False),
                ((998, 655, 132, 33), "设为紧急", "urgent", task.priority == 5 or task.status in FINISHED, True),
                ((1138, 655, 127, 33), "取消任务", "cancel", task.status not in ("pending", "reserved", "to_pickup"), False),
            ):
                r = button(surface, fonts, rect, label, danger=danger, disabled=disabled)
                if not disabled:
                    self.hitboxes.append((r, (action, task.id)))
        m = view.metrics
        text(surface, fonts.small, f"平均完成 {m['avg_completion']:.1f} 步   平均取货等待 {m['avg_wait']:.1f} 步", (884, 712), MUTED)
        text(surface, fonts.small, f"移动 {m['distance']} 格   路径等待 {m['waits']} 步   抢占 {m['preemptions']} 次", (884, 735), MUTED)
        text(surface, fonts.small, f"规划 {m['last_plan_ms']:.1f} ms   CBS 节点 {m['cbs_nodes']}", (884, 758), MUTED)
        text(surface, fonts.small, f"本轮预计完成时间和：{view.assignment.get('eta_sum', 0)} 步", (884, 782), ACCENT)
        text(surface, fonts.small, "分配精确最优；代价不含未来冲突等待", (884, 804), MUTED)

    def handle(self, event, view):
        if event.type == pygame.MOUSEWHEEL and self.list_rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll -= event.y * 54
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in reversed(self.hitboxes):
                if rect.collidepoint(event.pos):
                    op, value = action
                    if op == "select":
                        self.selected = value
                    elif op == "filter":
                        self.filter, self.scroll = value, 0
                    elif op in ("raise", "urgent"):
                        return ("priority", {"task_id": value, "priority":
                                5 if op == "urgent" else view.tasks[value].priority + 1})
                    elif op == "cancel":
                        return ("cancel", {"task_id": value})
                    return None
        return None
