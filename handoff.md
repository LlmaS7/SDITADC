# 多机器人在线任务调度与协同路径规划项目 Handoff

> 本文档用于将前期方案讨论完整交接给后续开发人员 / Codex。  
> 当前阶段：**选题与总体技术路线基本确定，即将进入 MVP 编码阶段。**
>
> 项目核心原则：
>
> **先完成“任务产生 → 任务分配 → 多机器人无碰撞路径规划 → 动态执行 → 2D 可视化”的完整闭环。**
>
> 连续运动学、真实机器人控制、ROS2、Webots 等均为后期可选扩展，不属于第一阶段主体。

---

# 1. 项目背景

项目用于大学生智能技术应用设计类比赛。

团队约 3 人，开发周期较紧，约 20 天。

当前硬件条件有限，因此项目应：

- 以软件和算法为主体；
- 使用仿真代替真实 AGV / 移动机器人；
- 最终必须有较直观的可视化 Demo；
- 项目看起来应具有一定实际应用价值，而不是只针对某个训练集；
- 优先控制工程复杂度；
- 暂不把 ROS、SLAM、传感器、真实机器人控制作为主体。

目前最终选题方向为：

> **多机器人集群的任务调度与协同路径规划**

主要应用场景暂定：

> **智能仓储 / 多 AGV 搬运系统**

---

# 2. 当前建议项目名称

暂定：

## 面向智能仓储的多机器人在线任务调度与协同路径规划系统

英文可暂写：

**Multi-Robot Online Task Scheduling and Cooperative Path Planning System for Smart Warehousing**

后续可以根据比赛命名需求修改。

---

# 3. 项目的核心问题

整个项目主要回答以下几个问题：

1. 仓库中不断出现新的搬运任务；
2. 应该把某个任务分配给哪台机器人；
3. 每台机器人应该走哪条路径；
4. 多机器人如何避免互相碰撞；
5. 遇到拥堵、新任务或状态变化时如何重新规划；
6. 如何量化不同调度 / 路径规划算法的效果；
7. 如何以清晰的 2D 仿真方式展示整个系统。

抽象流程：

```text
新任务产生
    ↓
Task Scheduling / Assignment
    ↓
确定 Robot ↔ Task
    ↓
Multi-Agent Path Planning
    ↓
冲突检测与消解
    ↓
机器人执行
    ↓
新任务 / 状态变化
    ↓
重新调度 / 重新规划
    ↓
持续循环
```

---

# 4. 相关问题定义

项目不应仅被描述为“普通 MAPF”。

更准确的理论背景包括：

## 4.1 MAPF

MAPF：

**Multi-Agent Path Finding**

给定：

- 一张地图 / 图；
- N 个机器人；
- 每个机器人的起点；
- 每个机器人的目标点；

寻找所有机器人的无碰撞路径。

经典 MAPF：

```text
Robot 1: Start A → Goal B
Robot 2: Start C → Goal D
Robot 3: Start E → Goal F
```

目标通常一次性确定。

---

## 4.2 Lifelong MAPF

实际仓储机器人通常不会：

```text
到达一个目标
→ 所有人停止
→ 仿真结束
```

而是：

```text
完成 Task 1
↓
继续 Task 2
↓
继续 Task 3
↓
……
```

因此项目更加接近：

> **Lifelong MAPF**

机器人长期运行，目标不断发生变化。

---

## 4.3 MAPD

MAPD：

**Multi-Agent Pickup and Delivery**

尤其适合描述本项目。

一个任务可以表示为：

```text
Task:
    Pickup
       ↓
    Delivery
```

系统需要同时解决：

```text
Task Assignment
+
Multi-Agent Path Planning
```

例如：

```text
Task A
Pickup = P1
Delivery = D1

Task B
Pickup = P2
Delivery = D2
```

首先决定：

```text
Robot 1 → Task B
Robot 2 → Task A
```

然后规划：

```text
Robot → Pickup → Delivery
```

并保证机器人之间不发生冲突。

因此报告中建议写：

> 本项目参考 Multi-Agent Pickup and Delivery（MAPD）及 Lifelong MAPF 问题建模，实现在线任务分配与多机器人协同路径规划。

---

# 5. 关于“MAPF 会不会只能走格子”

这是前期讨论过的一个重要问题。

结论：

> **MAPF 本质上是在 Graph 上规划，而不是必须在二维 Grid 上规划。**

经典表示：

```text
G = (V, E)
```

其中：

- `V`：机器人可到达的位置；
- `E`：机器人允许经过的道路。

Grid 只是非常方便的一种 Graph。

例如二维网格：

```text
□─□─□
│ │ │
□─□─□
```

本质就是：

```text
A─B─C
│ │ │
D─E─F
```

现实仓储也可以抽象为道路拓扑：

```text
        Station
           A
           │
B ─── C ─── D
      │
      E
```

因此项目的核心数据结构最好不要与像素或某一种 UI 强绑定。

推荐思维：

```text
Map / Graph
↓
Nodes / Cells
↓
Planner
```

