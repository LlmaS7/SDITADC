"""Reproducible shelves, static clutter, service bays and off-aisle parking."""
from collections import deque
from random import Random
from config import WIDTH, HEIGHT
from models import Position


class Warehouse:
    def __init__(self, seed: int):
        self.seed = seed
        self.width, self.height = WIDTH, HEIGHT
        self.shelves: set[Position] = set()
        self.obstacles: set[Position] = set()
        self.parking = [(2, 2), (3, 2), (4, 2), (29, 2), (2, 21), (29, 21)]
        self.starts = self.parking[:3]
        self.pickups: list[Position] = []
        self.deliveries = [(9, 21), (15, 21), (21, 21), (26, 21)]
        # Four rows of five solid shelves, with two-cell cross aisles.
        for y in (5, 9, 13, 17):
            for x in (4, 9, 14, 19, 24):
                self.shelves.update((sx, sy) for sx in range(x, x + 3)
                                    for sy in range(y, y + 2))
                self.pickups.append((x + 1, y - 1))
        self.blocked = {(x, y) for y in range(HEIGHT) for x in range(WIDTH)
                        if x in (0, WIDTH - 1) or y in (0, HEIGHT - 1)} | self.shelves
        # Protect endpoints and their immediate approaches.
        protected = set(self.parking + self.pickups + self.deliveries)
        protected |= {q for p in list(protected) for q in self.adjacent(p)}
        candidates = [(x, y) for y in range(3, 21) for x in range(2, 30)
                      if (x, y) not in self.blocked | protected]
        rng = Random(seed)
        rng.shuffle(candidates)
        for p in candidates:
            if len(self.obstacles) >= 20:
                break
            self.blocked.add(p)
            if len(self.reachable(self.starts[0])) == WIDTH * HEIGHT - len(self.blocked):
                self.obstacles.add(p)
            else:
                self.blocked.remove(p)
        self._distances: dict[Position, dict[Position, int]] = {}

    @staticmethod
    def adjacent(p):
        x, y = p
        return ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))

    def is_open(self, p):
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height and p not in self.blocked

    def neighbors(self, p):
        return [q for q in self.adjacent(p) if self.is_open(q)]

    def reachable(self, start):
        distances = {start: 0}
        queue = deque([start])
        while queue:
            p = queue.popleft()
            for q in self.neighbors(p):
                if q not in distances:
                    distances[q] = distances[p] + 1
                    queue.append(q)
        return distances

    def distance(self, start, goal):
        if goal not in self._distances:
            self._distances[goal] = self.reachable(goal)
        return self._distances[goal].get(start, 10**6)

