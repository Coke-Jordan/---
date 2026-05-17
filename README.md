# 平板引射器实验平台

`ejector_lab_combined.py` 是一个基于 `Panel + Bokeh + HoloViews` 的实验采集与可视化程序，用于压力、风速、温度以及耦合实验的数据采集、实时曲线显示、关系分析、多项式拟合和 CSV 导出。

页面打开时不会立即占用串口。只有点击 `开始采集` 后，程序才会连接当前实验所需硬件端口。

## 当前特性

- 门户页集中管理全部实验模式。
- 每个实验页支持开始/停止采集、暂停记录、清空本轮数据、导出 CSV。
- 实时曲线总览图把当前实验的所有采集通道合并到一张图中，用不同颜色和图例区分。
- 实时曲线保留本轮采集历史数据；绘图时自动抽样渲染，避免长时间采集导致页面过重。
- 实时曲线重置或跟随数据时，X 轴固定从 `0 s` 开始，避免坐标轴原点随数据滑动。
- 图表支持滚轮缩放、拖拽平移、框选缩放、Hover 查看数据、Reset、Save。
- 支持端口自动扫描和手动选择。
- 支持变量关系图、历史拟合图和拟合公式展示。

## 文件结构

```text
FE/
- ejector_lab_combined.py  主程序
- README.md               本文档
- exports/                CSV 导出目录，运行后生成或追加
```

## 环境依赖

建议使用项目虚拟环境或已安装依赖的 Python 运行。需要的主要包：

```powershell
python -m pip install panel holoviews bokeh pandas numpy pyserial
```

如果本机 `python` 命令不可用，请换成你的实际 Python 路径。

## 启动方式

启动实验门户：

```powershell
python FE\ejector_lab_combined.py
```

启动但不自动打开浏览器：

```powershell
python FE\ejector_lab_combined.py --no-browser
```

指定 Panel 服务端口：

```powershell
python FE\ejector_lab_combined.py --no-browser --port 5007
```

直接进入指定实验：

```powershell
python FE\ejector_lab_combined.py --experiment pressure
python FE\ejector_lab_combined.py --experiment wind
python FE\ejector_lab_combined.py --experiment temperature
python FE\ejector_lab_combined.py --experiment pressure_wind
python FE\ejector_lab_combined.py --experiment pressure_temperature
```

查看全部实验：

```powershell
python FE\ejector_lab_combined.py --list
```

执行配置和页面构建检查：

```powershell
python FE\ejector_lab_combined.py --check
```

## 实验模式

| 实验 key | 实验名称 | 默认端口 | 采集通道 | 主要用途 |
|---|---|---|---|---|
| `pressure` | 压力单变量实验 | COM11 | P1, P2 | 两路压力时序与 P1-P2 同步关系 |
| `wind` | 风速单变量实验 | COM5 | W_s, W_t | 风速与温度通道观测 |
| `temperature` | 温度单变量实验 | COM7 | T1, T2 | K 型热电偶温度响应 |
| `pressure_wind` | 压力-风速耦合实验 | COM11, COM5 | P1, P2, W_s, W_t | 压力关于风速的关系和拟合 |
| `pressure_temperature` | 压力-温度耦合实验 | COM11, COM7 | P1, P2, T1, T2, T_a | 压力关于平均温度的关系和拟合 |

`T_a = (T1 + T2) / 2`，由程序自动计算。

## 硬件与数据解析

### 压力模块

- 默认端口：`COM11`
- 波特率：`9600`
- 协议：Modbus RTU
- 读取：地址 `0x01`，功能码 `0x03`，起始寄存器 `0x0000`，数量 `8`
- 通道：`P1`, `P2`
- 换算：

```text
ADC 0-65535 -> 0-5 V -> -100 到 300 kPa
```

### 热敏风速传感器

- 默认端口：`COM5`
- 波特率：`9600`
- 协议：RS485
- 设备地址：`0x04`
- 连续测量间隔：默认 `100 ms`，与原装 WindTEST 上位机一致
- 风速读取：功能码 `0x03`
- 温度读取：功能码 `0x05`，这是设备厂家自定义温度读数帧，不按标准 Modbus 写线圈语义处理
- 请求与换算：

```text
风速请求：04 03 00 00 00 02 C4 5E
风速返回：04 03 04 00 00 00 raw CRC_LO CRC_HI
W_s = raw / 10.0

温度请求：04 05 00 00 00 02 4C 5E
温度返回：04 05 04 00 00 raw_hi raw_lo CRC_LO CRC_HI
raw_temp = raw_hi * 256 + raw_lo
W_t = (raw_temp - 400) / 10.0
W_t 限幅到 0-80 C
```

示例：风速 `raw = 0x09` 表示 `0.9 m/s`；温度 `raw_hi raw_lo = 02 EE`，即 `750`，表示 `(750 - 400) / 10 = 35.0 C`。

注意：风速和温度分别来自不同请求帧。程序会先校验地址、功能码、数据长度和 CRC，再按上述字节位置换算，不要把 `0x03` 风速响应里的数据直接当温度。

### K 型热电偶模块