而不是：

```text
Pygame pixel
↓
Planner
```

---

# 6. 关于连续运动的当前决策

## 6.1 当前不重点研究连续运动学

此前考虑过：

```text
离散 MAPF
↓
Trajectory Generation
↓
Velocity / Acceleration
↓
Robot Dynamics
↓
Webots
```

目前该部分已经明确：

> **重要性降级。**

第一阶段不重点实现：

- Differential Drive；
- 转弯半径；
- 速度规划；
- 加速度限制；
- Trajectory Optimization；
- PID；
- MPC；
- ROS2；
- SLAM；
- Local Planner。

---

## 6.2 2D 展示仍然可以看起来连续

算法内部：

```text
t = 0: (2, 3)
t = 1: (3, 3)
```

前端可以渲染为：

```text
(2,3)
  ● ─────────→ ●
              (3,3)
```

即：

> **路径规划仍然离散，但画面通过插值连续运动。**

这样已经能够得到比较好的展示效果。

---

## 6.3 Webots 为 Optional

如果后期时间充足：

```text
MAPF Path
↓
Grid / Node coordinates
↓
World coordinates
↓
Webots Controller
↓
AGV 连续移动
```

可以进一步做 3D 仿真。

但必须保证：

> Webots 只是展示 / 执行层，不重新承担任务调度和核心 MAPF 算法。

---

# 7. 总体系统架构

推荐架构：

```text
┌─────────────────────────────────────┐
│            Environment              │
│                                     │
│ Map / Graph                         │
│ Robots                              │
│ Online Tasks                        │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│           Task Scheduler            │
│                                     │
│ Greedy                              │
│ Hungarian                           │
│ Cost-based Assignment               │
└─────────────────┬───────────────────┘
                  │
             Robot ↔ Task
                  ↓
┌─────────────────────────────────────┐
│             MAPF Planner            │
│                                     │
│ A*                                  │
│ Space-Time A*                       │
│ Reservation Table                   │
│ Priority Planning                   │
│ Optional: CBS / PIBT                │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│          Conflict Handling          │
│                                     │
│ Vertex Conflict                     │
│ Edge Conflict                       │
│ WAIT                                │
│ Priority                            │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│         Dynamic Replanning          │
│                                     │
│ Rolling Horizon                     │
│ New Tasks                           │
│ Congestion                          │
│ State Changes                       │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│          Simulation Engine          │
│                                     │
│ timestep                            │
│ robot state                         │
│ task state                          │
│ statistics                          │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│        2D Visualization Layer       │
│                                     │
│ Warehouse                           │
│ Robots                              │
│ Planned Paths                       │
│ Pickup / Delivery                   │
│ Heatmap                             │
│ Metrics                             │
└─────────────────────────────────────┘

                  │
                  │ Optional
                  ↓
             Webots / 3D
```

---

# 8. 必须坚持的模块边界

算法层与可视化层必须分离。

Planner 不应该：

- 直接调用 Pygame 绘图；
- 直接操作 Canvas；
- 使用像素坐标作为算法核心状态。

Planner 应只接受：

```text
Map
Robot states
Tasks
Constraints
```

输出：

```text
Paths
Assignments
Actions
```

例如：

```python
paths = {
    0: [(1, 1), (2, 1), (3, 1)],
    1: [(5, 4), (5, 5), (5, 6)]
}
```

Visualizer 再决定如何显示。

这样以后可以：

```text
Python Planner
      ↓
Pygame
```

替换为：

```text
Python Planner
      ↓
FastAPI
      ↓
Web Canvas
```

甚至：

```text
Python Planner
      ↓
Webots
```

核心算法均不用重写。

---

# 9. 第一阶段 MVP

目前最重要的是避免继续无限研究。

第一阶段只需要：

> **让几个机器人在二维地图中无碰撞地到达目标。**

暂时不做：

- 动态任务；
- Web；
- Webots；
- LLM；
- SOTA MAPF；
- ROS。

---

# 10. MVP Phase 1：单机器人 A*

首先自己实现基础 A*。

输入：

```text
Map
Start
Goal
```

输出：

```text
Path
```

状态：

```python
(x, y)
```

启发函数：

```text
Manhattan Distance
```

即：

```text
h(n) = |x - goal_x| + |y - goal_y|
```

完成标准：

- 可以读地图；
- 可以设置起点终点；
- 可以避开障碍；
- 找到可行路径；
- 能可视化。

---

# 11. MVP Phase 2：多机器人 Priority Planning

不建议第一个版本直接实现 CBS。

第一版 MAPF 使用：

> **Prioritized Planning + Reservation Table**

算法：

```text
Robot 1
↓
规划 path
↓
记录占用

Robot 2
↓
规划 path
↓
避开 Robot 1

Robot 3
↓
继续……
```

状态由：

```text
(x, y)
```

升级成：

```text
(x, y, t)
```

因此实际搜索类似：

> Space-Time A*

---

# 12. Reservation Table

记录机器人未来已经占用的状态：

```text
(x, y, t)
```

