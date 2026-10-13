# SDITADC v0.2.1_preview

三机器人仓库 HTML 预览版，拆分为面向使用者的主窗口和独立调试窗口。主窗口同时显示 **Three.js 3D、Canvas 2D 和任务列表**，调试窗口集中提供测试操作与内部运行信息。原 `v0.2_preview/` 已原地升级并改名为 `v0.2.1_preview/`。

## 启动

本机环境已经安装，双击 **`launch.bat`** 即可。默认打开最大化的主窗口；点击右上角 **“调试窗口”** 打开独立调试窗口。页面就绪后开始执行普通任务。

重复点击入口会显示已打开的调试窗口，不会创建另一套仿真。关闭调试窗口不影响主窗口，可以再次打开；关闭主窗口会一并关闭调试窗口和本次后台服务。

双击默认启动不会保留额外命令行窗口；有启动错误时会提示日志位置。需要控制台诊断或其他参数时使用下面的命令。

在本目录启动：

```powershell
.\.venv\Scripts\python.exe main.py
```

另一台 Windows 电脑首次使用时重建环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

本机验证环境：Python 3.14.5、pywebview 6.2.1、pythonnet 3.2.1、Microsoft WebView2 Runtime。独立窗口需要 WebView2；3D需要WebGL 2。pywebview在Windows还使用.NET运行时，由其依赖负责桥接。

Three.js 0.186.1及OrbitControls已保存在 `frontend/vendor/`，附MIT许可及来源记录。运行不需要Node.js、npm、外部CDN、Vite或前端构建步骤。请使用启动入口；直接双击 `index.html` 无法连接仿真接口。

## 主窗口：仓库运行

- 3D：拖动旋转、滚轮缩放、恢复视角。简化货架、障碍及三个机器人带编号、载货箱和紧急提示。
- 2D：网格、作业点、机器人和路线，与3D使用同一位置插值和时间步。
- 任务按编号升序排列，显示状态和执行机器人；支持全部、未完成、已完成筛选。
- 点击任务同时高亮3D和2D的取送位置；已完成任务也可查看。可点击“清除高亮”。
- 提升等级、设为紧急、取消任务沿用原规则。取消后从列表移除，内部记录保留，编号不重排。
- 保留暂停/继续、速度、任务筛选、提升等级、设为紧急和取消任务等日常操作。
- 顶部只呈现运行状态、已完成、执行中和待处理数量；机器人卡显示阶段、任务和完成数量。内部时间步、种子、规划耗时、CBS节点和分配代价移到调试窗口。
- 主窗口的空格快捷键控制暂停/继续。单步、任务注入、保存等调试快捷键仅在调试窗口生效。
- 默认9个普通任务，自动生成关闭；开启后每45步新增普通任务。仅提供普通场景预设。
- 加载、重置后暂停。保存及正常退出写入本版本 `outputs/last_scenario.json` 与 `outputs/last_run.json`。
- 场景是输入事件回放，不是中途状态恢复。支持读取0.1、0.2场景，默认加载路径在本版本内；保存版本号为 `0.2.1_preview`。

## 调试窗口：操作与信息

- 按钮：随机任务、自定义任务、自动生成开关、单步、重试规划、保存记录、加载记录、按种子重置场景。也提供同步的暂停和速度控制。
- 信息：仿真时刻、地图种子和尺寸、场景轮次、快照编号、任务记录数量、输入回放状态、规划耗时、CBS节点、规划/恢复次数、路程、等待、抢占、分配代价和机器人内部状态。
- 仅显示调试操作与数据，不重复显示3D、2D或主窗口的任务卡列表。
- 打开自定义任务窗口会暂停同一仿真；创建完成后可在任一窗口继续。调试窗口快捷键：空格暂停/继续，N单步，A随机任务，R重试，S保存。
- 关闭或重新打开调试窗口均保持任务和仿真状态。调试操作提交给同一控制器，主窗口自动更新。

## 其他运行方式

