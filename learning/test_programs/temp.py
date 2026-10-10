from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = ROOT / "maps" / "learning" / "astar_grid.txt"

CELL_SIZE = 34
MARGIN = 30
PANEL_WIDTH = 350
PANEL_GAP = 28

BACKGROUND = (15, 23, 42)
PANEL = (30, 41, 59)
TEXT = (241, 245, 249)
MUTED_TEXT = (148, 163, 184)
ACCENT = (56, 189, 248)
FLOOR = (226, 232, 240)
WALL = (51, 65, 85)
OPEN_COLOR = (96, 165, 250)
CLOSED_COLOR = (148, 163, 184)
PATH_COLOR = (251, 191, 36)
START_COLOR = (52, 211, 153)
GOAL_COLOR = (248, 113, 113)
CURRENT_COLOR = (167, 139, 250)

NEIGHBOR_OFFSETS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def load_map(path: Path) -> tuple[list[list[str]], tuple[int, int], tuple[int, int]]:
    """Read a small teaching map made of #, ., S, and G characters."""
    rows = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError(f"Map rows must all have the same non-zero width: {path}")

    allowed = {"#", ".", "S", "G"}
    if any(cell not in allowed for row in rows for cell in row):
        raise ValueError("Map cells can only be #, ., S, or G")

    starts = [(x, y) for y, row in enumerate(rows) for x, cell in enumerate(row) if cell == "S"]
    goals = [(x, y) for y, row in enumerate(rows) for x, cell in enumerate(row) if cell == "G"]
    if len(starts) != 1 or len(goals) != 1:
        raise ValueError("The map must contain exactly one S start and one G goal")

    return [list(row) for row in rows], starts[0], goals[0]


def heuristic(position: tuple[int, int], goal: tuple[int, int]) -> int:
    """Manhattan distance for four-direction movement."""
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


def new_search(start: tuple[int, int]) -> dict:
    return {
        "open": [start],
        "closed": set(),
        "came_from": {},
        "g_score": {start: 0},
        "current": None,
        "path": [],
        "steps": 0,
        "status": "running",
    }


def rebuild_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [goal]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def take_search_step(
    search: dict,
    grid: list[list[str]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> None:
    """Expand one cell with the lowest f = g + h score."""
    if search["status"] != "running":
        return

    open_cells = search["open"]
    if not open_cells:
        search["status"] = "no_path"
        return

    g_score = search["g_score"]
    current = min(open_cells, key=lambda point: g_score[point] + heuristic(point, goal))
    open_cells.remove(current)
    search["current"] = current
    search["closed"].add(current)
    search["steps"] += 1

    if current == goal:
        search["path"] = rebuild_path(search["came_from"], start, goal)
        search["status"] = "found"
        return

    height = len(grid)
    width = len(grid[0])
    for dx, dy in NEIGHBOR_OFFSETS:
        neighbor = (current[0] + dx, current[1] + dy)
        x, y = neighbor
        if not (0 <= x < width and 0 <= y < height):
            continue
        if grid[y][x] == "#" or neighbor in search["closed"]:
            continue

        new_g = g_score[current] + 1
        if new_g < g_score.get(neighbor, float("inf")):
            search["came_from"][neighbor] = current
            g_score[neighbor] = new_g
            if neighbor not in open_cells:
                open_cells.append(neighbor)


def draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    position: tuple[int, int],
    color: tuple[int, int, int] = TEXT,
) -> None:
    surface.blit(font.render(text, True, color), position)


def draw_map(
    surface: pygame.Surface,
    grid: list[list[str]],
    start: tuple[int, int],
    goal: tuple[int, int],
    search: dict,
    origin: tuple[int, int],
    font: pygame.font.Font,
    score_font: pygame.font.Font,
) -> None:
    open_cells = set(search["open"])
    closed_cells = search["closed"]
    path_cells = set(search["path"])
    current = search["current"]
    g_score = search["g_score"]
    origin_x, origin_y = origin

    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            position = (x, y)
            rect = pygame.Rect(
                origin_x + x * CELL_SIZE,
                origin_y + y * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE,
            )

            if cell == "#":
                color = WALL
            elif position == start:
                color = START_COLOR
            elif position == goal:
                color = GOAL_COLOR
            elif position in path_cells:
                color = PATH_COLOR
            elif position == current:
                color = CURRENT_COLOR
            elif position in open_cells:
                color = OPEN_COLOR
            elif position in closed_cells:
                color = CLOSED_COLOR
            else:
                color = FLOOR

            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (203, 213, 225), rect, width=1)

            if position in (start, goal):
                label = "S" if position == start else "G"
                label_surface = font.render(label, True, (15, 23, 42))
                surface.blit(label_surface, label_surface.get_rect(center=rect.center))
            elif position in open_cells:
                f_score = g_score[position] + heuristic(position, goal)
                score_surface = score_font.render(str(f_score), True, (15, 23, 42))
                surface.blit(score_surface, score_surface.get_rect(center=rect.center))


def draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    search: dict,
    goal: tuple[int, int],
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    auto_run: bool,
) -> None:
    pygame.draw.rect(screen, PANEL, rect, border_radius=12)
    x = rect.x + 20
    y = rect.y + 18

    draw_text(screen, font, "A* 搜索过程", (x, y))
    y += 38
    draw_text(screen, small_font, "每一步选 f 最小的格子：f(n) = g(n) + h(n)", (x, y), OPEN_COLOR)
    y += 32
    draw_text(screen, small_font, "g：从起点走到这里的实际步数", (x, y), MUTED_TEXT)
    y += 23
    draw_text(screen, small_font, "h：到终点的曼哈顿距离估计", (x, y), MUTED_TEXT)

    y += 34
    pygame.draw.line(screen, (71, 85, 105), (x, y), (rect.right - 20, y), 1)
    y += 15
    draw_text(screen, small_font, f"扩展步数：{search['steps']}", (x, y))
    y += 23
    draw_text(screen, small_font, f"OPEN 待探索：{len(search['open'])}", (x, y), OPEN_COLOR)
    y += 23
    draw_text(screen, small_font, f"CLOSED 已探索：{len(search['closed'])}", (x, y), MUTED_TEXT)

    y += 28
    current = search["current"]
    if current is None:
        draw_text(screen, small_font, "当前节点：尚未开始", (x, y))
    else:
        g = search["g_score"][current]
        h = heuristic(current, goal)
        f = g + h
        draw_text(screen, small_font, f"当前节点：({current[0]}, {current[1]})", (x, y))
        y += 22
        draw_text(screen, small_font, f"g = {g}    h = {h}    f = {f}", (x, y), CURRENT_COLOR)

    y = rect.y + 305
    pygame.draw.line(screen, (71, 85, 105), (x, y), (rect.right - 20, y), 1)
    y += 14
    draw_text(screen, small_font, "颜色图例", (x, y))
    y += 26

    legend = (
        (OPEN_COLOR, "OPEN 待探索"),
        (CLOSED_COLOR, "CLOSED 已探索"),
        (CURRENT_COLOR, "当前节点"),
        (PATH_COLOR, "最终路径"),
        (START_COLOR, "起点 S"),
        (GOAL_COLOR, "终点 G"),
    )
    for index, (color, label) in enumerate(legend):
        column = index % 2
        row = index // 2
        item_x = x + column * 160
        item_y = y + row * 27
        pygame.draw.rect(screen, color, (item_x, item_y, 16, 16), border_radius=3)
        draw_text(screen, small_font, label, (item_x + 23, item_y - 2), TEXT)

    controls_y = y + 91
    pygame.draw.line(screen, (71, 85, 105), (x, controls_y), (rect.right - 20, controls_y), 1)
    controls_y += 12
    action = "自动搜索中" if auto_run else "Space：单步搜索"
    draw_text(screen, small_font, f"{action}    A：自动 / 暂停", (x, controls_y), ACCENT)
    controls_y += 23
    draw_text(screen, small_font, "R：重置    Q / Esc：退出", (x, controls_y), MUTED_TEXT)
    controls_y += 27

    if search["status"] == "found":
        result = f"找到路径：{len(search['path']) - 1} 步"
    elif search["status"] == "no_path":
        result = "没有找到可行路径"
    elif search["steps"] == 0:
        result = "准备就绪，按 Space 开始"
    else:
        result = "搜索进行中……"
    draw_text(screen, small_font, result, (x, controls_y), PATH_COLOR)


def main() -> None:
    grid, start, goal = load_map(MAP_FILE)
    height = len(grid)
    width = len(grid[0])
    map_width = width * CELL_SIZE
    map_height = height * CELL_SIZE

    screen_width = MARGIN * 2 + map_width + PANEL_GAP + PANEL_WIDTH
    screen_height = max(690, map_height + 190)
    map_origin = (MARGIN, (screen_height - map_height) // 2 + 18)
    panel_rect = pygame.Rect(
        MARGIN + map_width + PANEL_GAP,
        map_origin[1],
        PANEL_WIDTH,
        screen_height - map_origin[1] - 34,
    )

    pygame.init()
    pygame.display.set_caption("A* 入门学习程序")
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("Microsoft YaHei", 27, bold=True)
    panel_font = pygame.font.SysFont("Microsoft YaHei", 21, bold=True)
    small_font = pygame.font.SysFont("Microsoft YaHei", 16)
    score_font = pygame.font.SysFont(None, 16)

    search = new_search(start)
    auto_run = False
    next_auto_step = 0
    running = True

    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_SPACE:
                    auto_run = False
                    take_search_step(search, grid, start, goal)
                elif event.key == pygame.K_a:
                    auto_run = not auto_run
                    next_auto_step = now
                elif event.key == pygame.K_r:
                    search = new_search(start)
                    auto_run = False

        if auto_run and now >= next_auto_step and search["status"] == "running":
            take_search_step(search, grid, start, goal)
            next_auto_step = now + 220
        if search["status"] != "running":
            auto_run = False

        screen.fill(BACKGROUND)
        draw_text(screen, title_font, "A* 算法：从起点找到终点", (MARGIN, 30))
        draw_text(
            screen,
            small_font,
            f"{width} × {height} 网格 · 四方向移动 · Manhattan 启发函数",
            (MARGIN, 69),
            MUTED_TEXT,
        )

        map_rect = pygame.Rect(map_origin[0] - 5, map_origin[1] - 5, map_width + 10, map_height + 10)
        pygame.draw.rect(screen, (30, 41, 59), map_rect, border_radius=8)
        draw_map(screen, grid, start, goal, search, map_origin, panel_font, score_font)
        draw_panel(screen, panel_rect, search, goal, panel_font, small_font, auto_run)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
