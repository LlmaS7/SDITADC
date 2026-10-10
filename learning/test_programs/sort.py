import heapq
import copy
import os
import time


# ==========================================
# 1. 单机器人 A* (纯 Python 列表实现)
# ==========================================
class AStar:
    def __init__(self, grid):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start, goal):
        if self.grid[start[0]][start[1]] == 1 or self.grid[goal[0]][goal[1]] == 1:
            return None
        open_set = [(self.heuristic(start, goal), 0, start)]
        g_score = {start: 0}
        came_from = {}
        expanded = set()

        while open_set:
            _, current_g, current = heapq.heappop(open_set)
            if current in expanded: continue
            expanded.add(current)

            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]

            for dr, dc in self.directions:
                neighbor = (current[0] + dr, current[1] + dc)
                if not (0 <= neighbor[0] < self.rows and 0 <= neighbor[1] < self.cols): continue
                if self.grid[neighbor[0]][neighbor[1]] == 1: continue

                tentative_g = current_g + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self.heuristic(neighbor, goal)
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor))
        return None


# ==========================================
# 2. 时空 A* (纯 Python 实现)
# ==========================================
class SpaceTimeAStar:
    def __init__(self, grid, reservation_table=None):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.reservation_table = reservation_table or {}
        self.directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start, goal, max_time=200):
        if self.grid[start[0]][start[1]] == 1 or self.grid[goal[0]][goal[1]] == 1:
            return None
        start_state = (start[0], start[1], 0)
        open_set = [(self.heuristic(start, goal), 0, start_state)]
        g_score = {start_state: 0}
        came_from = {}
        expanded = set()

        while open_set:
            _, current_g, current = heapq.heappop(open_set)
            if current in expanded: continue
            expanded.add(current)
            r, c, t = current

            if (r, c) == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_state)
                return path[::-1]

            if t >= max_time: continue

            for dr, dc in self.directions:
                nr, nc = r + dr, c + dc
                nt = t + 1
                if not (0 <= nr < self.rows and 0 <= nc < self.cols): continue
                if self.grid[nr][nc] == 1: continue
                if self.reservation_table.get((nr, nc, nt), False): continue

                neighbor = (nr, nc, nt)
                tentative_g = current_g + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self.heuristic((nr, nc), goal)
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor))
        return None


# ==========================================
# 3. 预约表
# ==========================================
class ReservationTable:
    def __init__(self):
        self.table = {}

    def reserve(self, path, agent_id):
        for r, c, t in path:
            self.table[(r, c, t)] = agent_id


# ==========================================
# 4. CBS 算法
# ==========================================
class CBSNode:
    def __init__(self, constraints, paths, cost):
        self.constraints = constraints
        self.paths = paths
        self.cost = cost

    def __lt__(self, other):
        return self.cost < other.cost


