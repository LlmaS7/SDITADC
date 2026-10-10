(() => {
  "use strict";

  // These values mirror astar_text.py so the page can replay its search.
  const grid = [
    "....#....",
    "....#....",
    "....#....",
    "....#....",
    ".........",
    ".........",
    "........."
  ];
  const start = [2, 1];
  const goal = [2, 7];
  const directions = [
    { dr: -1, dc: 0, name: "上" },
    { dr: 0, dc: 1, name: "右" },
    { dr: 1, dc: 0, name: "下" },
    { dr: 0, dc: -1, name: "左" }
  ];

  const $ = (id) => document.getElementById(id);
  const board = $("trace-board");
  const status = $("trace-status");
  const currentText = $("trace-current");
  const neighborList = $("trace-neighbors");
  const frontierBody = $("trace-frontier");
  const expandedCount = $("trace-expanded-count");
  const roundLabel = $("trace-round");
  const codeTitle = $("trace-code-title");
  const codeBox = $("trace-code");
  const codeExplanation = $("trace-code-explanation");
  const output = $("trace-output");
  const stepButton = $("trace-step");
  const autoButton = $("trace-auto");
  const resetButton = $("trace-reset");
  if (!board || !status || !stepButton || !autoButton || !resetButton) return;

  const height = grid.length;
  const width = grid[0].length;
  const key = (p) => p[0] + "," + p[1];
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  const manhattan = (p) => Math.abs(p[0] - goal[0]) + Math.abs(p[1] - goal[1]);
  const cells = new Map();

  board.style.gridTemplateColumns = "repeat(" + width + ", 36px)";
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const cell = document.createElement("div");
      cell.className = "trace-cell";
      cell.setAttribute("role", "gridcell");
      const f = document.createElement("span");
      f.className = "trace-f";
      const mark = document.createElement("span");
      mark.className = "trace-mark";
      cell.append(f, mark);
      board.append(cell);
      cells.set(row + "," + col, { cell, f, mark, point: [row, col] });
    }
  }

  let frontier;
  let cameFrom;
  let gScore;
  let expanded;
  let known;
  let current;
  let path;
  let round;
  let finished;
  let timer;

  const code = {
    setup: {
      title: "对应程序：定义地图并打印原图",
      text: "GRID = [\n    \"....#....\",  # 每个字符代表一个格子\n    ...\n]\nSTART = (2, 1)\nGOAL = (2, 7)\n\nrender_map(GRID, START, GOAL)\npath = astar(GRID, START, GOAL)",
      explanation: "地图字符串里的 # 是墙，. 是空地。坐标用 (行, 列)，左上角从 (0, 0) 开始。"
    },
    choose: {
      title: "对应程序：从 frontier 取 f 最小的位置",
      text: "current = min(\n    frontier,\n    key=lambda p: g_score[p] + manhattan(p, goal),\n)\nfrontier.remove(current)",
      explanation: "这就是 f=g+h：g_score 是已经走过的步数，manhattan 是 h。若 f 相同，Python 的 min 保留列表中先出现的位置。"
    },
    expand: {
      title: "对应程序：检查相邻格子并过滤不能走的位置",
      text: "expanded.add(current)\n\nfor dr, dc in [(-1, 0), (0, 1), (1, 0), (0, -1)]:\n    neighbor = (row + dr, col + dc)\n    if not inside or grid[next_row][next_col] == \"#\":\n        continue\n    if neighbor in expanded:\n        continue",
      explanation: "当前格先记入 expanded，然后按上、右、下、左检查。越界、撞墙或已经扩展过的位置都会跳过。"
    },
    update: {
      title: "对应程序：只保留更短的到达方式",
      text: "new_g = g_score[current] + 1\nif new_g < g_score.get(neighbor, float(\"inf\")):\n    came_from[neighbor] = current\n    g_score[neighbor] = new_g\n    if neighbor not in frontier:\n        frontier.append(neighbor)",
      explanation: "每移动一格，g 增加 1。如果新路线更短，就更新代价和前驱；下一轮会重新按 f 挑选位置。"
    },
    path: {
      title: "对应程序：回溯路径并打印文本地图",
      text: "if current == goal:\n    path = [goal]\n    while path[-1] != start:\n        path.append(came_from[path[-1]])\n    return list(reversed(path))\n\nrender_map(GRID, START, GOAL, path)\nprint(\"路径步数：\", len(path) - 1)",
      explanation: "came_from 记录每个位置是从哪里来的。先从终点倒着回到起点并反转；render_map 再逐格打印路径。"
    }
  };

  function showCode(part) {
    codeTitle.textContent = part.title;
    codeBox.textContent = part.text;
    codeExplanation.textContent = part.explanation;
  }

  function asciiMap(route) {
    const routeKeys = new Set((route || []).map(key));
    return grid.map((line, row) => {
      const symbols = [];
      for (let col = 0; col < line.length; col += 1) {
        const p = [row, col];
        const pKey = key(p);
        if (same(p, start)) symbols.push("S");
        else if (same(p, goal)) symbols.push("G");
        else if (line[col] === "#") symbols.push("#");
        else if (routeKeys.has(pKey)) symbols.push("*");
        else symbols.push(".");
      }
      return symbols.join(" ");
    }).join("\n");
  }

  function renderOutput() {
    if (!finished) {
      output.textContent = "图例：# 墙  . 空地  S 起点  G 终点  * 路径\n\n原始地图：\n" + asciiMap([]) + "\n\n搜索进行中……";
      return;
    }
    if (!path) {
      output.textContent = "图例：# 墙  . 空地  S 起点  G 终点  * 路径\n\n原始地图：\n" + asciiMap([]) + "\n\n没有找到可行路径。";
      return;
    }
    output.textContent =
      "图例：# 墙  . 空地  S 起点  G 终点  * 路径\n\n原始地图：\n" + asciiMap([]) +
      "\n\nA* 找到的路径：\n" + asciiMap(path) +
      "\n路径步数： " + (path.length - 1);
  }

  function renderBoard() {
    const routeKeys = new Set((path || []).map(key));
    for (const [cellKey, info] of cells) {
      const p = info.point;
      const isWall = grid[p[0]][p[1]] === "#";
      const isStart = same(p, start);
      const isGoal = same(p, goal);
      const classes = ["trace-cell"];
      if (isWall) classes.push("is-wall");
      if (frontier.some((q) => key(q) === cellKey)) classes.push("is-frontier");
      if (expanded.has(cellKey)) classes.push("is-expanded");
      if (current && key(current) === cellKey) classes.push("is-current");
      if (routeKeys.has(cellKey)) classes.push("is-route");
      if (isStart) classes.push("is-start");
      if (isGoal) classes.push("is-goal");
      info.cell.className = classes.join(" ");
      info.mark.textContent = isWall ? "#" : isStart ? "S" : isGoal ? "G" : "";
      const record = known.get(cellKey);
      info.f.textContent = record && !isWall ? "F" + record.f : "";
      info.cell.setAttribute("aria-label", "位置 " + p[0] + ", " + p[1] + (record ? "，f=" + record.f : ""));
    }
  }

  function renderFrontier() {
    frontierBody.replaceChildren();
    let best = null;
    for (const p of frontier) {
      const record = known.get(key(p));
      if (!best || record.f < best.f) best = record;
    }
    for (const p of frontier) {
      const record = known.get(key(p));
      const tr = document.createElement("tr");
      if (best && key(p) === key(best.point)) tr.className = "next-candidate";
      ["(" + p[0] + ", " + p[1] + ")", record.g, record.h, record.f, best && key(p) === key(best.point) ? "下一个" : "等待"].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.append(td);
      });
      frontierBody.append(tr);
    }
    if (frontier.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.textContent = finished ? "搜索结束" : "候选区为空";
      tr.append(td);
      frontierBody.append(tr);
    }
    expandedCount.textContent = "已扩展 " + expanded.size + " 个位置；候选区有 " + frontier.length + " 个位置。";
  }

  function addNeighborLine(text, accepted) {
    const li = document.createElement("li");
    li.textContent = text;
    li.className = accepted ? "accepted" : "skipped";
    neighborList.append(li);
  }

  function reconstruct() {
    const result = [goal];
    while (!same(result[result.length - 1], start)) {
      const parent = cameFrom.get(key(result[result.length - 1]));
      if (!parent) return null;
      result.push(parent);
    }
    return result.reverse();
  }

  function stopAuto() {
    if (timer !== undefined) window.clearInterval(timer);
    timer = undefined;
    autoButton.textContent = "自动播放";
  }

  function reset() {
    stopAuto();
    const startKey = key(start);
    frontier = [start];
    cameFrom = new Map();
    gScore = new Map([[startKey, 0]]);
    expanded = new Set();
    known = new Map([[startKey, { point: start, g: 0, h: manhattan(start), f: manhattan(start) }]]);
    current = null;
    path = null;
    round = 0;
    finished = false;
    neighborList.replaceChildren();
    addNeighborLine("还没有取出位置。", false);
    roundLabel.textContent = "第 0 轮";
    currentText.textContent = "起点 (2, 1) 已加入候选区，g=0，h=6，f=6。";
    status.textContent = "main() 已打印原始地图，并把起点交给 astar()。按“下一轮”进入 while 循环。";
    stepButton.disabled = false;
    autoButton.disabled = false;
    showCode(code.setup);
    renderBoard();
    renderFrontier();
    renderOutput();
  }

  function step() {
    if (finished) return;
    if (frontier.length === 0) {
      finished = true;
      status.textContent = "候选区已经空了，没有找到通路。";
      currentText.textContent = "搜索结束：没有可行路径。";
      stepButton.disabled = true;
      autoButton.disabled = true;
      stopAuto();
      renderFrontier();
      renderOutput();
      return;
    }

    // Strictly smaller preserves Python min()'s first item when f scores tie.
    let bestIndex = 0;
    for (let i = 1; i < frontier.length; i += 1) {
      const candidate = known.get(key(frontier[i]));
      const best = known.get(key(frontier[bestIndex]));
      if (candidate.f < best.f) bestIndex = i;
    }
    current = frontier.splice(bestIndex, 1)[0];
    round += 1;
    const currentKey = key(current);
    const record = known.get(currentKey);
    roundLabel.textContent = "第 " + round + " 轮";
    neighborList.replaceChildren();

    showCode(code.choose);
    if (same(current, goal)) {
      path = reconstruct();
      finished = true;
      showCode(code.path);
      currentText.textContent = "取出终点 (" + goal[0] + ", " + goal[1] + ")：g=" + record.g + "，h=0，f=" + record.f + "。沿 came_from 回溯，得到 " + (path.length - 1) + " 步路径。";
      status.textContent = "第 " + round + " 轮：终点以当前最低 f 被取出，A* 返回路径。";
      addNeighborLine("终点不再扩展邻居；程序开始回溯路径。", true);
      stepButton.disabled = true;
      autoButton.disabled = true;
      stopAuto();
      renderBoard();
      renderFrontier();
      renderOutput();
      return;
    }

    expanded.add(currentKey);
    const decisions = [];
    let acceptedCount = 0;
    for (const direction of directions) {
      const nextRow = current[0] + direction.dr;
      const nextCol = current[1] + direction.dc;
      const neighbor = [nextRow, nextCol];
      const neighborKey = key(neighbor);
      if (nextRow < 0 || nextRow >= height || nextCol < 0 || nextCol >= width) {
        decisions.push({ text: direction.name + "：超出地图，跳过。", accepted: false });
        continue;
      }
      if (grid[nextRow][nextCol] === "#") {
        decisions.push({ text: direction.name + "：是墙，跳过。", accepted: false });
        continue;
      }
      if (expanded.has(neighborKey)) {
        decisions.push({ text: direction.name + "：已经扩展过，跳过。", accepted: false });
        continue;
      }

      const newG = gScore.get(currentKey) + 1;
      const oldG = gScore.has(neighborKey) ? gScore.get(neighborKey) : Infinity;
      if (newG < oldG) {
        cameFrom.set(neighborKey, current);
        gScore.set(neighborKey, newG);
        const h = manhattan(neighbor);
        known.set(neighborKey, { point: neighbor, g: newG, h, f: newG + h });
        if (!frontier.some((p) => key(p) === neighborKey)) frontier.push(neighbor);
        acceptedCount += 1;
        decisions.push({ text: direction.name + " → (" + nextRow + ", " + nextCol + ")：加入/更新，g=" + newG + "，h=" + h + "，f=" + (newG + h) + "。", accepted: true });
      } else {
        decisions.push({ text: direction.name + " → (" + nextRow + ", " + nextCol + ")：已有路线更短，不更新。", accepted: false });
      }
    }

    for (const decision of decisions) addNeighborLine(decision.text, decision.accepted);
    showCode(code.update);
    currentText.textContent = "取出 (" + current[0] + ", " + current[1] + "）：g=" + record.g + "，h=" + record.h + "，f=" + record.f + "。它的邻居中有 " + acceptedCount + " 个被加入或更新。";
    status.textContent = "第 " + round + " 轮：先取最低 f，再依次检查上、右、下、左；新的候选分数已经显示在地图和表格中。";
    renderBoard();
    renderFrontier();
    renderOutput();
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
    }, 750);
  });
  resetButton.addEventListener("click", reset);
  reset();
})();
