# MovingAI MAPF 仓库地图

此目录保存 MovingAI Lab 的 `warehouse-10-20-10-2-1` MAPF 基准地图及配套静态场景。

## 来源与许可

- 数据来源：[MovingAI MAPF Benchmark](https://www.movingai.com/benchmarks/mapf/index.html)
- 格式说明：[MovingAI Benchmark Formats](https://www.movingai.com/benchmarks/formats.html)
- 来源页面注明数据采用 [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/)。分发或改编这些数据时，请保留来源归属。

## 目录内容

- `warehouse-10-20-10-2-1.map`：仓库网格地图，161×63。
- `scenarios/even/`：25 个 even 场景文件。
- `scenarios/random/`：25 个 random 场景文件。
- `source_archives/`：从官方来源下载的原始 ZIP 档案，便于追溯和重新解压。

每个 `.scen` 文件提供静态 MAPF 的起点、终点实例；它们不包含 Pickup/Delivery 任务。场景的参考路径长度采用对角移动代价；如果项目采用四方向移动，请先使用起终点坐标，忽略参考长度。

## 地图字符

MovingAI 地图包含文件头和 ASCII 网格，坐标原点在左上角。网格中 `.` 和 `G` 为可通行；`@`、`O`、`T` 为障碍/不可通行。格式中的 `S`、`W` 属于特殊地形，需要在规划器中另外定义语义。
