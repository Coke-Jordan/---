# ---
面向高热流密度电子器件的集成式微型气体压缩泵-平板引射器矩阵散热系统研究实验平台


## 目录

1. 文档说明
2. 系统概述
3. 运行环境
4. 快速启动
5. 实验模式
6. 串口与传感器配置
7. 页面功能
8. 标准实验流程
9. 图表交互与拟合
10. 数据导出与文件目录
11. 调试与维护
12. 常见问题

## 1. 文档说明

本文档适用于 `FE/ejector_lab.py` 单文件版平板引射器实验平台。平台用于压力、风速、温度及耦合实验的数据采集、实时显示、拟合分析和 CSV 导出。

程序采用 `Panel + HoloViews + Bokeh` 构建交互页面。实验页面打开后不会立即占用串口，只有点击 `开始采集` 后才会连接对应硬件。

## 2. 系统概述

平台集成以下功能：

- 分类实验入口。
- RS485 串口数据采集。
- 压力、风速、温度实时曲线。
- 变量关系图与多项式拟合。
- 实验数据表格预览。
- 按实验类型分目录导出 CSV。
- 无硬件接入时正常打开页面并保持可操作。

## 3. 运行环境

推荐使用项目内 FE 虚拟环境运行程序。

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

如果终端已经显示 `(.venv)`，也可以运行：

```powershell
python FE\ejector_lab.py
```

不要使用系统裸 Python 直接运行，否则可能出现 `ModuleNotFoundError`。

## 4. 快速启动

启动分类门户：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

启动后在浏览器中选择实验类型。门户页先显示基础实验，再显示耦合实验。

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

执行完整渲染检查：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --check
```

## 5. 实验模式

| 实验 key | 实验名称 | 分类 | 主要用途 |
|---|---|---|---|
| `pressure` | 压力单变量实验 | 基础实验 | 采集 P1、P2，观察压力变化和两路一致性。 |
| `wind` | 风速单变量实验 | 基础实验 | 采集风速 W_s 和风温 W_t，观察风速响应。 |
| `temperature` | 温度单变量实验 | 基础实验 | 采集 T1、T2，观察热电偶响应和一致性。 |
| `pressure_wind` | 压力-风速耦合实验 | 耦合实验 | 同步采集压力与风速，拟合 P=f(W_s)。 |
| `pressure_temperature` | 压力-温度耦合实验 | 耦合实验 | 同步采集压力与平均温度，拟合 P=f(T_a)。 |

其中 `T_a=(T1+T2)/2`。

## 6. 串口与传感器配置

| 模块 | 默认串口 | 波特率 | 协议 | 输出通道 | 说明 |
|---|---:|---:|---|---|---|
| 压力采集模块 | COM11 | 9600 | Modbus RTU | P1, P2 | 0-5 V 对应 -100 至 300 kPa。 |
| 热敏风速传感器 | COM5 | 9600 | RS485 查询 | W_s, W_t | W_s 为风速，W_t 为风温。 |
| K 型热电偶模块 | COM7 | 38400 | Modbus RTU | T1, T2 | 寄存器值换算为摄氏温度。 |

注意事项：

- 进入实验页面不会立即打开串口。
- 点击 `开始采集` 后，程序才会打开当前实验所需串口。
- 点击 `停止采集` 后，程序会关闭串口并释放硬件资源。
- 无传感器接入时，页面仍可正常浏览、设置和调试。

## 7. 页面功能

### 7.1 分类门户

分类门户用于选择实验模式。页面分为：

- 基础实验。
- 耦合实验。

每张实验卡片显示实验名称、实验 key 和所需串口。

### 7.2 实验页面

左侧控制区分为三组：

| 分组 | 功能 |
|---|---|
| 实验控制 | 开始采集、停止采集、暂停记录、自动缩放坐标、实时窗口设置。 |
| 数据拟合 | 设置多项式阶数、计算拟合、清除拟合。 |
| 数据管理 | 导出 CSV、清空本轮数据、返回实验目录。 |

主内容区包含：

- 实验标题和串口信息。
- 状态卡片。
- 实时读数卡片。
- 实时曲线。
- 关系图与拟合图。
- 最近样本数据表。

状态含义：

| 状态 | 含义 |
|---|---|
| 待机 | 页面已打开，但尚未开始采集。 |
| 等待数据 | 已点击开始采集，正在等待串口数据。 |
| 实时采集 | 已接收到有效数据并持续刷新。 |
| 数据延迟 | 采集中超过 3 秒未收到新样本。 |
| 暂停记录 | 串口仍在读取，但数据不写入当前实验缓存。 |

## 8. 标准实验流程

1. 连接传感器电源和 RS485 转接器。
2. 确认串口号与实验模式匹配。
3. 运行 `FE\.venv\Scripts\python.exe FE\ejector_lab.py`。
4. 在门户页选择实验。
5. 进入实验页面后检查串口信息。
6. 点击 `开始采集`。
7. 确认实时读数和曲线正常刷新。
8. 点击 `清空本轮数据`，开始正式记录。
9. 调整实验工况并观察图表。
10. 需要拟合时点击 `计算拟合`。
11. 点击 `导出 CSV` 保存数据。
12. 实验结束后点击 `停止采集`。

## 9. 图表交互与拟合

每张图独立交互，互不影响。支持：

- 鼠标滚轮缩放。
- 拖拽平移。
- 框选缩放。
- Hover 查看数据点。
- Reset 重置当前图。
- Save 保存当前图。

刷新策略：

- 实时读数和实时曲线采用高频刷新。
- 关系图、拟合图、公式区和表格采用低频刷新。

该策略用于提高帧率，减少表格和拟合图频繁重绘造成的卡顿。

拟合建议：

- 样本较少时使用 1 阶或 2 阶。
- 自变量变化范围过小时不建议高阶拟合。
- 拟合失败通常表示样本不足或自变量重复。

## 10. 数据导出与文件目录

默认导出目录位于 `FE/exports`。

| 实验 key | 导出子目录 |
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

项目目录：

```text
FE/
├─ ejector_lab.py        主程序
├─ 使用说明书.md         本说明书
├─ exports/              数据导出目录
└─ .venv/                Python 虚拟环境
```

如需指定导出根目录：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py --export-root D:\EjectorData
```

