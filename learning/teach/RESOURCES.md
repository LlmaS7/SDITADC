# 学习资源

## A* 与启发式搜索

- **[UC Berkeley CS188：Informed Search](https://inst.eecs.berkeley.edu/~cs188/textbook/search/informed.html)**  
  A* 的核心阅读材料。说明已付出的路径代价 g(n)、剩余代价估计 h(n)、总评分 f(n)=g(n)+h(n)，以及 A* 如何从候选位置中选取评分最低者继续搜索。

- **[UC Berkeley CS188：Search Project](https://inst.eecs.berkeley.edu/~cs188/sp26/projects/proj1/)**  
  后续写 A* 时参考，展示搜索问题和 Manhattan 距离启发式的实现练习。现在无需阅读。

## 多机器人路径规划

- **[Stern 等：Multi-Agent Pathfinding: Definitions, Variants, and Benchmarks](https://ojs.aaai.org/index.php/SOCS/article/view/18510)**  
  MAPF 时间步、等待动作、冲突类型和目标行为的统一术语参考。

- **[David Silver：Cooperative Pathfinding](https://ojs.aaai.org/index.php/AIIDE/article/view/18726)**  
  协作式 A* 与时空搜索的经典入门来源。

- **[Ma 等：Searching with Consistent Prioritization for Multi-Agent Path Finding](https://arxiv.org/abs/1812.06356)**  
  后续理解固定优先级规划的局限时参考；当前先看摘要即可。

## 项目地图

- **[Moving AI：MAPF Benchmark Formats](https://www.movingai.com/benchmarks/formats.html)**  
  后续加载仓库 benchmark 地图时查 .map 与场景文件格式。当前第一课不需要处理文件格式。

## 进阶原始论文

- **[Hart, Nilsson, Raphael (1968)：A Formal Basis for the Heuristic Determination of Minimum Cost Paths](https://doi.org/10.1109/TSSC.1968.300136)**  
  A* 的经典论文。等基础概念熟悉后再读，不作为入门前置材料。
