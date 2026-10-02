# SDITADC 项目说明

> 本文面向团队成员和后续 AI，概括项目目标、当前文件状态、已完成内容与建议学习/开发顺序。
> 整理日期：2026-10-02。详细技术方案见 [handoff.md](handoff.md)。

## 1. 项目目标

项目面向大学生智能技术应用设计类比赛，目标是实现一个智能仓储多机器人仿真系统：

**在线搬运任务 → 任务分配 → 多机器人无碰撞路径规划 → 仿真执行 → 二维可视化与指标统计**

暂定英文名：Multi-Robot Online Task Scheduling and Cooperative Path Planning System for Smart Warehousing。handoff.md 中的约 3 人、约 20 天是早期规划假设，交接时应确认是否仍适用。

- **MAPF**：多机器人在地图上同时规划无冲突路径。
- **MAPD / Lifelong MAPF**：机器人持续接收取货、送货等任务，而不是只完成一轮固定目标。

先完成离散网格上的算法与系统闭环。真实机器人、连续运动学、ROS、SLAM、Webots 和大型前沿算法是后续可选方向，不是当前 MVP 的前置条件。

## 2. 当前状态：已有与未实现

| 模块 | 当前状态 |
|---|---|
| Python 环境 | .venv 已存在；Python 3.14.5；已安装 pygame-ce 2.5.8。 |
| 单机器人 A* 可视化 | 根目录 temp.py 中已有单机器人 A* 和 Pygame 步进/自动搜索界面，读取小型文本地图。本次整理未重新运行确认。 |
| 单机器人文本程序 | learning/teach/astar_text.py 已创建：内置小地图，用 A* 找路并在终端打印路径。本次整理未运行确认。 |
| A* 学习材料 | learning/teach/lessons/0001-astar-search-basics.html，含交互式网格演示；样式和脚本在 learning/teach/assets/。 |
| 学习地图 | maps/learning/astar_grid.txt，供 temp.py 使用。 |
| MovingAI 地图 | 已保存一张仓库地图及其静态场景；当前程序尚未加载该基准 .map。 |
| 多机器人避碰 | 尚未实现。 |
| Pickup/Delivery 任务与任务分配 | 尚未实现。 |
| 在线任务、持续执行与统计指标 | 尚未实现。 |
| 工程结构 | 目前仍是少量脚本和数据文件；还没有独立的 map、planner、scheduler、simulator 模块。 |
| Git 与依赖清单 | 当前目录未检测到 Git 仓库，也没有项目级 requirements.txt 或 pyproject.toml。 |

**重要区分：** handoff.md 记录的是目标方案和建议路线，不代表这些模块已经完成。

## 3. 目录说明

    SDITADC/
    ├── README.md                         项目现状与交接入口
    ├── handoff.md                        完整方案、风险、架构和比赛开发建议
    ├── temp.py                           单机器人 A* 的 Pygame 演示程序
    ├── .venv/                            项目 Python 虚拟环境
    ├── assets/                           当前为空，项目视觉资源可放这里
    ├── maps/
    │   ├── learning/astar_grid.txt       temp.py 使用的小型字符地图
    │   └── movingai/                     仓库地图、场景及原始压缩包
    └── learning/teach/                   学习资料与小型练习程序
        ├── MISSION.md                    学习目的和范围
        ├── NOTES.md                      学习进度与用户偏好
        ├── RESOURCES.md                  可信学习资料索引
        ├── GLOSSARY.md                   已确认掌握的术语
        ├── astar_text.py                 纯文本 A* 程序
        ├── assets/                       HTML 课程共享样式和演示脚本
        └── lessons/
            └── 0001-astar-search-basics.html

## 4. 环境与运行方式

在项目根目录的 PowerShell 中运行：

    ./.venv/Scripts/python.exe learning/teach/astar_text.py
    ./.venv/Scripts/python.exe temp.py

也可以先激活环境：

    ./.venv/Scripts/Activate.ps1
    python learning/teach/astar_text.py
    python temp.py

- 纯文本程序只用 Python 标准库，不需要 pygame。
- temp.py 使用 pygame；环境安装的发行包名是 pygame-ce，代码仍写 import pygame。
- temp.py 的按键：Space 单步搜索，A 自动搜索/暂停，R 重置，Q 或 Esc 退出。
- HTML 学习页在浏览器中打开 learning/teach/lessons/0001-astar-search-basics.html；需要保留相对位置的 course.css 和 astar-demo.js。

本 README 的整理过程只检查了文件和环境信息，没有运行程序或测试。

## 5. 地图与数据

### 学习地图

maps/learning/astar_grid.txt 是小型字符地图，使用 # 表示障碍、. 表示通路、S 表示起点、G 表示目标。temp.py 要求地图为等宽文本，并且恰有一个起点和一个目标。

learning/teach/astar_text.py 暂时使用代码内置的 7×9 小地图。终端显示符号：# 墙、. 空地、S 起点、G 终点、* 路径。