例如：

```text
Robot 1

t=0   (1,1)
t=1   (2,1)
t=2   (3,1)
```

Reservation Table：

```text
(1,1,0)
(2,1,1)
(3,1,2)
```

其他机器人规划时不能在相同时刻进入同一位置。

---

# 13. 必须处理的两类冲突

## 13.1 Vertex Conflict

两个机器人同一时刻位于同一节点：

```text
Robot A:
u → X

Robot B:
v → X
```

禁止：

```text
position_A(t) == position_B(t)
```

---

## 13.2 Edge Conflict

两个机器人交换位置：

```text
t = 0

A B

t = 1

B A
```

虽然每一个 timestep 都没有两个机器人占同一个格子，但现实过程中会迎面相撞。

需要禁止：

```text
A: u → v
B: v → u
```

在同一 timestep 同时发生。

---

# 14. WAIT Action

机器人动作集合不能只有：

```text
UP
DOWN
LEFT
RIGHT
```

必须包括：

```text
WAIT
```

即：

```text
(x, y, t)
→
(x, y, t+1)
```

等待是 MAPF 中非常关键的行为。

---

# 15. Goal 到达后的行为

这个问题必须统一规定。

当前建议：

> 对 Lifelong / MAPD 系统，机器人到达当前任务目标以后不会消失，而是保留在环境中等待下一任务。

即：

```text
Robot reaches Delivery
↓
Task completed
↓
Robot becomes idle
↓
Wait
↓
Receive next task
```

必须避免有人默认：

```text
到 goal 后机器人从地图删除
```

否则算法语义会不同。

---

# 16. Task 数据模型

任务推荐设计：

```python
class Task:
    id
    pickup
    delivery
    status
    assigned_robot
    created_at
```

状态可以使用：

```text
PENDING
ASSIGNED
PICKING
DELIVERING
COMPLETED
```

完整流程：

```text
PENDING
↓
ASSIGNED
↓
Robot → Pickup
↓
PICKING
↓
Robot → Delivery
↓
DELIVERING
↓
COMPLETED
```

---

# 17. Robot 数据模型

建议至少：

```python
class Robot:
    id
    position
    goal
    path
    status
    current_task
```

后期可以加入：

```python
priority
wait_time
completed_tasks
total_distance
```

状态例如：

```text
IDLE
TO_PICKUP
TO_DELIVERY
WAITING
```

---

# 18. Map 数据模型

第一阶段：

```python
class GridMap:
    width
    height
    obstacles
```

推荐统一坐标：

```text
(x, y)
```

不要同时存在：

```text
row / col
x / y
pixel_x / pixel_y
```

而没有统一约定。

建议文档里明确：

```text
x = horizontal
y = vertical

map[y][x]
```

或者：

```text
row, col
```

任选一种，但整个项目必须统一。

---

# 19. Simulation 数据模型

推荐：

```python
class Simulation:
    map
    robots
    tasks
    timestep
    scheduler
    planner
```

主循环大致：

```python
while running:

    generate_tasks()

    assign_tasks()

    plan_if_needed()

    execute_one_step()

    update_task_states()

    update_statistics()

    timestep += 1
```

---

# 20. 第一版 Task Scheduling

第一版不要复杂化。

直接：

> **Nearest Robot / Greedy**

对于一个 Task：

```text
Pickup = P
```

选择：

```text
argmin distance(robot_i, P)
```

建议距离使用：

> shortest path distance

而不是欧氏距离。

因为：

```text
直线很近
```

并不意味着：

```text
道路很近
```

---

# 21. 第二版 Task Scheduling

随后可升级：

> **Hungarian Algorithm**

当同时存在：

```text
multiple robots
+
multiple tasks
```

构造 cost matrix：

```text
          Task1 Task2 Task3
Robot1       5    10     8
Robot2       9     4     7
Robot3       6     8     3
```

求最小总代价匹配。

Python 后期可以直接考虑：

```text
scipy.optimize.linear_sum_assignment
```

---

# 22. Congestion-aware Assignment

这是非常适合项目作为“算法增强”的一个点。

普通 cost：

```text
Cij = distance(robot_i, pickup_j)
```

升级：

```text
Cij =
    α * distance
  + β * waiting
  + γ * congestion
  + δ * workload
```

考虑：

- Robot → Pickup 的实际路径；
- 当前拥堵程度；
- Robot 已经等待多久；
- Robot 当前任务负载。

意义：

> 最近的机器人不一定最快。

例如：

```text
Robot A
距离近
但前面高度拥堵

Robot B
稍远
但路径畅通
```

系统可以选择 B。

---

# 23. Dynamic Priority

基础 Prioritized Planning：

```text
Robot 1 > Robot 2 > Robot 3 > Robot 4
```

缺点：

低优先级机器人可能长时间等待。

后续可设计：

```text
Priority_i =
    α * wait_time
  + β * conflict_count
  + γ * task_urgency
```

等待越久：

```text
priority ↑
```

用于改善：

