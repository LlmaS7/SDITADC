"""Exact matching for three robot slots, using O(tasks * robots * 2**robots).

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
        following = dict(states)
        for mask, (score, pairs) in states.items():
            for index, slot in enumerate(slots):
                if mask & (1 << index):
                    continue
                eta = cost(slot, task)
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