程序仍会按实验 key 自动创建子文件夹。

## 11. 调试与维护

修改程序后建议执行：

```powershell
FE\.venv\Scripts\python.exe -m py_compile FE\ejector_lab.py
FE\.venv\Scripts\python.exe FE\ejector_lab.py --check
```

常用启动参数：

| 参数 | 作用 |
|---|---|
| `--list` | 列出全部实验模式。 |
| `--check` | 执行配置和图表渲染检查，不打开串口。 |
| `--no-browser` | 启动服务但不自动打开浏览器。 |
| `--port 5007` | 指定 Panel 服务端口。 |
| `--export-root 路径` | 指定数据导出根目录。 |

## 12. 常见问题

### 12.1 页面打开后没有数据

先确认是否已点击 `开始采集`。如果仍无数据，依次检查：

- 是否选择了正确实验模式。
- 传感器是否连接到对应 COM 口。
- RS485 A/B 是否接反。
- 波特率是否正确。
- 传感器供电是否正常。
- 串口是否被其他软件占用。

### 12.2 串口拒绝访问

常见原因：

- 串口助手正在占用该 COM 口。
- 另一个实验页面正在采集。
- 上一次 Python 进程未完全退出。

处理方式：

1. 点击 `停止采集`。
2. 关闭串口助手或其他占用串口的软件。
3. 关闭旧浏览器页面和旧 Python 进程。
4. 重新插拔 USB-RS485。
5. 重新运行程序并点击 `开始采集`。

### 12.3 缺少 holoviews 或 panel

说明没有使用 FE 虚拟环境。请使用：

```powershell
FE\.venv\Scripts\python.exe FE\ejector_lab.py
```

### 12.4 拟合失败

可能原因：

- 有效样本数量不足。
- 自变量几乎不变化。
- 多项式阶数过高。
- 数据中存在异常值。

建议先降低阶数，并增加稳定工况下的有效样本数量。
