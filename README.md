# 平板引射器实验平台 README

## 1. 项目简介

`FE/ejector_lab.py` 是平板引射器实验平台的前端和采集主程序，采用 `Panel + HoloViews + Bokeh` 构建交互页面，用于压力、风速、温度以及耦合实验的数据采集、实时显示、拟合分析和 CSV 导出。

页面打开时不会立即占用串口。只有点击 `开始采集` 后，程序才会连接当前实验所需的硬件端口。

## 2. 当前版本重点

- 修复压力-风速耦合实验：风速传感器现在一次读取风速和风温两个寄存器，避免寄存器偏移造成风速读数错误。
- 优化耦合同步：压力-风速实验单独放宽同步窗口，减少多串口轮询周期不同导致的有效样本丢弃。
- 优化页面布局：改为更紧凑的实验仪表盘布局，减少冗余说明文字。
- 合并实时曲线：每个实验的采集通道统一显示在一张实时曲线总览图中，并用不同颜色和图例区分。
- 增强稳定性：图表使用固定 Bokeh 对象和 `ColumnDataSource` 动态更新数据，缩放/拖拽不会打断采集曲线演变。
- 优化 iOS 风格渲染：页面采用浅灰系统背景、半透明导航、grouped 面板、胶囊按钮和分段页签。
- 增加端口设置：每个实验页面会自动识别当前串口，并允许手动选择压力、风速、温度模块接入的端口名称。
- 自动清理后台进程：关闭最后一个实验页面或门户页面后，程序会释放串口并结束后台 Python 服务。
- 保留主要状态信息：终端日志和页面提示更短，便于实验时快速判断状态。

## 3. 文件结构

当前 FE 目录核心文件如下：

```text
FE/
- ejector_lab.py    主程序
- README.md         本文档
- .venv/            Python 虚拟环境
```

运行后可能生成：

```text
FE/exports/         CSV 导出目录
FE/__pycache__/     Python 编译缓存
```

## 4. 环境与依赖

推荐使用项目内虚拟环境运行：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

如果需要重新安装依赖，使用虚拟环境中的 `pip`：

```powershell
FE\.venv\Scripts\python.exe -m pip install panel holoviews bokeh pandas numpy pyserial
```

不要直接使用系统 Python 运行，否则可能出现 `ModuleNotFoundError` 或依赖版本不一致。

## 5. 启动方式

启动实验门户：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

启动但不自动打开浏览器：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --no-browser
```

指定服务端口：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --no-browser --port 5007
```

直接进入指定实验：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --experiment pressure
FE\.venv\Scripts\python.exe FE\ejector_lab.py --experiment wind
FE\.venv\Scripts\python.exe FE\ejector_lab.py --experiment temperature
FE\.venv\Scripts\python.exe FE\ejector_lab.py --experiment pressure_wind
FE\.venv\Scripts\python.exe FE\ejector_lab.py --experiment pressure_temperature
```

查看实验列表：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --list
```