- 饥饿；
- 局部拥堵；
- 固定优先级不公平。

---

# 24. Rolling Horizon

非常适合 Lifelong MAPF。

不要一次规划未来几百步。

例如：

```text
当前 t = 50
```

只规划：

```text
t = 50 ~ 70
```

执行：

```text
5 steps
```

然后：

```text
重新规划 t = 55 ~ 75
```

循环：

```text
Plan
↓
Execute
↓
Update
↓
Plan Again
```

优点：

- 适合持续新任务；
- 适合状态动态变化；
- 降低一次性规划复杂度；
- 与 RHCR 思路一致。

---

# 25. 当前推荐算法路线

整体推荐：

```text
A*
↓
Independent A*
↓
Prioritized Planning
↓
Space-Time A*
↓
Reservation Table
↓
Dynamic Priority
↓
Rolling Horizon
↓
Congestion-aware Planning / Assignment
```

注意：

> 不要求所有内容都实现。

MVP 真正必须完成的是：

```text
A*
+
Space-Time Search
+
Reservation Table
+
Priority Planning
+
Task Assignment
```

后面的属于增强。

---

# 26. CBS 的定位

CBS：

**Conflict-Based Search**

是经典 MAPF 算法。

建议：

> 学习 + Benchmark + 对照算法。

暂不建议将 CBS 作为整个项目最主要的自研算法。

原因：

- 理论漂亮；
- 小规模表现好；
- 标准 MAPF baseline；
- 但高冲突、大机器人数量时可能出现较大搜索开销。

如果时间允许，可实现或调用现成库进行比较。

---

# 27. PIBT / ECBS / LNS2 等

后续可以了解：

- PIBT；
- ECBS；
- PBS；
- MAPF-LNS2。

但当前：

> 不应因为这些算法阻碍 MVP。

顺序必须是：

```text
能跑
↓
跑完整
↓
有 benchmark
↓
再升级算法
```

而不是：

```text
读 SOTA
↓
继续读 SOTA
↓
20 天过去
```

---

# 28. 2D 可视化方案

## 第一阶段

推荐：

> **Python + Pygame**

理由：

- 团队已有 Python 基础；
- 开发快；
- 很容易画二维 Grid；
- 很适合算法 Debug；
- 不需要额外前端栈。

第一版至少显示：

- 地图；
- 障碍物 / 货架；
- Robots；
- Goal；
- Paths；
- timestep。

---

# 29. 最终展示方案

最终推荐：

```text
Python Algorithm Backend
          ↓
       FastAPI
          ↓
     JSON / WebSocket
          ↓
      React / Vue
          ↓
     Canvas / SVG
```

但 Web 不是第一阶段必须项。

最终页面可以展示：

```text
┌────────────────────────────────────┐
│ Smart Warehouse Fleet System       │
├───────────────────────┬────────────┤
│                       │ Robots  30 │
│   Warehouse           │ Tasks  48 │
│                       │ Done   120 │
│  ● → →                │ Delay  ... │
│       ↓ ●             │ Plan   ... │
│                       │            │
├───────────────────────┴────────────┤
│ Algorithm / status / timeline      │
└────────────────────────────────────┘
```

---

# 30. 可视化建议

不要只画“机器人移动”。

应该让观众能看到算法。

建议显示：

### Robot

不同机器人显示：

```text
ID
status
current task
```

---

### Planned Path

点击机器人可以看到：

```text
Robot 7 planned path
```

---

### Conflict

出现潜在冲突：

```text
⚠ Conflict
```

然后显示：

```text
Robot A waits
Robot B proceeds
```

---

### Pickup / Delivery

分别用不同 marker：

```text
P
D
```

---

### Heatmap

统计每个 Cell / Edge 的历史或当前流量。

展示：

> Traffic / Congestion Heatmap

非常适合作为比赛 Demo。

---

# 31. 建议最终做两个 View

## Algorithm View

重点：

- Grid；
- Path；
- Reservation；
- Conflict；
- Priority；
- timestep。

用于讲算法。

---

## Warehouse View

重点：

- 仓储货架；
- AGV；
- Task；
- Heatmap；
- KPI；
- Throughput。

用于展示项目完成度。

---

# 32. 现成地图：MovingAI MAPF Benchmark

无需自己从零画所有测试地图。

推荐使用：

> **MovingAI MAPF Benchmark**

常见地图类型：

```text
warehouse
maze
room
random
```

尤其适合本项目：

```text
warehouse-*
```

---

## 文件类型

### `.map`

地图：

```text
@@@@@@@@@@@@
@..........@
@..@@@@....@
@..........@
@@@@@@@@@@@@
```

一般：

```text
@ = obstacle
. = traversable
```

具体解析应按照对应 MovingAI 格式实现。

---

### `.scen`

提供测试 scenario：

```text
start
goal
```

可用于：

```text
5 robots
10 robots
20 robots
50 robots
...
```

做 MAPF Benchmark。

---

# 33. MovingAI 的用途

主要用于：

> **经典 MAPF 算法测试。**

即：