坐标约定需要留意：temp.py 使用 (x, y)，也就是 (列, 行)；文本练习程序使用 (行, 列)。MovingAI 的原点在左上角，场景坐标以列、行给出。将地图或规划器接起来前，应统一坐标约定。

### MovingAI 仓库数据

数据目录：maps/movingai/warehouse-10-20-10-2-1/

- .map 文件：161 列 × 63 行。
- scenarios/even/：25 个静态起终点场景。
- scenarios/random/：25 个静态起终点场景。
- source_archives/：来源 ZIP 压缩包。
- 同目录 README.md 记录来源、许可和格式注意事项。

这些 .scen 是静态 MAPF 起终点实例，不是 Pickup/Delivery 任务。其参考路径长度采用对角移动代价；若项目使用四方向移动，应读取起终点并按项目规则重新计算。MovingAI 地图中 . 和 G 可通行，@、O、T 为障碍；S、W 是需要项目另行定义语义的特殊地形。

来源为 MovingAI MAPF Benchmark。分发或改编地图时应保留来源归属，并遵循地图目录 README 中列出的 Open Data Commons Attribution License。

## 6. 已学内容与当前学习阶段

学习工作区在 learning/teach/。教学以项目问题为线索，边学边做，不要求先学完 MAPF 理论。

已经讲解的 A* 内容：

- 网格位置与可通行邻居。
- 路径评分：f(n) = g(n) + h(n)。
- 四方向等步长网格中的曼哈顿距离。
- 从候选位置中取 f 最小者并扩展相邻格子。
- 记录前驱位置，找到目标后还原路径。

当前正从概念进入小程序。纯文本 A* 程序已创建，但还没有确认学习者运行结果或独立理解情况；不要将看过课程记录成已掌握。

### 建议的下一步学习顺序

1. **运行并读懂 astar_text.py**：从地图表示开始，再看候选区、g/h/f、邻居检查和路径还原。
2. **用小地图巩固 A***：改起点、终点和障碍，理解有路、绕路与无路时程序怎样响应。
3. **加载字符地图文件**：让规划器读取 astar_grid.txt，再学习 MovingAI .map 的文件头、坐标和地形字符。
4. **连接单机器人可视化**：理解 temp.py 如何把地图坐标转换成格子绘图，并保持算法与绘图分开。
5. **多机器人固定目标**：学习优先规划、时空位置、Reservation Table、顶点冲突、对向换边冲突、等待动作和目标占用。
6. **加入任务与持续执行**：定义 Robot、Task、Pickup、Delivery，先做简单任务分配，再让新任务持续到达。
7. **补齐仿真与评估**：统一 timestep、机器人/任务状态，记录成功率、规划耗时、总路径代价、等待时间、吞吐量和冲突数。
8. **做可复现的对比与展示**：固定地图、场景和随机种子，再比较基础与改进方案；最后完善二维演示和比赛说明。

每一阶段都保持程序规模可读，只在遇到实际问题时引入下一项概念。

## 7. 建议的项目实现路线

**单机器人 A* → 多机器人优先规划 → Space-Time A* 与 Reservation Table → Pickup/Delivery 与任务分配 → 在线任务和滚动仿真 → 指标与基准比较 → 最终演示**

模块边界建议：

- **Map/Graph**：可通行位置、邻接关系、坐标与地图解析。
- **Planner**：接收地图、机器人状态、目标和规划约束；不负责 Pygame 绘图。
- **Scheduler**：把任务分给机器人。
- **Simulator**：按离散时间推进机器人与任务状态。
- **Visualization**：绘制地图、路径、机器人、任务和指标。

优先跑通几个机器人无碰撞到达目标，再加入任务。核心闭环完成前，不扩张到 ROS、SLAM、真实运动学、Webots、LLM 或复杂前沿算法。

## 8. 面向后续协作者 / AI 的接手说明

1. 先读本 README；需要完整背景时再读 handoff.md。
2. 区分当前已有文件和 handoff 中规划的功能，不要把计划写成完成状态。
3. 当前学习者正在入门 A*，刚开始写纯文本程序。使用中文讲解，保持小型可运行步骤；可以合并相关概念讲清楚，不要一次生成大型交互程序。
4. 当前先用终端文本渲染地图；不要自动把这一步升级成 Pygame、Web 或多机器人功能。
5. 只有在用户理解和当前阶段需要时，再引入新的算法/术语；不主动安排测验。
6. 实现时保持 Planner 与 UI 分离，先完成一个可展示的闭环，再增加算法。

## 9. 主要参考

- MovingAI MAPF Benchmark：https://www.movingai.com/benchmarks/mapf/index.html
- MovingAI 格式说明：https://www.movingai.com/benchmarks/formats.html
- Berkeley CS188 A* / Informed Search：https://inst.eecs.berkeley.edu/~cs188/textbook/search/informed.html
- 完整技术方案、风险清单、接口建议、指标和参考项目：[handoff.md](handoff.md)
- 个性化学习任务与进度：[learning/teach/MISSION.md](learning/teach/MISSION.md)、[learning/teach/NOTES.md](learning/teach/NOTES.md)