class CBS:
    def __init__(self, grid, agents):
        self.grid = grid
        self.agents = agents
        self.rows = len(grid)
        self.cols = len(grid[0])

    def find_path_with_constraints(self, agent_id, start, goal, constraints, max_time=200):
        reservation = {}
        for constraint in constraints:
            if len(constraint) == 3:
                r, c, t = constraint
                reservation[(r, c, t)] = True
        sta = SpaceTimeAStar(self.grid, reservation)
        return sta.find_path(start, goal, max_time)

    def detect_conflict(self, paths):
        agent_ids = list(paths.keys())
        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                a1, a2 = agent_ids[i], agent_ids[j]
                path1, path2 = paths[a1], paths[a2]
                min_len = min(len(path1), len(path2))
                for k in range(min_len):
                    r1, c1, t1 = path1[k]
                    r2, c2, t2 = path2[k]
                    if r1 == r2 and c1 == c2 and t1 == t2:
                        return (a1, a2, 'vertex', (r1, c1, t1))
                for k in range(min_len - 1):
                    r1, c1, t1 = path1[k]
                    r1_next, c1_next, t1_next = path1[k + 1]
                    r2, c2, t2 = path2[k]
                    r2_next, c2_next, t2_next = path2[k + 1]
                    if t1 == t2 and t1_next == t2_next:
                        if r1 == r2_next and c1 == c2_next and r2 == r1_next and c2 == c1_next:
                            return (a1, a2, 'edge', (r1, c1, r1_next, c1_next, t1))
        return None

    def solve(self, max_expand=1000):
        num_agents = len(self.agents)
        root_paths = {}
        root_constraints = {i: set() for i in range(num_agents)}
        for i, (start, goal) in enumerate(self.agents):
            path = self.find_path_with_constraints(i, start, goal, set())
            if path is None: return None
            root_paths[i] = path
        root_cost = sum(len(p) for p in root_paths.values())
        root = CBSNode(root_constraints, root_paths, root_cost)
        open_list = [root]
        expanded = 0
        while open_list and expanded < max_expand:
            node = heapq.heappop(open_list)
            expanded += 1
            conflict = self.detect_conflict(node.paths)
            if conflict is None:
                return node.paths
            a1, a2, ctype, cinfo = conflict
            for agent in [a1, a2]:
                new_constraints = copy.deepcopy(node.constraints)
                if ctype == 'vertex':
                    r, c, t = cinfo
                    new_constraints[agent].add((r, c, t))
                elif ctype == 'edge':
                    r1, c1, r2, c2, t = cinfo
                    new_constraints[agent].add((r1, c1, t))
                    new_constraints[agent].add((r2, c2, t + 1))
                new_paths = copy.deepcopy(node.paths)
                new_path = self.find_path_with_constraints(agent, self.agents[agent][0], self.agents[agent][1],
                                                           new_constraints[agent])
                if new_path is not None:
                    new_paths[agent] = new_path
                    new_cost = sum(len(p) for p in new_paths.values())
                    heapq.heappush(open_list, CBSNode(new_constraints, new_paths, new_cost))
        return None


# ==========================================
# 5. 优先级规划
# ==========================================
class PrioritizedPlanner:
    def __init__(self, grid):
        self.grid = grid

    def plan(self, agents):
        agent_order = sorted(range(len(agents)), key=lambda i: abs(agents[i][0][0] - agents[i][1][0]) + abs(
            agents[i][0][1] - agents[i][1][1]), reverse=True)
        reservation = ReservationTable()
        paths = {}
        for agent_id in agent_order:
            start, goal = agents[agent_id]
            res_dict = {k: True for k, v in reservation.table.items() if v != agent_id}
            sta = SpaceTimeAStar(self.grid, res_dict)
            path = sta.find_path(start, goal)
            if path is None: return None
            paths[agent_id] = path
            reservation.reserve(path, agent_id)
        return paths


# ==========================================
# 6. 任务分配（纯 Python 贪心算法代替 scipy）
# ==========================================
class TaskAllocator:
    def __init__(self, robots, tasks):
        self.robots = robots
        self.tasks = tasks

    def allocate_greedy(self):
        if not self.robots or not self.tasks: return []
        assigned_tasks = set()
        result = []
        for i, (r1, c1) in enumerate(self.robots):
            best_j, best_cost = None, float('inf')
            for j, (r2, c2) in enumerate(self.tasks):
                if j not in assigned_tasks:
                    cost = abs(r1 - r2) + abs(c1 - c2)
                    if cost < best_cost:
                        best_cost, best_j = cost, j
            if best_j is not None:
                assigned_tasks.add(best_j)
                result.append((i, best_j, best_cost))
        return result


