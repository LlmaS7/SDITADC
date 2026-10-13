"""Check padded paths, including occupancy after final arrival."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Conflict:
    a: int
    b: int
    time: int
    position: tuple[int, int] | None = None
    edge_a: tuple | None = None
    edge_b: tuple | None = None


def at(path, tick):
    return path[min(tick, len(path) - 1)]


def first_conflict(paths):
    ids = sorted(paths)
    for tick in range(max(map(len, paths.values()))):
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                u, v = at(paths[a], tick), at(paths[b], tick)
                if u == v:
                    return Conflict(a, b, tick, position=u)
                if tick:
                    pu, pv = at(paths[a], tick - 1), at(paths[b], tick - 1)
                    if pu == v and pv == u:
                        return Conflict(a, b, tick, edge_a=(pu, u), edge_b=(pv, v))
    return None


def validate_paths(warehouse, starts, paths):
    for robot, path in paths.items():
        if not path or path[0] != starts[robot]:
            raise ValueError("Path does not start at the robot position")
        if any(not warehouse.is_open(p) for p in path):
            raise ValueError("Path enters an obstacle")
        if any(abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1 for a, b in zip(path, path[1:])):
            raise ValueError("Path contains an invalid move")
    if first_conflict(paths):
        raise ValueError("Paths contain a collision")

