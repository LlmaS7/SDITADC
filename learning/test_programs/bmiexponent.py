# smart_warehouse.py
# 智能仓储多机器人仿真 - 最小骨架
# 运行: python smart_warehouse.py
# 依赖: matplotlib (pip install matplotlib)

import random
from collections import deque
from dataclasses import dataclass, field
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as patches

# ============================================================
# 0. 全局参数
# ============================================================
W, H = 20, 15              # 地图宽高
NUM_ROBOTS = 3
MAX_STEPS = 600
TASK_ARRIVAL_PROB = 0.05   # 每个 tick 生成新任务的概率
SEED = 42
random.seed(SEED)

# 四邻域移动：下、上、右、左
DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


# ============================================================
# 1. 地图与环境
# ============================================================
class Environment:
    def __init__(self, w, h):
        self.W, self.H = w, h
        # 注意：必须用推导式，不能 [[0]*w]*h
        self.grid = [[0] * w for _ in range(h)]
        self._build_obstacles()

    def _build_obstacles(self):
        # 随机放一些货架作为障碍，边缘留通道
        for _ in range(30):
            x = random.randint(1, self.W - 2)
            y = random.randint(1, self.H - 2)
            self.grid[y][x] = 1

    def in_bounds(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H

    def is_free(self, x, y):
        return self.in_bounds(x, y) and self.grid[y][x] == 0

    def random_free_cell(self):
        while True:
            x = random.randint(0, self.W - 1)
            y = random.randint(0, self.H - 1)
            if self.is_free(x, y):
                return (x, y)


# ============================================================
# 2. 任务
# ============================================================
@dataclass
class Task:
    id: int
    start: tuple    # 取货点 (x, y)
    goal: tuple     # 送货点 (x, y)
    assigned: bool = False
    done: bool = False
    create_time: int = 0
    finish_time: int = -1


# ============================================================
# 3. 机器人
# ============================================================
@dataclass
class Robot:
    id: int
    pos: tuple
    state: str = "IDLE"        # IDLE / TO_PICKUP / TO_DELIVERY
    task: Task = None
    path: list = field(default_factory=list)   # 未来要走的格子列表
    busy_ticks: int = 0
    distance: int = 0

    def next_pos(self):
        """返回下一步想去的位置，没有则返回 None"""
        if self.path:
            return self.path[0]
        return None

    def step(self):
        """按路径走一步"""
        if self.path:
            self.pos = self.path.pop(0)
            self.distance += 1
        self.busy_ticks += 1


# ============================================================
# 4. 路径规划：BFS + 预约表避让
# ============================================================
def bfs(env, start, goal, reserved, current_time):
    """
    在时空预约表 reserved 约束下，找 start->goal 的路径。
    reserved: dict {(x,y,t): robot_id}
    返回: [(x,y), ...] 不含起点，含终点；找不到返回 []
    """
    if start == goal:
        return []
    q = deque()
    q.append((start, 0))
    visited = {start}
    parent = {}

    while q:
        (x, y), t = q.popleft()
        if (x, y) == goal:
            # 回溯
            path = []
            cur = (x, y)
            while cur != start:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return path

        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy
            nt = t + 1
            if not env.is_free(nx, ny):
                continue
            if (nx, ny) in visited:
                continue
            # 预约表检查：该格在该时刻不能被别人占
            if reserved.get((nx, ny, nt), None) is not None:
                continue
            visited.add((nx, ny))
            parent[(nx, ny)] = (x, y)
            q.append(((nx, ny), nt))
    return []


# ============================================================
# 5. 任务分配（贪心）
# ============================================================
def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def assign_tasks(robots, tasks, env):
    """给空闲机器人分配未分配任务（贪心：最近优先）"""
    idle_robots = [r for r in robots if r.state == "IDLE"]
    pending = [t for t in tasks if not t.assigned and not t.done]

    for r in idle_robots:
        if not pending:
            break
        # 找离机器人最近的待分配任务
        best = min(pending, key=lambda t: manhattan(r.pos, t.start))
        best.assigned = True
        r.task = best
        r.state = "TO_PICKUP"
        pending.remove(best)


# 6. 仿真世界
# ============================================================
class Simulation:
    def __init__(self):
        self.env = Environment(W, H)
        self.robots = []
        self.tasks = []
        self.task_counter = 0
        self.t = 0
        self.reserved = {}  # {(x,y,t): robot_id}
        self.metrics = {
            "completed": 0,
            "total_wait": 0,  # 任务从生成到完成的累计时间
            "collisions": 0,
        }
        self._init_robots()

    def _init_robots(self):
        used = set()
        for i in range(NUM_ROBOTS):
            while True:
                p = self.env.random_free_cell()
                if p not in used:
                    used.add(p)
                    break
            self.robots.append(Robot(id=i, pos=p))

    def spawn_tasks(self):
        if random.random() < TASK_ARRIVAL_PROB:
            s = self.env.random_free_cell()
            g = self.env.random_free_cell()
            if s == g:
                return
            task = Task(id=self.task_counter, start=s, goal=g, create_time=self.t)
            self.task_counter += 1
            self.tasks.append(task)

    def plan_for_robot(self, r):
        """为机器人规划下一步路径，写入 r.path"""
        if r.path:
            return
        if r.state == "TO_PICKUP":
            target = r.task.start
        elif r.state == "TO_DELIVERY":
            target = r.task.goal
        else:
            return

        path = bfs(self.env, r.pos, target, self.reserved, self.t)
        if not path:
            return
        r.path = path
        # 把自己的路径写进预约表（简化：只预约到终点时刻）
        t = self.t
        for (x, y) in r.path:
            t += 1
            self.reserved[(x, y, t)] = r.id

    def resolve_conflicts(self):
        """
        简单避让：如果两个机器人下一步想去同一格，编号大的等待。
        （更严谨的做法在规划阶段就避让，这里做兜底。）
        """
        desire = {}
        for r in self.robots:
            nxt = r.next_pos()
            if nxt is not None:
                desire.setdefault(nxt, []).append(r)
        for pos, rs in desire.items():
            if len(rs) > 1:
                # 保留 id 最小的，其他等待（清空这一步）
                rs.sort(key=lambda r: r.id)
                for r in rs[1:]:
                    r.path = []  # 等待，下个 tick 重新规划
                    self.metrics["collisions"] += 0  # 已避免，不计碰撞

    def step(self):
        self.t += 1
        self.spawn_tasks()
        assign_tasks(self.robots, self.tasks, self.env)

        # 1. 规划
        for r in self.robots:
            self.plan_for_robot(r)

        # 2. 冲突兜底
        self.resolve_conflicts()

        # 3. 执行
        for r in self.robots:
            r.step()

        # 4. 状态转换
        for r in self.robots:
            if r.state == "TO_PICKUP" and r.pos == r.task.start:
                r.state = "TO_DELIVERY"
                r.path = []
            elif r.state == "TO_DELIVERY" and r.pos == r.task.goal:
                r.task.done = True
                r.task.finish_time = self.t
                self.metrics["completed"] += 1
                self.metrics["total_wait"] += (self.t - r.task.create_time)
                r.task = None
                r.state = "IDLE"
                r.path = []

        # 5. 清理已预约的过期时间
        self.reserved = {k: v for k, v in self.reserved.items() if k[2] > self.t}


# ============================================================
# 7. 可视化
# ============================================================
COLORS = ["red", "blue", "green"]


def run_visualization(sim):
    fig, ax = plt.subplots(figsize=(9, 7))

    def draw(frame):
        ax.clear()
        ax.set_xlim(-0.5, sim.env.W - 0.5)
        ax.set_ylim(-0.5, sim.env.H - 0.5)
        ax.set_aspect("equal")
        ax.set_title(f"t = {sim.t} | completed = {sim.metrics['completed']}")

        # 画障碍
        for y in range(sim.env.H):
            for x in range(sim.env.W):
                if sim.env.grid[y][x] == 1:
                    ax.add_patch(patches.Rectangle((x - 0.5, y - 0.5), 1, 1,
                                                   color="gray"))

        # 画任务点
        for task in sim.tasks:
            if task.done:
                continue
            sx, sy = task.start
            gx, gy = task.goal
            ax.plot(sx, sy, marker="*", color="orange", markersize=12)
            ax.plot(gx, gy, marker="X", color="purple", markersize=10)


# 画机器人
        for r in sim.robots:
            x, y = r.pos
            ax.add_patch(patches.Circle((x, y), 0.35,
                                         color=COLORS[r.id % len(COLORS)]))
            ax.text(x, y, str(r.id), color="white",
                    ha="center", va="center", fontsize=9, weight="bold")
            # 画路径
            if r.path:
                px = [x] + [p[0] for p in r.path]
                py = [y] + [p[1] for p in r.path]
                ax.plot(px, py, "--", color=COLORS[r.id % len(COLORS)],
                        alpha=0.5)

        # 仿真推进一步
        sim.step()

    ani = animation.FuncAnimation(fig, draw, frames=MAX_STEPS,
                                  interval=80, repeat=False)
    plt.show()
    return ani


# ============================================================
# 8. 主程序
# ============================================================
if __name__ == "__main__":
    sim = Simulation()
    print("初始机器人位置:", [r.pos for r in sim.robots])
    print("障碍格数:", sum(sum(row) for row in sim.env.grid))

    run_visualization(sim)

    # 打印最终指标
    print("\n===== 指标统计 =====")
    print("完成任务数:", sim.metrics["completed"])
    print("生成任务数:", sim.task_counter)
    if sim.metrics["completed"] > 0:
        print("平均完成时间: %.2f tick" %
              (sim.metrics["total_wait"] / sim.metrics["completed"]))
    for r in sim.robots:
        util = r.busy_ticks / max(1, sim.t)
        print(f"机器人 {r.id}: 行走距离={r.distance}, 利用率={util:.2%}")
