# 纯文本 A* 入门程序
# 坐标是 (行, 列)，左上角为 (0, 0)。

GRID = [
    "....#....",
    "....#....",
    "....#....",
    "....#....",
    ".........",
    ".........",
    ".........",
]
START = (2, 1)
GOAL = (2, 7)


def manhattan(position, goal):
    row, col = position
    goal_row, goal_col = goal
    return abs(row - goal_row) + abs(col - goal_col)


def astar(grid, start, goal):
    frontier = [start]   # 已发现、还没扩展的位置
    came_from = {}        # 每个位置的前一个位置  ->line 62
    g_score = {start: 0}  # 从起点走到这里的步数
    expanded = set()      # 已经查看过邻居的位置

    while frontier:
        # 取 f = g + h 最小的位置。
        current = min(
            frontier,
            key=lambda p: g_score[p] + manhattan(p, goal),
        )
        frontier.remove(current)

        if current == goal:
            path = [goal]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            return list(reversed(path))

        expanded.add(current)
        row, col = current

        # 依次查看上、右、下、左四个方向。
        for dr, dc in [(-1, 0), (0, 1), (1, 0), (0, -1)]:
            next_row, next_col = row + dr, col + dc
            neighbor = (next_row, next_col)

            inside = (
                0 <= next_row < len(grid)
                and 0 <= next_col < len(grid[0])
            )
            if not inside or grid[next_row][next_col] == "#":
                continue
            if neighbor in expanded:
                continue

            new_g = g_score[current] + 1
            if new_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = new_g
                if neighbor not in frontier:
                    frontier.append(neighbor)

    return None


def render_map(grid, start, goal, path=None):
    path = set(path or [])

    for row_index, row in enumerate(grid):
        symbols = []
        for col_index, tile in enumerate(row):
            position = (row_index, col_index)

            if position == start:
                symbol = "S"
            elif position == goal:
                symbol = "G"
            elif tile == "#":
                symbol = "#"
            elif position in path:
                symbol = "*"
            else:
                symbol = "."
            symbols.append(symbol)

        print(" ".join(symbols))


print("图例：# 墙  . 空地  S 起点  G 终点  * 路径")
print("\n原始地图：")
render_map(GRID, START, GOAL)

path = astar(GRID, START, GOAL)
if path is None:
    print("\n没有找到可行路径。")
else:
    print("\nA* 找到的路径：")
    render_map(GRID, START, GOAL, path)
    print("路径步数：", len(path) - 1)
"""Learning example: standalone single-robot A* in text."""
