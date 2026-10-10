"""A small text-only example of prioritized planning for two robots.

Run with (from SDITADC/learning):
    python teach/examples/two_robot_prioritized.py

Coordinates are written as (x, y): x grows right, y grows down.
"""

from heapq import heappop, heappush


GRID = [
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
]

# Each robot has a fixed start and goal for this lesson.
ROBOTS = {
    "A": ((1, 2), (3, 2)),
    "B": ((2, 1), (2, 3)),
}

# Four directions plus WAIT. Every action costs one time step.
ACTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0), (0, 0))
MAX_TIME = 20

Position = tuple[int, int]
State = tuple[int, int, int]  # (x, y, time)


def is_open(position: Position) -> bool:
    """Return whether a cell is inside the map and is not a wall."""
    x, y = position
    return 0 <= y < len(GRID) and 0 <= x < len(GRID[0]) and GRID[y][x] != "#"


def manhattan(position: Position, goal: Position) -> int:
    """The same lower-bound heuristic used by four-direction A*."""
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


def plan_path(
    start: Position,
    goal: Position,
    reserved_vertices: set[tuple[int, Position]],
    reserved_edges: set[tuple[int, Position, Position]],
) -> list[Position] | None:
    """Find a path through space and time while respecting earlier robots."""
    if not is_open(start) or not is_open(goal):
        return None
    if (0, start) in reserved_vertices:
        return None

    start_state: State = (start[0], start[1], 0)
    frontier: list[tuple[int, int, int, int]] = []
    heappush(frontier, (manhattan(start, goal), 0, start[1], start[0]))
    parent: dict[State, State | None] = {start_state: None}

    while frontier:
        _, time, y, x = heappop(frontier)
        state = (x, y, time)
        position = (x, y)

        if position == goal:
            path: list[Position] = []
            current: State | None = state
            while current is not None:
                path.append((current[0], current[1]))
                current = parent[current]
            return list(reversed(path))

        if time == MAX_TIME:
            continue

        next_time = time + 1
        for dx, dy in ACTIONS:
            next_position = (x + dx, y + dy)
            if not is_open(next_position):
                continue

            # A vertex conflict: two robots occupy one cell at one time.
            if (next_time, next_position) in reserved_vertices:
                continue

            # A swap conflict: robots traverse the same edge in opposite ways.
            reverse_edge = (next_time, next_position, position)
            if next_position != position and reverse_edge in reserved_edges:
                continue

            next_state = (next_position[0], next_position[1], next_time)
            if next_state in parent:
                continue

            parent[next_state] = state
            priority = next_time + manhattan(next_position, goal)
            heappush(
                frontier,
                (priority, next_time, next_position[1], next_position[0]),
            )

    return None


def reserve_path(
    path: list[Position],
    reserved_vertices: set[tuple[int, Position]],
    reserved_edges: set[tuple[int, Position, Position]],
) -> None:
    """Record a path so later robots plan around it."""
    for time, position in enumerate(path):
        reserved_vertices.add((time, position))

    for arrival_time in range(1, len(path)):
        reserved_edges.add(
            (arrival_time, path[arrival_time - 1], path[arrival_time])
        )

    # This lesson assumes a robot stays at its goal after arriving.
    goal = path[-1]
    for time in range(len(path) - 1, MAX_TIME + 1):
        reserved_vertices.add((time, goal))


def position_at(path: list[Position], time: int) -> Position:
    """After arrival, treat the robot as waiting at its goal."""
    return path[min(time, len(path) - 1)]


def first_conflict(paths: dict[str, list[Position]]) -> str | None:
    """Describe the first vertex or swap conflict in a set of paths."""
    names = list(paths)
    last_time = max(len(path) - 1 for path in paths.values())

    for time in range(last_time + 1):
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                first, second = names[i], names[j]
                first_pos = position_at(paths[first], time)
                second_pos = position_at(paths[second], time)
                if first_pos == second_pos:
                    return (
                        f"vertex conflict at t={time}, cell={first_pos}: "
                        f"robots {first} and {second}"
                    )

                if time < last_time:
                    first_next = position_at(paths[first], time + 1)
                    second_next = position_at(paths[second], time + 1)
                    if first_pos == second_next and second_pos == first_next:
                        return (
                            f"swap conflict between t={time} and t={time + 1}: "
                            f"robots {first} and {second}"
                        )

    return None


def show_grid() -> None:
    print("Map (# = wall, . = open cell)")
    for row in GRID:
        print(row)
    print("Coordinates: A starts at (1, 2) and heads to (3, 2).")
    print("            B starts at (2, 1) and heads to (2, 3).")


def show_paths(paths: dict[str, list[Position]]) -> None:
    for name, path in paths.items():
        route = " -> ".join(str(position) for position in path)
        print(f"{name}: {route}")


def show_schedule(paths: dict[str, list[Position]]) -> None:
    last_time = max(len(path) - 1 for path in paths.values())
    print("\nTime | Robot A | Robot B")
    print("-----+---------+--------")
    for time in range(last_time + 1):
        a = position_at(paths["A"], time)
        b = position_at(paths["B"], time)
        print(f"{time:>4} | {str(a):>7} | {b}")


def main() -> None:
    show_grid()

    # First, plan as if the other robot did not exist.
    independent_paths = {
        name: plan_path(start, goal, set(), set())
        for name, (start, goal) in ROBOTS.items()
    }
    # This tiny map has a path for each robot, so these assertions guard the demo setup.
    assert all(path is not None for path in independent_paths.values())
    solo_paths = {
        name: path
        for name, path in independent_paths.items()
        if path is not None
    }

    print("\nIndependent A* paths (each ignores the other robot):")
    show_paths(solo_paths)
    print("First conflict:", first_conflict(solo_paths))

    # Then plan one robot at a time in a fixed priority order: A, then B.
    reserved_vertices: set[tuple[int, Position]] = set()
    reserved_edges: set[tuple[int, Position, Position]] = set()
    coordinated_paths: dict[str, list[Position]] = {}

    for name, (start, goal) in ROBOTS.items():
        path = plan_path(start, goal, reserved_vertices, reserved_edges)
        if path is None:
            print(f"\nRobot {name}: no path found under the current reservations.")
            return
        coordinated_paths[name] = path
        reserve_path(path, reserved_vertices, reserved_edges)

    print("\nPrioritized paths (A is planned before B):")
    show_paths(coordinated_paths)
    show_schedule(coordinated_paths)
    print("First conflict:", first_conflict(coordinated_paths))


if __name__ == "__main__":
    main()
