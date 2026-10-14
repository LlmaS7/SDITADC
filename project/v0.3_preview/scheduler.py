"""Exact matching for configurable fleets, using O(tasks * robots * 2**robots).

Lexicographic objective: maximize assigned priority-5 count, then priority-4,
etc.; then minimize total ETA. Arrival order breaks equal-cost ties only.
This is exact for the supplied cost matrix, not global lifelong optimality.
"""
from dataclasses import dataclass
from config import LOAD_TICKS, UNLOAD_TICKS


@dataclass(frozen=True)
class Slot:
    robot_id: int
    origin: tuple[int, int]
    release: int = 0
    deferred: bool = False


def completion_cost(warehouse, slot, task):
    return (slot.release + warehouse.distance(slot.origin, task.pickup) + LOAD_TICKS
            + warehouse.distance(task.pickup, task.delivery) + UNLOAD_TICKS)


def exact_matching(slots, tasks, cost):
    """Dynamic programming over used robot masks; each task is used at most once."""
    # score = negative counts at each priority, ETA sum, arrival tie-break.
    empty = (0,) * 7
    states = {0: (empty, {})}
    for task in sorted(tasks, key=lambda t: t.id):
        estimates = [cost(slot, task) for slot in slots]
        following = dict(states)
        for mask, (score, pairs) in states.items():
            for index, slot in enumerate(slots):
                if mask & (1 << index):
                    continue
                eta = estimates[index]
                if eta >= 10**6:
                    continue
                updated = list(score)
                updated[5 - task.priority] -= 1
                updated[5] += eta
                updated[6] += task.created_at
                new_mask = mask | (1 << index)
                value = (tuple(updated), {**pairs, slot.robot_id: task.id})
                if new_mask not in following or value[0] < following[new_mask][0]:
                    following[new_mask] = value
        states = following
    score, pairs = min(states.values(), key=lambda item: item[0])
    return pairs, score


def minimum_assignment(costs):
    """Rectangular Hungarian algorithm: assign every row to a distinct column."""
    n = len(costs)
    if n == 0:
        return []
    m = len(costs[0])
    if m < n or any(len(row) != m for row in costs):
        raise ValueError("停车位不足或代价矩阵尺寸错误")
    u, v, matched, previous = [0]*(n+1), [0]*(m+1), [0]*(m+1), [0]*(m+1)
    for row in range(1, n+1):
        matched[0] = row
        column = 0
        slack, used = [float("inf")]*(m+1), [False]*(m+1)
        while True:
            used[column] = True
            current = matched[column]
            delta, following = float("inf"), 0
            for j in range(1, m+1):
                if used[j]:
                    continue
                reduced = costs[current-1][j-1]-u[current]-v[j]
                if reduced < slack[j]:
                    slack[j], previous[j] = reduced, column
                if slack[j] < delta:
                    delta, following = slack[j], j
            for j in range(m+1):
                if used[j]:
                    u[matched[j]] += delta; v[j] -= delta
                else:
                    slack[j] -= delta
            column = following
            if matched[column] == 0:
                break
        while column:
            following = previous[column]
            matched[column] = matched[following]
            column = following
    result = [0]*n
    for j in range(1, m+1):
        if matched[j]:
            result[matched[j]-1] = j-1
    return result


def optimal_parking(warehouse, origins):
    """Minimize total distance, then parking indices in robot order, exactly."""
    parks = warehouse.parking
    base = len(parks)+1
    # The lower digits encode deterministic ties without changing distance optimality.
    scale = base**len(origins)
    costs = [[warehouse.distance(origin, park)*scale + j*base**(len(origins)-1-i)
              for j, park in enumerate(parks)] for i, origin in enumerate(origins)]
    return [parks[j] for j in minimum_assignment(costs)]