```text
Map
+
Start / Goal
+
N robots
```

然后比较：

```text
Independent A*
Prioritized Planning
CBS
Our Planner
```

不要把 MovingAI 当完整仓储业务系统。

它主要解决：

> 标准化地图和测试场景。

---

# 34. 动态 Task 数据

MovingAI 自带 scenario 不等同于 MAPD 动态任务。

项目后续需要自己生成：

```text
Task:
pickup
delivery
created_at
```

例如：

```python
Task(
    pickup=(3, 5),
    delivery=(20, 14),
    created_at=37
)
```

可以：

- 随机生成；
- 从固定 seed 生成；
- 后期参考 League of Robot Runners benchmark。

---

# 35. League of Robot Runners

League of Robot Runners：

> 不是一个单独的软件。

更准确来说是：

> **一个围绕多机器人 Task Scheduling、Path Planning、Execution Control 构建的竞赛 / Benchmark / Research Ecosystem。**

大致包括：

```text
League of Robot Runners
│
├─ Start-Kit
├─ Benchmark Archive
├─ PlanViz
├─ Code Archive
└─ Competition framework
```

---

# 36. LoRR 对本项目的价值

最值得研究的是：

> **Start-Kit**

因为其中有非常明确的模块：

```text
TaskScheduler
MAPFPlanner
Simulation
Environment
```

这和本项目架构非常接近。

推荐用途：

> **作为系统架构参考。**

不建议当前直接在 LoRR Start-Kit 上开始整个项目。

原因：

初学阶段容易被：

```text
SharedEnvironment
TaskScheduler
MAPFPlanner
competition interfaces
```

等大量框架代码绕进去。

推荐顺序：

```text
自己实现小型 MVP
↓
理解 Task / Robot / Planner
↓
再读 LoRR
↓
借鉴接口与 benchmark
```

---

# 37. PlanViz

LoRR 生态中的：

> 多机器人方案可视化工具。

可以用于：

- 查看 path；
- 查看 agent movement；
- 查看 collision；
- 查看 delay；
- 查看 task event。

推荐：

> 作为参考和 Debug 工具。

最终比赛展示仍建议自制 UI。

---

# 38. RHCR

重要参考项目：

> **Rolling-Horizon Collision Resolution**

相关方向：

> Lifelong MAPF in large-scale warehouses

非常适合学习：

```text
planning window
simulation window
replanning
lifelong MAPF
```

推荐用途：

> 理解为什么 Lifelong MAPF 适合 Rolling Horizon。

不要第一天就尝试完整复现。

---

# 39. MAPD 经典论文

建议了解：

> Lifelong Multi-Agent Path Finding for Online Pickup and Delivery Tasks

核心意义：

正式定义：

```text
online tasks
+
pickup
+
delivery
+
task assignment
+
collision-free path planning
```

这基本就是本项目的问题背景。

---

# 40. libMultiRobotPlanning

值得研究的开源库。

包含例如：

```text
A*
SIPP
CBS
ECBS
CBS-TA
ECBS-TA
Task Assignment
```

用途：

- 学习算法实现；
- 对比 baseline；
- 理解 Task Assignment + Path Finding；
- 后期 benchmark。

---

# 41. LSMART

LSMART：

> Lifelong Scalable Multi-Agent Realistic Testbed

主要解决传统 MAPF 和真实机器人物理执行之间的 gap，例如：

- Differential-drive；
- acceleration；
- velocity；
- execution uncertainty。

当前项目：

> **只作为未来扩展参考。**

不是第一阶段开发重点。

---

# 42. MAPF-LNS2

用于了解：

> 大规模 MAPF。

采用 Large Neighborhood Search 类思路。

可以作为：

> 后期高级算法参考。

当前不建议自行实现。

---

# 43. 项目评价指标

必须在开发早期就定义。

否则最终容易只剩：

> “动画挺漂亮。”

至少统计：

## Success Rate

```text
成功完成任务比例
```

---

## Planning Time

算法一次规划所需时间。

---

## Makespan

对于静态 MAPF：

> 所有机器人完成目标的时间。

---

## Sum of Costs

所有机器人总代价：

```text
Σ path_length
```

---

## Average Delay

由于协同避碰带来的额外等待。

---

## Throughput

Lifelong / MAPD 最重要指标之一：

```text
completed_tasks / simulation_time
```

---

## Waiting Time

机器人平均等待时间。

---

## Replanning Count

动态重规划次数。

---

## Conflict Count

可以统计：

```text
detected conflicts
resolved conflicts
```

最终实际执行应该保证：

```text
collision = 0
```

---

# 44. Benchmark 实验设计

至少考虑以下地图：

```text
warehouse
maze
room
random
```

不同规模：

```text
5 robots
10 robots
20 robots
50 robots
```

如果性能允许：

```text
100 robots
```

不要为了数量硬凑。

---

# 45. 算法对照建议

例如：

```text
Independent A*
```

作为：

> 无多机器人协调 baseline。

然后：

```text
Prioritized Planning
```

作为基础 MAPF。

