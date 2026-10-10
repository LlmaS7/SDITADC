import heapq
import sys
import time
import random
import colorsys
import numpy as np
import pygame


# ==========================================
# 工具函数：安全获取中文字体
# ==========================================
def get_font(size):
    for font_name in ['microsoftyahei', 'simhei', 'simsun', 'pingfang', 'arialunicode']:
        try:
            font = pygame.font.SysFont(font_name, size)
            font.render("测试", True, (0, 0, 0))
            return font
        except:
            continue
    return pygame.font.Font(None, size)


# ==========================================
# 1. 算法层：纯单机器人 A*
# ==========================================
class AStar:
    def __init__(self, grid):
        self.grid = grid
        self.rows, self.cols = grid.shape
        self.directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start, goal):
        if self.grid[start] == 1 or self.grid[goal] == 1:
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
                if self.grid[neighbor] == 1: continue

                tentative_g = current_g + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self.heuristic(neighbor, goal)
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor))
        return None


# ==========================================
# 2. 调度层：任务分配
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
# 3. 核心重规划函数（纯 A*）
# ==========================================
def replan_all(grid, agents):
    all_results = {}
    paths = {}

    start_time = time.time()

    for i, (start, goal) in enumerate(agents):
        astar = AStar(grid)
        path_2d = astar.find_path(start, goal)

        if path_2d:
            path_3d = [(r, c, t) for t, (r, c) in enumerate(path_2d)]
            paths[i] = path_3d
        else:
            print(f"警告：机器人 {i} 无法找到从 {start} 到 {goal} 的路径！(可能被障碍物堵死)")

    time_cost = time.time() - start_time

    if paths:
        all_results["纯 A* (独立寻路)"] = {
            "paths": paths,
            "cost": sum(len(p) for p in paths.values()),
            "time": time_cost
        }

    return all_results