- 默认端口：`COM7`
- 波特率：`38400`
- 协议：Modbus RTU
- 读取：地址 `0x01`，功能码 `0x03`，起始寄存器 `0x0003`，数量 `3`
- 通道：`T1`, `T2`
- 换算：有符号寄存器值 / 10

## 采样速率上限

程序使用主动 RS485 轮询。热敏风速传感器按原装 `WindTEST` 上位机方式工作：默认 `时间间隔 / ms = 100`，每轮依次发送风速请求和温度请求，然后更新实时读数与曲线。页面显示的 `当前理论上限` 按串口帧 `8N1` 和当前间隔估算，即每字节约 `10 bit`。实际采样速率还会受设备响应延迟、USB-RS485 转接器、操作系统调度和多串口同步影响，通常略低于理论值。

当前默认配置的典型上限：

| 模块 | 默认波特率 | 每样本传输量 | 当前默认理论上限 |
|---|---:|---:|---:|
| 热敏风速传感器，风速+温度两条请求，间隔 100 ms | 9600 | 34 字节 | 约 10 Hz |
| 热敏风速传感器，风速+温度两条请求，间隔 0 ms | 9600 | 34 字节 | 约 28 Hz |
| 热敏风速传感器，仅风速单条请求，间隔 0 ms | 9600 | 17 字节 | 约 56 Hz |
| 压力模块 | 9600 | 29 字节 | 约 33 Hz |
| K 型热电偶模块 | 38400 | 19 字节 | 约 202 Hz |

因此，在厂家说明书给定的热敏风速传感器 `9600` 波特率、请求-响应协议下，软件无法采到 `800 Hz`。要达到 `800 Hz`，需要更高波特率并且设备支持，或改为单片机本地高速采样后通过 USB/高速串口连续输出，或改用模拟量传感器配高速 ADC。

## 页面使用流程

1. 连接传感器、电源和 RS485 转接器。
2. 启动程序，进入门户页。
3. 选择实验模式。
4. 在左侧 `端口设置` 中确认或修改实际 COM 口。
5. 风速实验按需要设置 `时间间隔 / ms`，默认值 `100` 与原装 WindTEST 连续测量一致。
6. 点击 `开始采集`。
7. 检查状态卡片和实时读数是否合理。
8. 点击 `清空本轮数据` 开始正式记录。
9. 调整实验工况，观察实时曲线和关系图。
10. 需要拟合时设置多项式阶数，点击 `计算拟合`。
11. 点击 `导出 CSV` 保存数据。
12. 实验结束后点击 `停止采集`。

## 图表说明

### 实时曲线

- 当前实验的全部通道绘制在一张 `实时曲线总览` 中。
- 曲线颜色与图例对应。
- 图例可点击隐藏或显示某一路通道。
- X 轴表示实验时间 `t (s)`，自动/重置时固定从 `0` 开始。
- Y 轴使用实验配置范围，避免坐标原点或量程随数据跳动。
- 历史数据保留在内存中，长时间采集时仅对显示数据做抽样。

### 关系与拟合

- 变量关系图显示指定变量之间的散点关系。
- 历史拟合图用于展示多项式拟合结果。
- 拟合阶数可在左侧 `数据拟合` 中设置。

### 数据表

- 显示最近样本预览。
- 导出 CSV 会保存本轮记录数据。

## 数据导出

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

指定导出根目录：

```powershell
python FE\ejector_lab_combined.py --export-root D:\EjectorData
```

程序会在该根目录下按实验 key 创建子目录。

## 常用参数

| 参数 | 作用 |
|---|---|
| `--list` | 列出全部实验模式 |
| `--check` | 执行配置和页面构建检查 |
| `--no-browser` | 启动服务但不自动打开浏览器 |
| `--port 5007` | 指定 Panel 服务端口 |
| `--export-root 路径` | 指定数据导出根目录 |
| `--experiment key` | 直接启动指定实验 |

## 调试建议

修改代码后建议执行：

```powershell
python -m py_compile FE\ejector_lab_combined.py
python FE\ejector_lab_combined.py --check
```

如果提示缺少 `panel`、`holoviews`、`bokeh` 或 `serial`，说明当前 Python 环境不对，需切换到正确虚拟环境或安装依赖。

## 常见问题

### 页面打开后没有数据

- 确认已点击 `开始采集`。
- 检查实验模式是否匹配传感器。
- 检查左侧端口是否选对。
- 检查 RS485 A/B 是否接反。
- 检查传感器供电是否正常。
- 检查串口是否被其他软件占用。

### 风速温度显示不合理

- 确认正在运行的是最新的 `FE\ejector_lab_combined.py`。
- 修改代码后需要重启程序，旧页面不会自动加载新代码。
- 重新采集前建议点击 `清空本轮数据`。
- 当前温度必须来自 `0x05` 温度请求帧，不应来自 `0x03` 风速响应帧。

### 坐标轴看起来移动了

- 点击左侧 `重置当前视图`。
- 实时曲线自动/重置范围固定从 `0 s` 开始。
- 手动拖拽图表只改变当前浏览器视图，不改变采集数据。

### 串口拒绝访问

- 关闭串口助手或其他占用串口的软件。
- 确认没有另一个实验页面正在采集。
- 点击 `停止采集` 后再重新开始。
- 必要时重新插拔 USB-RS485。