再和：

```text
Improved Planner
```

比较。

有时间可以加入：

```text
CBS
```

作为标准 MAPF benchmark。

---

# 46. Random Seed

所有算法比较必须：

> 使用相同的实例。

例如：

```python
random.seed(42)
```

同一次 benchmark：

- map 相同；
- robot starts 相同；
- goals 相同；
- tasks 相同。

否则实验不公平。

---

# 47. 主要容易踩的坑

## 47.1 忘记 Edge Conflict

只检测：

```text
same position
```

不够。

必须检测：

```text
u → v
v → u
```

交换冲突。

---

## 47.2 忘记 WAIT

WAIT 是必要 Action。

---

## 47.3 起点冲突

随机生成机器人时不能：

```text
Robot A start == Robot B start
```

---

## 47.4 Goal 占用

机器人完成目标以后如何处理必须统一。

---

## 47.5 无限搜索

Space-Time A* 如果没有时间范围限制：

```text
t → ∞
```

可能导致异常。

需要：

- planning horizon；
- max timestep；
- Rolling Horizon。

---

## 47.6 Priority Starvation

固定 priority：

```text
Robot 1 > Robot 2 > Robot 3
```

可能导致低优先级长时间等待。

后期考虑：

- dynamic priority；
- wait-time compensation。

---

## 47.7 狭窄通道

例如：

```text
██████████
A →    ← B
██████████
```

是 MAPF 很典型的困难区域。

必须专门测试：

- corridor；
- bottleneck；
- high-density warehouse。

---

## 47.8 不要只测试空旷地图

空地图可能让任何算法都很好看。

真正需要测试：

```text
warehouse
maze
narrow corridor
high robot density
```

---

## 47.9 Task Assignment 不应该只看欧氏距离

应该至少考虑：

> shortest path distance

因为障碍物会导致：

```text
Euclidean near
but path far
```

---

## 47.10 前端坐标污染算法层

禁止 Planner 依赖：

```text
pixel_x
pixel_y
```

算法使用：

```text
grid position / node id
```

UI 自己转换。

---

# 48. 第一阶段推荐 Repository 结构

建议先简单：

```text
multi_robot_project/
│
├── README.md
├── AGENTS.md
├── docs/
│   ├── HANDOFF.md
│   ├── architecture.md
│   └── references.md
│
├── assets/
│   └── maps/
│
├── src/
│   ├── map/
│   │   ├── grid_map.py
│   │   └── movingai_loader.py
│   │
│   ├── models/
│   │   ├── robot.py
│   │   └── task.py
│   │
│   ├── planning/
│   │   ├── astar.py
│   │   ├── space_time_astar.py
│   │   ├── reservation_table.py
│   │   └── prioritized_planner.py
│   │
│   ├── scheduling/
│   │   ├── greedy.py
│   │   └── hungarian.py
│   │
│   ├── simulation/
│   │   ├── simulator.py
│   │   └── metrics.py
│   │
│   └── visualization/
│       └── pygame_view.py
│
├── tests/
│
└── main.py
```

注意：

> 第一周不要为了目录架构本身投入太多时间。

如果觉得太复杂，可以先压成：

```text
src/
├── astar.py
├── planner.py
├── robot.py
├── task.py
├── simulation.py
└── visualization.py
```

以后再重构。

---

# 49. 推荐统一接口

## Planner

```python
planner.plan(
    graph,
    robots,
    goals,
    reservations
)
```

输出：

```python
dict[robot_id, path]
```

---

## Scheduler

```python
scheduler.assign(
    robots,
    pending_tasks,
    graph
)
```

输出：

```python
dict[robot_id, task_id]
```

---

## Simulator

```python
sim.step()
```

一次只推进一个 timestep。

---

## Visualization

```python
view.render(sim_state)
```

只读取状态。

---

# 50. 三人分工建议

## 成员 A：Path Planning

负责：

- A*；
- Space-Time A*；
- Reservation Table；
- Vertex Conflict；
- Edge Conflict；
- Prioritized Planning；
- 后期 Dynamic Priority / Rolling Horizon。

---

## 成员 B：Task + Simulation

负责：

- Robot；
- Task；
- Task Generator；
- Task Scheduler；
- Greedy；
- Hungarian；
- Simulation Loop；
- Metrics；
- Benchmark。

---

## 成员 C：Visualization + Integration

负责：

- Pygame MVP；
- warehouse visualization；
- Robot animation；
- paths；
- task markers；
- Heatmap；
- 后期 Web UI。

---

## 所有人必须共同明确

以下数据格式：

```text
position
path
task
robot
timestep
map
```

否则非常容易集成失败。

---

# 51. 20 天开发建议

## Day 1–3

目标：

```text
MovingAI / simple map
+
A*
+
Pygame
```

实现：

- 地图；
- 障碍；
- 单机器人；
- Path；
- Animation。

---

## Day 4–6

实现：

```text
multi-robot
+
space-time
+
reservation
```

至少：