执行渲染和配置检查：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --check
```

退出方式：

- 关闭最后一个浏览器页面后，后台服务会在短暂延迟后自动退出。
- 在终端中按 `Ctrl+C` 退出时，程序会先停止采集线程并释放串口。
- 如果使用隐藏方式启动服务，关闭所有实验页面即可结束对应后台进程。

## 6. 实验模式

| 实验 key | 实验名称 | 分类 | 数据源 | 拟合目标 |
|---|---|---|---|---|
| `pressure` | 压力单变量实验 | 基础实验 | P1, P2 | 压力随时间变化 |
| `wind` | 风速单变量实验 | 基础实验 | W_s, W_t | 风温关于风速变化 |
| `temperature` | 温度单变量实验 | 基础实验 | T1, T2 | 温度随时间变化 |
| `pressure_wind` | 压力-风速耦合实验 | 耦合实验 | P1, P2, W_s, W_t | P=f(W_s) |
| `pressure_temperature` | 压力-温度耦合实验 | 耦合实验 | P1, P2, T1, T2, T_a | P=f(T_a) |

`T_a=(T1+T2)/2`，由程序根据 T1 和 T2 自动计算。

## 7. 硬件与串口配置

| 模块 | 默认串口 | 波特率 | 协议 | 输出通道 |
|---|---:|---:|---|---|
| 压力采集模块 | COM11 | 9600 | Modbus RTU | P1, P2 |
| 热敏风速传感器 | COM5 | 9600 | Modbus RTU 查询 | W_s, W_t |
| K 型热电偶模块 | COM7 | 38400 | Modbus RTU | T1, T2 |

端口设置规则：

- 每个实验页左侧都有 `端口设置` 面板。
- 页面打开时会自动扫描当前系统串口。
- 插拔 USB-RS485 后，点击 `刷新端口` 更新端口列表。
- 默认端口仍保留为 COM11、COM5、COM7；如果当前设备端口不同，在下拉框中选择实际接入端口。
- 单端口实验如果只检测到一个串口，会自动选择该串口。
- 多模块实验允许把波特率相同的模块选择到同一物理端口；程序会合并轮询。
- 波特率不同的模块不能共用同一物理端口，程序会阻止启动并提示。

压力换算：

```text
0-5 V -> -100 到 300 kPa
ADC 0-65535 -> 0-5 V
```

风速传感器读取：

```text
地址: 0x04
功能码: 0x03
起始寄存器: 0x0000
寄存器数量: 2
返回: W_s, W_t
```

热电偶读取：

```text
地址: 0x01
功能码: 0x03
起始寄存器: 0x0003
寄存器数量: 3
返回: T1, T2
```

## 8. 采集与同步机制

每个串口由独立后台线程轮询，采集结果进入队列，再由页面定时合并刷新。

单串口实验：

- 直接将该串口返回值记为一条实验样本。

多串口耦合实验：

- 程序按时间戳把不同串口的数据合并为一条同步样本。
- 同步失败或过期的数据会计入丢弃样本。
- 压力-风速实验已单独设置更宽同步窗口：`sync_timeout=1.5`，`max_sync_diff=0.45`。

## 9. 页面功能

左侧控制区：

| 分组 | 功能 |
|---|---|
| 实验控制 | 开始采集、停止采集、暂停记录、视图跟随数据、重置当前视图、实时窗口设置 |
| 端口设置 | 自动识别串口、刷新端口列表、为当前实验选择实际接入端口 |
| 数据拟合 | 设置多项式阶数、计算拟合、清除拟合 |
| 数据管理 | 导出 CSV、清空本轮数据 |

主内容区：

| 页签 | 内容 |
|---|---|
| 实时曲线 | 一张实时曲线总览图显示当前实验全部采集通道，按颜色和图例区分 |
| 关系与拟合 | 变量关系图、历史拟合图、拟合公式 |
| 数据表 | 最近样本预览 |

图表交互能力：

- 鼠标滚轮缩放。
- 工具栏提供 X 轴单独滚轮缩放和 Y 轴单独滚轮缩放。
- 拖拽平移。
- 框选缩放，包括整体框选、X 轴框选和 Y 轴框选。
- Hover 查看数据点。
- Reset 重置当前图。
- Save 保存当前图。
- 实时曲线图例可点击隐藏或显示对应通道，便于临时聚焦某一路数据。

图表动态策略：

- 采集过程中，状态卡片和实时读数会自动刷新。
- 图表数据源会持续更新，曲线和散点随采集数据动态演变。
- 用户缩放、拖拽和平移只改变坐标视图，不影响数据采集和数据源更新。
- `视图跟随数据` 只控制坐标范围是否自动跟随最新数据。
- `重置当前视图` 只重置当前页签图表的缩放和位置，不重新采集、不清空数据。

## 10. 标准实验流程

1. 连接传感器电源和 RS485 转接器。
2. 确认 COM 口与实验模式匹配。
3. 启动程序。
4. 在门户选择实验，或使用 `--experiment` 直接进入实验。
5. 在 `端口设置` 面板确认或修改实际接入端口。
6. 点击 `开始采集`。
7. 确认状态变为 `实时采集`，并检查实时读数。
8. 点击 `清空本轮数据` 开始正式记录。
9. 调整实验工况，观察曲线和关系图随数据动态演变。
10. 需要固定局部细节时直接缩放或拖拽图表；需要回到最新范围时点击 `重置当前视图`。
11. 需要拟合时设置阶数并点击 `计算拟合`。
12. 点击 `导出 CSV` 保存数据。
13. 实验结束后点击 `停止采集`。

## 11. 数据导出

默认导出目录：

```text
FE/exports/
```

各实验默认子目录：

| 实验 key | 导出目录 |
|---|---|
| `pressure` | `FE/exports/pressure_only` |
| `wind` | `FE/exports/wind_only` |
| `temperature` | `FE/exports/temperature_only` |
| `pressure_wind` | `FE/exports/pressure_wind` |
| `pressure_temperature` | `FE/exports/pressure_temperature` |

导出文件名格式：

```text
实验标题_YYYYMMDD_HHMMSS.csv
```

CSV 编码为 `utf-8-sig`，可直接用 Excel 打开。

指定导出根目录：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --export-root D:\EjectorData
```

