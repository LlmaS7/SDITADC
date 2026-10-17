# AWCS · AW 协同路径标志

2026-10-16采用用户在新对话中附上的最终版本：AW共用斜笔画、三个方形起点、琥珀色协同路径、右上独立端块，以及AWCS和完整中英文名称。项目名为 **Agent-Assisted Warehouse Coordination System / 智能仓储协同调度系统**。

同日用户从四版UI预览中选定 **A · 无底嵌入**，已应用到主窗口和AI欢迎区：银灰主体 `#aeb7be`、琥珀路径 `#e6b568`，路径加深色 `#1c2024` 细分隔线，移除白色底板。

## 原稿与制作

原始附件原样保存在 `.temp/awcs-aw-studies/05-selected-awcs.png`，SHA-256为 `da4d18d961f3f542403ad63c4657cfeb049215efd0a2c016744345233d3f2ff6`。该附件与历史 `04-coordinated-routes-refined-v2.png` 的哈希不同，以本次附件为准。

SVG根据附件的实际像素轮廓描摹，图形、AWCS字标及中英文名称全部转为路径；保留原稿的结构和切口。白底宣传组合使用石墨色 `#24292e` 和主题琥珀色 `#e6b568`；软件使用上述A版银灰配色，移除位图底纹。没有重新生成另一版Logo，也不需要本机字体或外部资源。

## 运行素材

| 文件 | 用途 |
| --- | --- |
| `logo-mark.svg` / `logo-mark.png` | A版透明底银灰AW图形，主窗口与AI欢迎区共用SVG |
| `logo-icon.svg` / `logo-icon.png` | 暗底方形图标，主窗口与调试页的浏览器图标共用 |
| `app-icon.svg` / `app-icon.png` / `app-icon.ico` | 原生窗口与任务栏图标，透明底，仅AW图形，不包含AWCS或中文文字 |
| `logo.svg` / `logo.png` | 白底横向组合，图形在左，字标与完整中英文名在右 |
| `logo-stacked.svg` / `logo-stacked.png` | 白底纵向组合，沿用原稿图形与名称的相对位置 |

PNG由对应SVG在Edge中导出。SVG使用纯路径，缩放不依赖原始附件；正式程序只读取本目录，不读取 `.temp`。

## 软件排版

主窗口采用112×46px透明标识区，无底板、边框或阴影；AW图形按比例显示为108×37px，名称置于右侧，与图形区相隔15px。AI欢迎区共用同一图形和尺寸。银灰主体适配暗色表面，琥珀路径以深色细线分隔，沿用用户选定A预览的几何和配色。

白底横向/纵向组合是宣传素材，不用于软件顶栏；本次无需改变它们。A版来源归档于 `.temp/awcs-aw-studies/header-ui-options/mark-a.svg`，运行副本位于本目录，不依赖 `.temp`。

紧凑窗口沿用现有布局；调试窗口保留D标记以区分用途，浏览器图标统一更新。16px图标以整体轮廓为主，路线和字标的精细阅读建议32px以上。不要拉伸图形或将路径当作真实机器人状态。

## 原生窗口与任务栏

2026-10-17按用户要求更换原生图标。`app-icon.ico`包含16、20、24、32、40、48、64、128、256px共9个32位透明PNG帧；原始AW宽高比保持不变，居中放在方形透明画布上。小尺寸以整体轮廓为主，图标内不添加中文、AWCS字标或其他文字。

`main.py`在启动原生WebView2循环时传入本目录ICO，当前固定版本pywebview 6.2.1的WinForms实现会为主窗口、新建和重开的调试窗口设置同一图标。`desktop.py`在创建窗口前设置进程AppUserModelID `AWCS.WarehouseCoordination.Preview`，将任务栏分组与Python运行器区分。参见 [Microsoft AppUserModelID说明](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-setcurrentprocessexplicitappusermodelid)。不修改Python可执行文件或用户固定的任务栏快捷方式。

22项原生检查通过，核对ICO帧、Windows大小图标句柄、实际图标像素、任务栏参与属性、进程标识及调试窗口重开，见 `outputs/verification_native_icon.json`。验证使用隐藏的实际WinForms/WebView2窗口，不读取真实密钥或保存运行记录；没有截取Explorer的可见任务栏按钮。关闭旧窗口并重新启动程序后生效。