- 3~5 Robots；
- Vertex conflict；
- Edge conflict；
- WAIT；
- Prioritized Planning。

---

## Day 7–9

加入：

```text
Task
+
Pickup
+
Delivery
+
Greedy Scheduling
```

完成：

```text
Task appears
↓
robot receives task
↓
robot reaches pickup
↓
robot reaches delivery
↓
task complete
```

---

## Day 10–12

进入 Lifelong：

- Task 持续产生；
- Robot 完成任务继续接单；
- 动态重新规划；
- Planning Horizon。

---

## Day 13–15

算法升级：

优先考虑：

- Hungarian；
- Dynamic Priority；
- Rolling Horizon；
- Congestion Cost。

不要全部做。

选其中最有效的几个。

---

## Day 16–18

做最终 UI：

优先：

```text
2D Warehouse
```

加入：

- Robot continuous interpolation；
- Paths；
- Task；
- Heatmap；
- Status；
- Metrics。

如果 Pygame 已经够漂亮，可以不强制迁 Web。

---

## Day 19

Benchmark：

```text
warehouse
maze
room
```

生成：

- chart；
- table；
- result log。

---

## Day 20

只做：

- Fix；
- Demo；
- PPT；
- README；
- 视频；
- 备份。

不要增加新算法。

---

# 52. 第一阶段开发的最小目标

不要现在想着最终系统。

第一阶段只需要：

> **20 × 20 Grid + Obstacles + A* + 3 Robots + Pygame Animation**

随后：

> **3 个机器人无碰撞到达目标。**

这是当前最重要的 milestone。

---

# 53. 最推荐的学习方式

不要：

```text
先系统学习完 MAPF
↓
再学 MAPD
↓
再学 RHCR
↓
再学 CBS
↓
再开始写代码
```

应该：

```text
写 A*
↓
遇到多机器人冲突
↓
学 Reservation Table
↓
遇到等待问题
↓
加入 WAIT
↓
遇到拥堵
↓
学 Priority / Rolling Horizon
↓
遇到 Task
↓
再研究 MAPD
```

即：

> **Problem-driven learning**

---

# 54. 当前 Must Have

项目主体必须完成：

```text
✓ Warehouse / Grid / Graph
✓ Robots
✓ Online Tasks
✓ Pickup / Delivery
✓ Task Assignment
✓ Multi-Agent Path Planning
✓ Collision Avoidance
✓ WAIT
✓ Dynamic Execution
✓ 2D Visualization
✓ Basic Metrics
```

---

# 55. Should Have

优先增强：

```text
○ Hungarian Assignment
○ Space-Time A*
○ Reservation Table
○ Dynamic Priority
○ Rolling Horizon
○ Congestion-aware Cost
○ Heatmap
○ MovingAI Benchmark
```

其中 Space-Time / Reservation 实际大概率会成为核心。

---

# 56. Nice to Have

时间足够再做：

```text
△ CBS Benchmark
△ PIBT Benchmark
△ Robot temporary failure
△ Task burst
△ Web frontend
△ FastAPI
△ WebSocket
△ LLM Assistant
```

---

# 57. Optional / Future Work

当前不属于主体：

```text
△ Webots
△ Continuous trajectory planning
△ Differential drive model
△ Velocity constraints
△ Acceleration constraints
△ ROS2
△ Nav2
△ SLAM
△ Real robot
```

---

# 58. 当前明确不建议做的内容

在主体完成前暂时禁止扩散到：

```text
× Reinforcement Learning
× VLM
× Camera
× Object Detection
× SLAM
× ROS2 full stack
× 自研复杂 SOTA MAPF
× 3D 优先于算法
```

这些非常容易让项目失控。

---

# 59. 项目的“创新 / 改进”应该从哪里来

不需要声称提出全新的 MAPF 理论。

可以从系统结合角度产生亮点。

当前最推荐的两个：

## 方案 A

> **Congestion-aware Task Assignment**

让 Scheduler 不只看：

```text
distance
```

而考虑：

```text
distance
+
traffic congestion
+
waiting time
```

---

## 方案 B

> **Dynamic Priority + Rolling Horizon**

用于：

- 减少饥饿；
- 动态任务；
- 实时重新规划；
- 降低大规模规划压力。

---

# 60. 项目可能最终描述

可以表达成：

> 本项目针对智能仓储环境中的多机器人长期任务执行问题，构建在线任务调度与协同路径规划系统。系统参考 MAPD 与 Lifelong MAPF 建模，在在线任务到达条件下完成机器人任务分配，并通过时空路径规划和冲突消解实现多机器人无碰撞协同运行。进一步考虑动态优先级、滚动时域和拥堵感知代价，提高高密度场景下的任务吞吐效率。最终通过二维仓储仿真系统实时展示机器人、任务、规划路径、拥堵状态及运行指标。

---

# 61. 推荐重点参考资料

## MovingAI MAPF Benchmark

用途：

- 标准地图；
- `.map`；
- `.scen`；
- MAPF benchmark。

重点：

```text
warehouse
maze
room
random
```

主页：