程序会在该根目录下按实验 key 自动创建子目录。

## 12. 调试与验证

修改代码后建议执行：

```powershell
FE\.venv\Scripts\python.exe -m py_compile FE\ejector_lab.py
FE\.venv\Scripts\python.exe FE\ejector_lab.py --check
```

`--check` 会检查：

- 实验配置是否可实例化。
- Panel 页面对象是否可创建。
- HoloViews 图表是否可渲染。
- 所有实验模式的基础图表是否可生成。

如果需要验证页面可访问：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --no-browser --port 5007
```

然后访问：

```text
http://localhost:5007/
http://localhost:5007/pressure_wind
```

推荐的稳定性验证步骤：

1. 打开 `http://localhost:5007/`。
2. 点击任意实验卡片进入实验页。
3. 确认 `实时曲线` 页签只有一张总览图，且所有采集通道按不同颜色显示。
4. 在实时曲线、关系图和拟合图中使用滚轮缩放、拖拽和平移。
5. 切换不同页签并点击 `重置当前视图`。
6. 检查浏览器控制台和终端是否无异常。

## 13. 常用参数

| 参数 | 作用 |
|---|---|
| `--list` | 列出全部实验模式 |
| `--check` | 执行配置和图表渲染检查 |
| `--no-browser` | 启动服务但不自动打开浏览器 |
| `--port 5007` | 指定 Panel 服务端口 |
| `--export-root 路径` | 指定数据导出根目录 |
| `--experiment key` | 直接启动指定实验 |

## 14. 常见问题

### 页面打开后没有数据

先确认是否已点击 `开始采集`。如果仍无数据，检查：

- 实验模式是否正确。
- 传感器是否连接到对应 COM 口。
- 页面左侧 `端口设置` 是否选择了实际接入端口。
- RS485 A/B 是否接反。
- 波特率是否匹配。
- 传感器供电是否正常。
- 串口是否被其他软件占用。

### 串口拒绝访问

常见原因：

- 串口助手正在占用该 COM 口。
- 另一个实验页面正在采集。
- 旧 Python 进程未退出。

处理方式：

1. 点击 `停止采集`。
2. 关闭串口助手或其他占用串口的软件。
3. 关闭旧浏览器页面，等待后台进程自动退出。
4. 重新插拔 USB-RS485。
5. 重新启动程序。

### 压力-风速耦合样本很少

优先检查：

- COM11 和 COM5 是否都能独立采集。
- 风速传感器返回帧是否通过 CRC 校验。
- 压力和风速是否持续刷新。
- 丢弃样本是否持续增加。

当前版本已经放宽压力-风速同步窗口。如果仍然样本很少，通常是某个串口没有稳定返回数据，或硬件轮询周期明显超过预期。

### 风速或风温读数异常

风速传感器当前按两个寄存器解析：

```text
W_s = register[0] / 10
W_t = (register[1] - 400) / 10
```

如果读数异常，先确认传感器说明书是否与上述寄存器定义一致。

### 拟合失败

常见原因：

- 有效样本数量不足。
- 自变量几乎不变化。
- 多项式阶数过高。
- 数据中存在异常值。

建议先使用 1 阶或 2 阶拟合，并增加稳定工况下的样本数量。

### 图表缩放时页面闪动

当前版本图表数据源持续更新，缩放和位置由 Bokeh 坐标范围独立控制。

如果仍出现闪动，按以下方式处理：

- 关闭 `视图跟随数据`，避免坐标范围自动回到最新数据。
- 先完成缩放或拖拽，需要恢复全局范围时再点击 `重置当前视图`。
- 避免同时打开多个同一实验页面采集。
- 如果浏览器标签页打开时间很长，刷新页面后重新进入实验。

### 缺少 panel、holoviews 或 serial

说明当前 Python 环境不对。请使用：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

如仍缺依赖，执行：

```powershell
FE\.venv\Scripts\python.exe -m pip install panel holoviews bokeh pandas numpy pyserial
```