# ==========================================
# 4. 可视化层：Pygame 仿真器
# ==========================================
class PygameVisualizer:
    def __init__(self, grid, cell_size=40, fps=8, num_agents=4):
        self.grid = grid
        self.rows, self.cols = grid.shape
        self.cell_size = cell_size
        self.fps = fps
        self.ui_panel_width = 280
        self.width = self.cols * cell_size + self.ui_panel_width
        self.height = self.rows * cell_size

        self.COLOR_BG = (245, 245, 245)
        self.COLOR_FREE = (255, 255, 255)
        self.COLOR_OBSTACLE = (80, 80, 80)
        self.COLOR_GRID = (220, 220, 220)

        self.COLOR_AGENT = []
        self.COLOR_GOAL = []
        self.COLOR_PATH = []
        for i in range(num_agents):
            hue = i / max(1, num_agents)
            rgb = colorsys.hsv_to_rgb(hue, 0.85, 0.9)
            agent_color = tuple(int(x * 255) for x in rgb)
            self.COLOR_AGENT.append(agent_color)

            goal_color = tuple(min(255, int(x + (255 - x) * 0.7)) for x in agent_color)
            self.COLOR_GOAL.append(goal_color)

            path_color = tuple(int(x * 0.7) for x in agent_color)
            self.COLOR_PATH.append(path_color)

        self.COLOR_TEXT = (50, 50, 50)

    def screen_to_grid(self, pos):
        x, y = pos
        if x < self.cols * self.cell_size:
            return (y // self.cell_size, x // self.cell_size)
        return None

    def draw_grid(self, screen):
        for r in range(self.rows):
            for c in range(self.cols):
                rect = pygame.Rect(c * self.cell_size, r * self.cell_size, self.cell_size, self.cell_size)
                color = self.COLOR_OBSTACLE if self.grid[r, c] == 1 else self.COLOR_FREE
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, self.COLOR_GRID, rect, 1)

    def draw_manual_path(self, screen, manual_paths, active_agent):
        if active_agent in manual_paths:
            color = self.COLOR_PATH[active_agent % len(self.COLOR_PATH)]
            path = manual_paths[active_agent]
            for i in range(len(path) - 1):
                r1, c1 = path[i]
                r2, c2 = path[i + 1]
                start_pos = (c1 * self.cell_size + self.cell_size // 2, r1 * self.cell_size + self.cell_size // 2)
                end_pos = (c2 * self.cell_size + self.cell_size // 2, r2 * self.cell_size + self.cell_size // 2)
                pygame.draw.line(screen, color, start_pos, end_pos, 3)
            if path:
                r, c = path[0]
                pygame.draw.circle(screen, (0, 255, 0),
                                   (c * self.cell_size + self.cell_size // 2, r * self.cell_size + self.cell_size // 2),
                                   6)

    def draw_agents(self, screen, current_positions, goals, agent_ids, history_paths):
        for aid in agent_ids:
            color_idx = aid % len(self.COLOR_PATH)
            path_color = self.COLOR_PATH[color_idx]
            for (r, c) in history_paths.get(aid, []):
                path_rect = pygame.Rect(c * self.cell_size + self.cell_size // 4,
                                        r * self.cell_size + self.cell_size // 4,
                                        self.cell_size // 2, self.cell_size // 2)
                pygame.draw.rect(screen, path_color, path_rect)

        for aid in agent_ids:
            if aid not in current_positions: continue
            r, c = current_positions[aid]
            gr, gc = goals[aid]
            color_idx = aid % len(self.COLOR_AGENT)

            goal_rect = pygame.Rect(gc * self.cell_size + 4, gr * self.cell_size + 4,
                                    self.cell_size - 8, self.cell_size - 8)
            pygame.draw.rect(screen, self.COLOR_GOAL[color_idx], goal_rect, 3)

            center = (int(c * self.cell_size + self.cell_size / 2), int(r * self.cell_size + self.cell_size / 2))
            pygame.draw.circle(screen, self.COLOR_AGENT[color_idx], center, self.cell_size // 2 - 4)
            font = get_font(20)
            text = font.render(str(aid), True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=center))

    def draw_ui(self, screen, current_t, max_t, algo_name, algo_info, paused, alloc_result, manual_mode, active_agent):
        ui_rect = pygame.Rect(self.cols * self.cell_size, 0, self.ui_panel_width, self.height)
        pygame.draw.rect(screen, (230, 230, 230), ui_rect)
        pygame.draw.line(screen, (200, 200, 200), (self.cols * self.cell_size, 0),
                         (self.cols * self.cell_size, self.height), 2)

        font_title = get_font(28)
        font_text = get_font(22)
        font_small = get_font(18)

        title = font_title.render("纯 A* 仿真", True, self.COLOR_TEXT)
        screen.blit(title, (self.cols * self.cell_size + 20, 20))

        mode_text = font_text.render(f"模式: {'手动画线' if manual_mode else '算法自动'}", True,
                                     (200, 50, 50) if manual_mode else (50, 150, 50))
        screen.blit(mode_text, (self.cols * self.cell_size + 20, 60))

        if manual_mode:
            agent_text = font_text.render(f"控制机器人: {active_agent}", True, self.COLOR_TEXT)
            screen.blit(agent_text, (self.cols * self.cell_size + 20, 90))
            tip_text = font_small.render("左键拖动鼠标画线", True, (100, 100, 100))
            screen.blit(tip_text, (self.cols * self.cell_size + 20, 120))
        else:
            algo_text = font_text.render(f"算法: {algo_name}", True, (200, 50, 50))
            screen.blit(algo_text, (self.cols * self.cell_size + 20, 90))
            if algo_info:
                cost_text = font_text.render(f"总路径长度: {algo_info['cost']}", True, self.COLOR_TEXT)
                time_text = font_text.render(f"计算耗时: {algo_info['time']:.4f}s", True, self.COLOR_TEXT)
                screen.blit(cost_text, (self.cols * self.cell_size + 20, 120))
                screen.blit(time_text, (self.cols * self.cell_size + 20, 150))

        time_step_text = font_text.render(f"时间步: {current_t} / {max_t}", True, self.COLOR_TEXT)
        screen.blit(time_step_text, (self.cols * self.cell_size + 20, 190))

        status = "已暂停" if paused else "运行中"
        status_color = (255, 100, 100) if paused else (100, 200, 100)
        status_text = font_text.render(f"状态: {status}", True, status_color)
        screen.blit(status_text, (self.cols * self.cell_size + 20, 220))

        alloc_title = font_text.render("任务分配:", True, self.COLOR_TEXT)
        screen.blit(alloc_title, (self.cols * self.cell_size + 20, 260))
        for i, (r, t, cost) in enumerate(alloc_result):
            text = font_small.render(f"机器人{r} -> 任务{t}", True, self.COLOR_TEXT)
            screen.blit(text, (self.cols * self.cell_size + 20, 290 + i * 22))

        hint_y = self.height - 200
        hints = [
            "操作说明:",
            "M: 切换 自动/手动 模式",
            "1,2,3,4: 切换控制机器人",
            "手动模式: 左键拖动 画路线",
            "自动模式: 左键画障碍 | 右键擦除",
            "C: 清空障碍 | Enter: 重新规划",
            "空格: 暂停 | R: 重置动画",
            "ESC: 退出"
        ]
        for i, hint in enumerate(hints):
            color = (120, 120, 120) if i > 0 else (50, 50, 50)
            text = font_small.render(hint, True, color)
            screen.blit(text, (self.cols * self.cell_size + 20, hint_y + i * 22))

    def run(self, all_results, goals, agent_ids, alloc_result, agents):
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("多机器人纯 A* 寻路仿真")
        clock = pygame.time.Clock()

        algo_keys = list(all_results.keys())
        current_algo = algo_keys[0]
        paths = all_results[current_algo]['paths']
        algo_info = all_results[current_algo]

        max_t = max(len(p) for p in paths.values())
        current_t = 0
        paused = False
        running = True
        history_paths = {aid: [] for aid in agent_ids}

        manual_mode = False
        active_agent = 0
        manual_paths = {aid: [] for aid in agent_ids}
        drawing_path = False
        drawing_obstacle = False
        erasing_obstacle = False

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_r:
                        current_t = 0
                        history_paths = {aid: [] for aid in agent_ids}
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_c:
                        self.grid.fill(0)
                        manual_paths = {aid: [] for aid in agent_ids}
                        print("地图已清空，按 Enter 重新规划")
                    elif event.key == pygame.K_m:
                        manual_mode = not manual_mode
                        print(f"切换到 {'手动画线' if manual_mode else '算法自动'} 模式")
                        if not manual_mode:
                            manual_paths = {aid: [] for aid in agent_ids}
                    elif event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]:
                        if manual_mode:
                            active_agent = event.key - pygame.K_1
                            print(f"当前控制机器人: {active_agent}")
                    elif event.key == pygame.K_RETURN:
                        if manual_mode:
                            manual_result_paths = {}
                            for aid in agent_ids:
                                raw_path = manual_paths[aid]
                                if raw_path:
                                    space_time_path = [(r, c, t) for t, (r, c) in enumerate(raw_path)]
                                    if len(space_time_path) < max_t:
                                        last = space_time_path[-1]
                                        for extra_t in range(len(space_time_path), max_t):
                                            space_time_path.append((last[0], last[1], extra_t))
                                    manual_result_paths[aid] = space_time_path

                            if manual_result_paths:
                                all_results = {"手动规划": {"paths": manual_result_paths,
                                                            "cost": sum(len(p) for p in manual_result_paths.values()),
                                                            "time": 0.0}}
                                current_algo = "手动规划"
                                paths = manual_result_paths
                                max_t = max(len(p) for p in paths.values())
                                current_t = 0
                                history_paths = {aid: [] for aid in agent_ids}
                                print("已应用手动规划路径！")
                        else:
                            print("正在重新规划...")
                            all_results = replan_all(self.grid, agents)
                            if all_results:
                                current_algo = list(all_results.keys())[0]
                                paths = all_results[current_algo]['paths']
                                algo_info = all_results[current_algo]
                                max_t = max(len(p) for p in paths.values())
                                current_t = 0
                                history_paths = {aid: [] for aid in agent_ids}
                                print(f"重新规划完成!")
                            else:
                                print("重新规划失败，请检查是否将机器人起点/终点堵死了")
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if manual_mode:
                        if event.button == 1:
                            drawing_path = True
                            manual_paths[active_agent] = []
                            grid_pos = self.screen_to_grid(event.pos)
                            if grid_pos:
                                manual_paths[active_agent].append(grid_pos)
                    else:
                        if event.button == 1:
                            drawing_obstacle = True
                            self.modify_grid(event.pos, agents, 1)
                        elif event.button == 3:
                            erasing_obstacle = True
                            self.modify_grid(event.pos, agents, 0)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if manual_mode:
                        drawing_path = False
                        print(f"机器人 {active_agent} 的路线已画完，按 Enter 应用")
                    else:
                        drawing_obstacle = False
                        erasing_obstacle = False
                elif event.type == pygame.MOUSEMOTION:
                    if manual_mode and drawing_path:
                        grid_pos = self.screen_to_grid(event.pos)
                        if grid_pos and grid_pos not in manual_paths[active_agent]:
                            if self.grid[grid_pos] != 1:
                                manual_paths[active_agent].append(grid_pos)
                    elif not manual_mode:
                        if drawing_obstacle:
                            self.modify_grid(event.pos, agents, 1)
                        elif erasing_obstacle:
                            self.modify_grid(event.pos, agents, 0)

            if not paused and current_t < max_t:
                current_t += 1
                for aid in agent_ids:
                    if aid not in paths: continue
                    path = paths[aid]
                    idx = min(current_t, len(path) - 1)
                    r, c, _ = path[idx]
                    if not history_paths[aid] or history_paths[aid][-1] != (r, c):
                        history_paths[aid].append((r, c))

            screen.fill(self.COLOR_BG)
            self.draw_grid(screen)

            if manual_mode:
                self.draw_manual_path(screen, manual_paths, active_agent)

            current_positions = {}
            for aid in agent_ids:
                if aid not in paths: continue
                path = paths[aid]
                idx = min(current_t, len(path) - 1)
                r, c, _ = path[idx]
                current_positions[aid] = (r, c)

            self.draw_agents(screen, current_positions, goals, agent_ids, history_paths)
            self.draw_ui(screen, current_t, max_t, current_algo, algo_info, paused, alloc_result, manual_mode,
                         active_agent)

            pygame.display.flip()
            clock.tick(self.fps)

        pygame.quit()
        sys.exit()

    def modify_grid(self, pos, agents, value):
        grid_pos = self.screen_to_grid(pos)
        if grid_pos is None: return
        r, c = grid_pos
        for (start, goal) in agents:
            if (r, c) == start or (r, c) == goal: return
        self.grid[r, c] = value


# ==========================================
# 5. 主程序
# ==========================================
def create_warehouse_grid(rows=12, cols=12):
    grid = np.zeros((rows, cols), dtype=int)
    for r in range(2, rows - 2, 4):
        for c in range(2, cols - 2, 4):
            grid[r:r + 2, c:c + 2] = 1
    return grid


def generate_agents(num_agents, rows, cols, grid):
    available_positions = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 0]
    if num_agents * 2 > len(available_positions):
        print(f"错误：机器人数量过多！地图可用格子不足以生成 {num_agents} 个机器人。")
        sys.exit(1)

    random.shuffle(available_positions)
    agents = []
    for _ in range(num_agents):
        start = available_positions.pop()
        goal = available_positions.pop()
        agents.append((start, goal))
    return agents


def main():
    rows, cols = 12, 12
    grid = create_warehouse_grid(rows, cols)

    print("=" * 40)
    print("      欢迎使用纯 A* 多机器人仿真")
    print("=" * 40)

    # ====================================================
    # 在这里让用户自己输入机器人数量
    # ====================================================
    while True:
        try:
            user_input = input("请输入机器人数量 (建议 1-20): ")
            NUM_ROBOTS = int(user_input)
            if NUM_ROBOTS <= 0:
                print("机器人数量必须大于 0，请重新输入！")
                continue
            break
        except ValueError:
            print("输入无效！请输入一个整数（例如 5）。")
    # ====================================================

    agents = generate_agents(NUM_ROBOTS, rows, cols, grid)

    print(f"\n机器人数量: {len(agents)}")
    for i, (s, g) in enumerate(agents):
        print(f"  机器人{i}: 起点{s} -> 终点{g}")

    # 初始规划（纯 A*）
    all_results = replan_all(grid, agents)

    # 任务分配
    robot_positions = [s for s, g in agents]
    task_positions = [g for s, g in agents]
    allocator = TaskAllocator(robot_positions, task_positions)
    alloc_result = allocator.allocate_greedy()

    # 启动仿真
    if all_results:
        print("\n启动 Pygame 仿真...")
        print("操作说明: 左键画障碍 | 右键擦除 | Enter 重新规划 | C 清空")
        goals = {i: agents[i][1] for i in range(len(agents))}
        agent_ids = list(range(len(agents)))
        visualizer = PygameVisualizer(grid, cell_size=40, fps=8, num_agents=NUM_ROBOTS)
        visualizer.run(all_results, goals, agent_ids, alloc_result, agents)


if __name__ == "__main__":
    main()