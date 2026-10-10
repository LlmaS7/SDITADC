"""Three-robot prioritized planning; a teaching example, not a fleet solver.

Run from the project root:
    python teach/examples/three_robot_priority_search.py

Coordinates are (x, y), with x growing right and y growing down.
"""

from heapq import heappop, heappush
from itertools import count, permutations


GRID = [
    "#########",
    "###.#####",
    "###.#####",
    "#.......#",
    "#####.###",
    "#####.###",
    "#########",
]

# A's goal and C's goal are both located on B's one-cell-wide aisle.
ROBOTS = {
    "A": ((3, 1), (3, 3)),
    "B": ((1, 3), (7, 3)),
    "C": ((5, 5), (5, 3)),
}

ACTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0), (0, 0))  # up, right, down, left, wait
MAX_TIME = 20

Position = tuple[int, int]
State = tuple[int, int, int]  # x, y, time
VertexReservation = tuple[int, Position]
EdgeReservation = tuple[int, Position, Position]


def is_open(position: Position) -> bool:
    x, y = position
    return 0 <= y < len(GRID) and 0 <= x < len(GRID[0]) and GRID[y][x] != "#"


def heuristic(position: Position, goal: Position) -> int:
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


def goal_can_be_occupied(
    goal: Position,
    time: int,
    reserved_vertices: set[VertexReservation],
) -> bool:
    """In this lesson robots stay at their goals after arriving."""
    return all((tick, goal) not in reserved_vertices for tick in range(time, MAX_TIME + 1))


def rebuild_path(state: State, parent: dict[State, State | None]) -> list[Position]:
    path: list[Position] = []
    current: State | None = state
    while current is not None:
        path.append((current[0], current[1]))
        current = parent[current]
    return list(reversed(path))


def plan_one(
    start: Position,
    goal: Position,
    reserved_vertices: set[VertexReservation],
    reserved_edges: set[EdgeReservation],
) -> list[Position] | None:
    """Space-time A*: avoid earlier paths, including opposite edge swaps."""
    if not is_open(start) or not is_open(goal) or (0, start) in reserved_vertices:
        return None

    serial = count()
    start_state: State = (start[0], start[1], 0)
    frontier: list[tuple[int, int, State]] = []
    heappush(frontier, (heuristic(start, goal), next(serial), start_state))
    parent: dict[State, State | None] = {start_state: None}

    while frontier:
        _, _, state = heappop(frontier)
        x, y, time = state
        position = (x, y)

        if position == goal and goal_can_be_occupied(goal, time, reserved_vertices):
            return rebuild_path(state, parent)
        if time >= MAX_TIME:
            continue

        next_time = time + 1
        for dx, dy in ACTIONS:
            next_position = (x + dx, y + dy)
            if not is_open(next_position):
                continue
            if (next_time, next_position) in reserved_vertices:
                continue  # vertex conflict
            if next_position != position and (next_time, next_position, position) in reserved_edges:
                continue  # opposite-direction edge swap

            next_state = (next_position[0], next_position[1], next_time)
            if next_state in parent:
                continue
            parent[next_state] = state
            score = next_time + heuristic(next_position, goal)
            heappush(frontier, (score, next(serial), next_state))

    return None


def reserve(
    path: list[Position],
    vertices: set[VertexReservation],
    edges: set[EdgeReservation],
) -> None:
    for time, position in enumerate(path):
        vertices.add((time, position))
    for arrival_time in range(1, len(path)):
        edges.add((arrival_time, path[arrival_time - 1], path[arrival_time]))
    # Keep the destination occupied through the planning horizon.
    for time in range(len(path) - 1, MAX_TIME + 1):
        vertices.add((time, path[-1]))


def plan_order(order: tuple[str, ...]) -> tuple[dict[str, list[Position]] | None, str | None]:
    """Each trial gets fresh reservations; return paths or first blocked robot."""
    vertices: set[VertexReservation] = set()
    edges: set[EdgeReservation] = set()
    paths: dict[str, list[Position]] = {}
    for name in order:
        start, goal = ROBOTS[name]
        path = plan_one(start, goal, vertices, edges)
        if path is None:
            return None, name
        paths[name] = path
        reserve(path, vertices, edges)
    return paths, None


def at(path: list[Position], time: int) -> Position:
    return path[min(time, len(path) - 1)]


def first_conflict(paths: dict[str, list[Position]]) -> str | None:
    names = list(paths)
    final_time = max(len(path) - 1 for path in paths.values())
    for time in range(final_time + 1):
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                a_now, b_now = at(paths[a], time), at(paths[b], time)
                if a_now == b_now:
                    return f"vertex conflict at t={time}: {a} and {b}"
                if time < final_time:
                    a_next, b_next = at(paths[a], time + 1), at(paths[b], time + 1)
                    if a_now == b_next and b_now == a_next:
                        return f"swap conflict after t={time}: {a} and {b}"
    return None


def show_map() -> None:
    markers = {start: name.lower() for name, (start, _) in ROBOTS.items()}
    markers.update({goal: name for name, (_, goal) in ROBOTS.items()})
    for y, row in enumerate(GRID):
        print("".join(markers.get((x, y), cell) for x, cell in enumerate(row)))
    print("lowercase = start; uppercase = goal; # = wall; . = floor")


def show_schedule(paths: dict[str, list[Position]]) -> None:
    final_time = max(len(path) - 1 for path in paths.values())
    print("\n t |     A |     B |     C")
    print("---+-------+-------+-------")
    for time in range(final_time + 1):
        print(f"{time:>2} | {str(at(paths['A'], time)):>5} | {str(at(paths['B'], time)):>5} | {at(paths['C'], time)}")


def show_frame(paths: dict[str, list[Position]], time: int) -> None:
    robots = {at(path, time): name for name, path in paths.items()}
    print(f"\nt={time}")
    for y, row in enumerate(GRID):
        print("".join(robots.get((x, y), cell) for x, cell in enumerate(row)))


def main() -> None:
    print("Three robots, one narrow aisle:")
    show_map()

    fixed_order = ("A", "B", "C")
    paths, blocked = plan_order(fixed_order)
    if paths is None:
        print(f"\nA -> B -> C fails while planning {blocked}.")
        print("A parks on B's only route through the aisle.")

    print("\nTry priority orders in turn:")
    chosen_order: tuple[str, ...] | None = None
    chosen_paths: dict[str, list[Position]] | None = None
    for order in permutations(ROBOTS):
        paths, blocked = plan_order(order)
        label = " -> ".join(order)
        if paths is None:
            print(f"  {label}: blocked at {blocked}")
            continue
        print(f"  {label}: success")
        chosen_order, chosen_paths = order, paths
        break

    if chosen_paths is None or chosen_order is None:
        print("No order found a solution within this time limit.")
        return

    print("\nChosen order:", " -> ".join(chosen_order))
    print("Paths and wait counts:")
    for name in chosen_order:
        path = chosen_paths[name]
        waits = sum(path[i] == path[i - 1] for i in range(1, len(path)))
        print(f"  {name}: {' -> '.join(map(str, path))}  waits={waits}")
    show_schedule(chosen_paths)
    print("\nConflict check:", first_conflict(chosen_paths) or "no conflicts")
    for time in (0, 2, 4, 6):
        show_frame(chosen_paths, time)
    print("\nThis tries N! priority orders; use it only as a small teaching example.")


if __name__ == "__main__":
    main()