# ==========================================
# 7. 控制台仿真器（纯文本动画）
# ==========================================
class ConsoleSimulator:
    def __init__(self, grid, rows, cols):
        self.grid = grid
        self.rows = rows
        self.cols = cols

    def clear_screen(self):
        # 清除控制台屏幕（跨平台）
        os.system('cls' if os.name == 'nt' else 'clear')

    def draw(self, current_positions, current_t, max_t):
        self.clear_screen()
        print(f"=== 仓库多机器人仿真 | 时间步: {current_t}/{max_t} ===")
        print("说明: # = 障碍物, . = 空地, 数字 0-3 = 机器人\n")

        # 绘制网格
        for r in range(self.rows):
            row_str = ""
            for c in range(self.cols):
                if self.grid[r][c] == 1:
                    row_str += " # "
                else:
                    # 检查当前格子是否有机器人
                    agent_here = None
                    for aid, (ar, ac) in current_positions.items():
                        if ar == r and ac == c:
                            agent_here = aid
                            break
                    if agent_here is not None:
                        row_str += f" {agent_here} "
                    else:
                        row_str += " . "
            print(row_str)
        print("-" * 40)

    def run(self, paths, agents, fps=2):
        max_t = max(len(p) for p in paths.values())
        for t in range(max_t):
            current_positions = {}
            for aid in agents:
                path = paths[aid]
                r, c, _ = path[t] if t < len(path) else path[-1]
                current_positions[aid] = (r, c)
            self.draw(current_positions, t, max_t)
            time.sleep(1.0 / fps)


# ==========================================
# 8. 主程序
# ==========================================
def create_warehouse_grid(rows=12, cols=12):
    # 纯 Python 二维列表初始化
    grid = [[0 for _ in range(cols)] for _ in range(rows)]
    for r in range(2, rows - 2, 4):
        for c in range(2, cols - 2, 4):
            grid[r][c] = 1
            grid[r + 1][c] = 1
            grid[r][c + 1] = 1
            grid[r + 1][c + 1] = 1
    return grid


def main():
    rows, cols = 12, 12
    grid = create_warehouse_grid(rows, cols)

    print("仓库地图 (0=空地, 1=障碍物):")
    for row in grid:
        print(" ".join(str(x) for x in row))

    # 机器人起终点
    agents = [
        ((0, 0), (11, 11)),
        ((0, 11), (11, 0)),
        ((11, 0), (0, 11)),
        ((11, 11), (0, 0)),
    ]

    print(f"\n机器人数量: {len(agents)}")

    # --- 优先级规划 ---
    print("\n--- 优先级规划 ---")
    pp = PrioritizedPlanner(grid)
    paths_pp = pp.plan(agents)
    if paths_pp:
        print(f"优先级规划成功! 总路径长度: {sum(len(p) for p in paths_pp.values())}")
    else:
        print("优先级规划失败")

    # --- CBS 规划 ---
    print("\n--- CBS 规划 ---")
    cbs = CBS(grid, agents)
    paths_cbs = cbs.solve(max_expand=500)
    if paths_cbs:
        print(f"CBS 规划成功! 总路径长度: {sum(len(p) for p in paths_cbs.values())}")
    else:
        print("CBS 规划失败")

    # --- 任务分配 ---
    print("\n--- 任务分配 (贪心算法) ---")
    robot_positions = [s for s, g in agents]
    task_positions = [g for s, g in agents]
    allocator = TaskAllocator(robot_positions, task_positions)
    result = allocator.allocate_greedy()
    for r, t, c in result:
        print(f"  机器人{r} -> 任务{t} (距离={c})")

    # --- 纯文本动画仿真 ---
    if paths_cbs:
        print("\n启动控制台仿真... (按 Ctrl+C 可中断)")
        time.sleep(2)  # 缓冲2秒
        goals = {i: agents[i][1] for i in range(len(agents))}
        agent_ids = list(paths_cbs.keys())
        sim = ConsoleSimulator(grid, rows, cols)
        # fps=3 表示每秒刷新3帧
        sim.run(paths_cbs, agent_ids, fps=3)


if __name__ == "__main__":
    main()