https://movingai.com/benchmarks/mapf.html

---

## League of Robot Runners

用途：

- 参考完整系统；
- Task Scheduler；
- MAPF Planner；
- Lifelong simulation；
- Benchmark；
- PlanViz。

重点：

> Start-Kit

GitHub 组织：

https://github.com/MAPF-Competition

---

## RHCR

Rolling-Horizon Collision Resolution。

用途：

- Lifelong MAPF；
- Rolling Horizon；
- warehouse；
- dynamic replanning。

项目：

https://github.com/Jiaoyang-Li/RHCR

---

## libMultiRobotPlanning

用途：

- A*；
- SIPP；
- CBS；
- ECBS；
- Task Assignment。

项目：

https://github.com/whoenig/libMultiRobotPlanning

---

## MAPF-LNS2

用途：

- 大规模 MAPF；
- Large Neighborhood Search；
- advanced benchmark。

项目：

https://github.com/Jiaoyang-Li/MAPF-LNS2

---

## PIBT

用途：

- Priority-based MAPF；
- Priority inheritance；
- Backtracking。

项目：

https://github.com/Kei18/pibt

---

## LSMART

用途：

- MAPF 与现实机器人动力学之间的桥梁；
- 后期参考。

项目：

https://github.com/smart-mapf/lifelong-smart

---

# 62. 当前不应被误解的几点

## 本项目不是 ML 项目

MAPF：

> 主要属于搜索 / 规划 / 组合优化。

因此没有典型：

```text
training set
test set
generalization
```

这种核心逻辑。

---

## MovingAI 不是训练集

MovingAI 更准确说是：

> Benchmark instances / maps / scenarios。

---

## MAPF 不是“只能走格子”

Grid：

> 是 Graph 的一种实现。

---

## 2D 仿真并不意味着算法没有实际价值

算法解决的是：

> 高层全局协同规划。

真实机器人最终还需要：

```text
MAPF
↓
Trajectory
↓
Controller
```

但后两层目前属于 Future Work。

---

# 63. 当前最大风险

项目最大的风险不是：

> 算法太简单。

而是：

> 范围不断扩张。

典型危险：

```text
MAPF
↓
Webots
↓
ROS2
↓
Nav2
↓
SLAM
↓
视觉
↓
LLM
↓
强化学习
```

最终每个都做一点，没有任何一个完整。

必须坚持：

> **先闭环，再增强。**

---

# 64. 当前第一优先级

截至本 Handoff：

不要继续大范围调研。

下一步立即进入：

```text
MovingAI / simple grid
        ↓
A*
        ↓
Pygame
        ↓
3 robots
        ↓
Reservation Table
        ↓
No collision
```

完成后再讨论 Task。

---

# 65. 建议 Codex 接手后的第一任务

Codex / 后续开发人员看到本文档后：

## 第一步

创建基础 Python 项目。

---

## 第二步

实现 MovingAI `.map` loader。

如果该步骤阻碍开发：

> 暂时先 hard-code 一个 20×20 grid。

不要因为文件解析阻碍 A*。

---

## 第三步

实现：

```text
A*
```

API 尽量保持简单：

```python
find_path(grid, start, goal)
```

---

## 第四步

实现简单 Pygame：

```text
Map
Robot
Goal
Path
```

---

## 第五步

升级：

```text
Space-Time A*
+
Reservation Table
```

做到：

> 3~5 robots 无碰撞到达目标。

---

## 第六步

开始 Task / MAPD。

---

# 66. 开发原则

整个项目开发期间遵守：

> **能简单就不复杂。**

> **算法模块和 UI 模块分离。**

> **每增加一个新 feature 前，保证上一层已经能稳定运行。**

> **Benchmark 必须可复现。**

> **尽早可视化。**

> **不要为了“看起来高级”增加不必要的技术栈。**

---

# 67. 最终目标

项目完成时，应能够启动一个程序：

```text
Launch Simulation
```

用户看到：

```text
仓库地图
+
大量机器人
+
持续产生 Task
+
自动 Task Assignment
+
无碰撞协同运动
+
路径动态变化
+
拥堵区域
+
任务完成情况
+
性能统计
```

能够切换或比较：

```text
基础算法
vs
改进算法
```

并通过 benchmark 数据说明：

> 改进算法在哪些场景、哪些指标上带来了变化。

最终形成：

```text
问题定义
↓
基础算法
↓
发现问题
↓
方法改进
↓
Benchmark
↓
可视化系统
↓
实际应用解释
```

这就是整个项目最重要的故事线。

---

# 68. 一句话交接

如果只能保留一句话：

> **先用 Python 做出一个 MAPD / Lifelong MAPF 的二维智能仓储仿真：任务持续产生，Scheduler 给机器人派单，MAPF Planner 负责无碰撞路径，Simulation 按 timestep 执行，Pygame/Web 负责可视化；先跑通 A* → Space-Time A* → Reservation Table → Task Assignment 的完整闭环，再考虑 Rolling Horizon、拥堵感知、Web UI 或 Webots。**