```powershell
# 独立窗口，初始暂停
.\.venv\Scripts\python.exe main.py --paused

# 启动时同时打开主窗口与调试窗口
.\.venv\Scripts\python.exe main.py --debug-window

# 普通浏览器模式，主页面也提供独立调试页面入口
.\.venv\Scripts\python.exe main.py --browser

# 只提供本机服务，不打开窗口
.\.venv\Scripts\python.exe main.py --serve --paused

# 无界面验证普通自动任务
.\.venv\Scripts\python.exe main.py --headless --ticks 1200 --auto

# 隐藏原生双窗口检查实际绘制、共享命令和关闭重开行为
.\.venv\Scripts\python.exe main.py --smoke-test --paused --no-save

# 核心和本地接口测试
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`--no-save` 避免退出时覆盖已有运行记录。`--port` 可指定端口，默认0自动选择可用端口；服务仅监听 `127.0.0.1`。

## 模块

```text
main.py                 独立窗口、浏览器及无界面入口
desktop.py              原生双窗口管理、显示及关闭联动
controller.py           唯一仿真拥有者线程、命令队列及JSON快照
server.py               标准库本地服务，提供HTML与状态/命令接口
config.py               参数、版本号和路径
models.py               机器人、任务和作业阶段
warehouse.py            地图、可达性及网格最短路
scheduler.py            硬优先级下的精确任务匹配
simulation.py           任务状态机、抢占、执行及恢复
planning/               时空A*、CBS及冲突验证
persistence.py          场景回放与报告
frontend/index.html     面向使用者的主页面
frontend/debug.html     调试控制与运行数据页面
frontend/styles.css     页面布局
frontend/client.js      两个页面共用的状态及命令通信
frontend/app.js         主窗口展示、统一插值和业务操作
frontend/debug.js       调试操作及数据展示
frontend/scene3d.js     Three.js场景和相机
frontend/map2d.js       Canvas二维地图
frontend/vendor/        实际使用的Three.js文件及许可
scenarios/ordinary.json 普通任务预设
tests/                  正式核心及控制器测试
outputs/                使用或验证后产生的记录与截图
```

只有controller的后台线程推进仿真和修改任务。所有页面读取同一快照，操作交给同一队列。刷新或打开第二个页面不会创建新仿真；规划期间继续提供最后状态，界面保持响应。

网页计算一份机器人插值位置，交给3D和2D共同渲染。两个预览不各自推进任务或规划路径。3D只把二维网格映射到地面，不增加物理引擎或连续控制。

## 算法范围

分配按5至1级依次最大化服务数量，再精确最小化本轮预计完成时间之和。代价包括剩余必要动作、实际网格最短路和装卸，不预测未来插单与CBS等待；保证的是本轮给定代价下的最优匹配。

5级紧急任务可抢占尚未开始装货的普通任务；原任务保留身份返回队列。装卸不可中断，载货机器人先交付；必要时预约接手，同级紧急任务不互相抢占。

CBS沿用固定任务归属、作业顺序及有限时域。所有机器人保留占用，停车终点独立，禁止同格和对向换边冲突。计算超时或时域内未找到方案不等于证明无解，仍按原规则恢复或安全暂停。

## 精简与隔离

没有带入旧Pygame `ui/`、入口、界面测试、截图、运行记录、`work/`或缓存。重新建立独立环境，只安装HTML窗口依赖。核心测试是维护代码，应保留。

前端直接使用模块化HTML/JavaScript和少量本地Three.js文件，没有 `node_modules/`、重复构建产物或额外构建框架。浏览器检查工具与下载包在项目外，不是运行依赖。

v0.1_preview保留为原2D版本。原v0.2目录改名为v0.2.1，已有场景及运行记录随目录保留；改名后已更新环境入口，当前保存路径在新目录内。验证保存/加载时备份并恢复了已有用户记录。

## 验证与边界

本次升级验证：17项核心/接口检查、20项实际浏览器断言、原生双窗口检查均通过。验证覆盖窗口职责、任务同步、单步、暂停、双向速度设置、保存加载、重置、刷新，以及关闭和重新打开调试窗口时状态保持。原生检查还验证了实际WebGL2绘制与3D/2D坐标一致。

新报告和截图：`outputs/verification_v0.2.1.json`、`outputs/preview_main_v0.2.1.png`、`outputs/preview_debug_v0.2.1.png`。旧报告和运行记录保留，不应将其历史版本号误认为当前入口。

不包含外部精细模型、复杂材质、物理引擎、真实库存、动态障碍及真实机器人接口。若WebGL不可用，3D区域显示提示，2D和任务操作仍可使用。

