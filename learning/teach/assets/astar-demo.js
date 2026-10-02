(() => {
  "use strict";

  const width = 10;
  const height = 8;
  const start = { x: 1, y: 3 };
  const goal = { x: 8, y: 3 };
  const wallKeys = new Set();
  for (let y = 0; y <= 5; y += 1) wallKeys.add("4," + y);

  const board = document.getElementById("astar-board");
  const status = document.getElementById("demo-status");
  const stepButton = document.getElementById("step-button");
  const autoButton = document.getElementById("auto-button");
  const resetButton = document.getElementById("reset-button");
  if (!board || !status || !stepButton || !autoButton || !resetButton) return;

  const key = (point) => point.x + "," + point.y;
  const heuristic = (point) => Math.abs(point.x - goal.x) + Math.abs(point.y - goal.y);
  const cells = new Map();

  board.style.gridTemplateColumns = "repeat(" + width + ", minmax(28px, 42px))";
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const point = { x, y };
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.setAttribute("role", "gridcell");
      cell.setAttribute("aria-label", "格子 " + x + ", " + y);
      const cost = document.createElement("span");
      cost.className = "cost";
      const mark = document.createElement("span");
      mark.className = "mark";
      cell.append(cost, mark);
      board.append(cell);
      cells.set(key(point), { element: cell, cost, mark, point });
    }
  }

  let frontier;
  let costs;
  let parents;
  let records;
  let closed;
  let currentKey;
  let route;
  let finished;
  let timer;

  function stopAuto() {
    if (timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
    autoButton.textContent = "自动播放";
  }

  function reset() {
    stopAuto();
    frontier = new Map();
    costs = new Map();
    parents = new Map();
    records = new Map();
    closed = new Set();
    currentKey = null;
    route = [];
    finished = false;

    const startKey = key(start);
    const h = heuristic(start);
    const initial = { ...start, g: 0, h, f: h };
    frontier.set(startKey, initial);
    costs.set(startKey, 0);
    records.set(startKey, initial);
    status.textContent = "准备就绪。起点已进入候选区；按“下一步”查看第一轮。";
    stepButton.disabled = false;
    autoButton.disabled = false;
    render();
  }

  function render() {
    const routeKeys = new Set(route);
    for (const [cellKey, info] of cells) {
      const point = info.point;
      const isStart = cellKey === key(start);
      const isGoal = cellKey === key(goal);
      const isWall = wallKeys.has(cellKey);
      const record = records.get(cellKey);

      info.element.className = "cell";
      if (isWall) info.element.classList.add("is-wall");
      if (frontier.has(cellKey)) info.element.classList.add("is-open");
      if (closed.has(cellKey)) info.element.classList.add("is-closed");
      if (cellKey === currentKey) info.element.classList.add("is-current");
      if (routeKeys.has(cellKey)) info.element.classList.add("is-path");
      if (isStart) info.element.classList.add("is-start");
      if (isGoal) info.element.classList.add("is-goal");

      info.mark.textContent = isWall ? "#" : isStart ? "S" : isGoal ? "G" : "";
      info.cost.textContent = record && !isWall ? "F" + record.f : "";
      info.element.setAttribute(
        "aria-label",
        "格子 " + point.x + ", " + point.y +
          (isWall ? "，墙" : "") +
          (isStart ? "，起点" : "") +
          (isGoal ? "，目标" : "") +
          (record && !isWall ? "，f 等于 " + record.f : "")
      );
    }
  }

  function reconstruct(goalKey) {
    const result = [goalKey];
    let cursor = goalKey;
    while (parents.has(cursor)) {
      cursor = parents.get(cursor);
      result.push(cursor);
    }
    return result.reverse();
  }

  function finishNoPath() {
    finished = true;
    status.textContent = "候选区已空，没有找到通路。";
    stepButton.disabled = true;
    autoButton.disabled = true;
    stopAuto();
    render();
  }

  function step() {
    if (finished) return;

    let current = null;
    for (const candidate of frontier.values()) {
      if (
        current === null ||
        candidate.f < current.f ||
        (candidate.f === current.f && candidate.h < current.h) ||
        (candidate.f === current.f && candidate.h === current.h && candidate.y < current.y) ||
        (candidate.f === current.f && candidate.h === current.h && candidate.y === current.y && candidate.x < current.x)
      ) {
        current = candidate;
      }
    }

    if (current === null) {
      finishNoPath();
      return;
    }

    const selectedKey = key(current);
    frontier.delete(selectedKey);
    currentKey = selectedKey;
    if (selectedKey === key(goal)) {
      route = reconstruct(selectedKey);
      finished = true;
      status.textContent =
        "取出目标格 (" + goal.x + ", " + goal.y + ")；路线找到，共 " + current.g +
        " 步。绿色格子是回溯得到的路线。";
      stepButton.disabled = true;
      autoButton.disabled = true;
      stopAuto();
      render();
      return;
    }

    closed.add(selectedKey);
    const neighbors = [
      { x: current.x + 1, y: current.y },
      { x: current.x, y: current.y + 1 },
      { x: current.x - 1, y: current.y },
      { x: current.x, y: current.y - 1 }
    ];
    let added = 0;
    let updated = 0;

    for (const neighbor of neighbors) {
      if (
        neighbor.x < 0 || neighbor.x >= width ||
        neighbor.y < 0 || neighbor.y >= height
      ) continue;

      const neighborKey = key(neighbor);
      if (wallKeys.has(neighborKey) || closed.has(neighborKey)) continue;

      const newCost = current.g + 1;
      const oldCost = costs.get(neighborKey);
      if (oldCost !== undefined && newCost >= oldCost) continue;

      const h = heuristic(neighbor);
      const record = { ...neighbor, g: newCost, h, f: newCost + h };
      costs.set(neighborKey, newCost);
      records.set(neighborKey, record);
      parents.set(neighborKey, selectedKey);
      frontier.set(neighborKey, record);
      if (oldCost === undefined) added += 1;
      else updated += 1;
    }

    status.textContent =
      "取出 (" + current.x + ", " + current.y + ")：g=" + current.g +
      "，h=" + current.h + "，f=" + current.f +
      "；加入 " + added + " 个新候选位置" +
      (updated ? "，更新 " + updated + " 个更短到达方式" : "") +
      "。候选区还剩 " + frontier.size + " 个位置。";
    render();
  }

  stepButton.addEventListener("click", step);
  autoButton.addEventListener("click", () => {
    if (timer !== undefined) {
      stopAuto();
      return;
    }
    autoButton.textContent = "暂停";
    timer = window.setInterval(() => {
      step();
      if (finished) stopAuto();
    }, 420);
  });
  resetButton.addEventListener("click", reset);

  reset();
})();
