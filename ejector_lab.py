from __future__ import annotations

import argparse
import html
import queue
import re
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
import serial

hv.extension("bokeh")


# =========================
# 页面主题：科研仪表盘风格
# =========================

RAW_CSS = """
:root {
  --lab-ink: #1d1d1f;
  --lab-muted: #6e6e73;
  --lab-line: rgba(60, 60, 67, 0.14);
  --lab-paper: #f5f5f7;
  --lab-card: rgba(255, 255, 255, 0.84);
  --lab-blue: #0071e3;
  --lab-green: #248a3d;
  --lab-orange: #bf5a00;
  --lab-purple: #8944ab;
  --lab-red: #d70015;
  --lab-shadow: 0 18px 45px rgba(0, 0, 0, 0.08);
  --lab-shadow-strong: 0 28px 70px rgba(0, 0, 0, 0.12);
}
.bk-root, body {
  font-family: "SF Pro Display", "SF Pro Text", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at 12% -8%, rgba(0, 113, 227, 0.13), transparent 34%),
    radial-gradient(circle at 92% 2%, rgba(175, 82, 222, 0.11), transparent 30%),
    linear-gradient(180deg, #fbfbfd 0%, #f5f5f7 48%, #f2f2f5 100%);
  color: var(--lab-ink);
}
.bk-root .sidebar {
  background: rgba(255, 255, 255, 0.78) !important;
  backdrop-filter: blur(24px) saturate(180%);
  border-right: 1px solid var(--lab-line);
}
.bk-root .main {
  max-width: 1480px;
  margin: 0 auto;
}
#header,
.app-header,
.pn-template-header {
  background: rgba(251, 251, 253, 0.86) !important;
  color: var(--lab-ink) !important;
  border-bottom: 1px solid rgba(60, 60, 67, 0.12);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(28px) saturate(180%);
}
#header a,
.app-header a,
.pn-template-header a,
#header .title,
.app-header .title,
.pn-template-header .title {
  color: var(--lab-ink) !important;
  font-weight: 760;
  letter-spacing: -0.02em;
}
.lab-hero {
  background:
    radial-gradient(circle at 14% 18%, rgba(255, 255, 255, 0.90), transparent 24%),
    radial-gradient(circle at 86% 14%, rgba(0, 113, 227, 0.18), transparent 26%),
    linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(244,248,255,0.92) 46%, rgba(245,245,247,0.92) 100%);
  color: var(--lab-ink);
  border: 1px solid rgba(255, 255, 255, 0.88);
  border-radius: 28px;
  padding: 30px 34px;
  box-shadow: var(--lab-shadow-strong);
  backdrop-filter: blur(28px) saturate(180%);
}
.lab-hero h1 {
  margin: 0 0 8px 0;
  font-size: clamp(30px, 3.2vw, 46px);
  letter-spacing: -0.03em;
  font-weight: 820;
}
.lab-hero p {
  margin: 0;
  color: var(--lab-muted);
  font-size: 15px;
  line-height: 1.65;
}
.metric-grid, .experiment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(178px, 1fr));
  gap: 14px;
}
.metric-card, .experiment-card {
  background: var(--lab-card);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 22px;
  padding: 16px 18px;
  box-shadow: var(--lab-shadow);
}
.experiment-card {
  min-height: 154px;
  transition: transform 180ms ease, box-shadow 180ms ease;
}
.experiment-card-basic {
  border-top: 4px solid rgba(0, 113, 227, 0.70);
}
.experiment-card-coupled {
  border-top: 4px solid rgba(175, 82, 222, 0.72);
  background:
    radial-gradient(circle at 90% 8%, rgba(175, 82, 222, 0.12), transparent 34%),
    var(--lab-card);
}
.experiment-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.12);
}
.experiment-card a {
  color: var(--lab-blue);
  font-weight: 700;
  text-decoration: none;
}
.experiment-card a:hover {
  text-decoration: underline;
}
.metric-name {
  color: var(--lab-muted);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.metric-value {
  color: var(--lab-ink);
  font-size: 25px;
  font-weight: 760;
  margin-top: 4px;
  letter-spacing: -0.02em;
}
.metric-unit {
  color: var(--lab-muted);
  font-size: 12px;
  margin-left: 4px;
}
.section-title {
  color: var(--lab-ink);
  font-size: 18px;
  font-weight: 760;
  margin: 10px 0 6px 0;
  letter-spacing: -0.01em;
}
.portal-section {
  margin-top: 18px;
}
.section-kicker {
  color: var(--lab-muted);
  font-size: 13px;
  margin: 0 0 12px 0;
}
.status-pill {
  display: inline-block;
  background: rgba(0, 113, 227, 0.08);
  color: var(--lab-blue);
  border: 1px solid rgba(0, 113, 227, 0.16);
  border-radius: 999px;
  padding: 4px 10px;
  margin: 2px 6px 2px 0;
  font-size: 12px;
}
.equation-box {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid var(--lab-line);
  border-radius: 18px;
  padding: 14px 16px;
  color: var(--lab-ink);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.07);
}
.apple-panel {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.76);
  border-radius: 26px;
  padding: 16px;
  box-shadow: var(--lab-shadow);
  backdrop-filter: blur(24px) saturate(180%);
}
.workflow-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.workflow-item {
  background: rgba(255,255,255,0.70);
  border: 1px solid rgba(60,60,67,0.10);
  border-radius: 20px;
  padding: 14px 16px;
}
.workflow-index {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 24px;
  height: 24px;
  margin-right: 8px;
  border-radius: 999px;
  background: var(--lab-blue);
  color: white;
  font-size: 12px;
  font-weight: 760;
}
.workflow-title {
  font-size: 14px;
  color: var(--lab-ink);
  font-weight: 760;
}
.workflow-desc {
  color: var(--lab-muted);
  font-size: 12px;
  margin-top: 7px;
  line-height: 1.55;
}
.plot-card {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 26px;
  padding: 14px;
  box-shadow: var(--lab-shadow);
  backdrop-filter: blur(24px) saturate(180%);
}
.plot-caption {
  color: var(--lab-muted);
  font-size: 12px;
  margin: 2px 0 10px 5px;
}
.tab-shell {
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(255,255,255,0.74);
  border-radius: 28px;
  padding: 14px;
  box-shadow: var(--lab-shadow);
  backdrop-filter: blur(22px) saturate(180%);
}
.bk-root .bk-btn {
  border-radius: 999px !important;
  font-weight: 680 !important;
  border: 1px solid rgba(60, 60, 67, 0.12) !important;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.06);
}
.bk-root .bk-input,
.bk-root input {
  border-radius: 12px !important;
}
.bk-root .bk-tab {
  border-radius: 999px 999px 0 0 !important;
  font-weight: 680;
}
"""
pn.extension("tabulator", raw_css=[RAW_CSS])


# =========================
# 通用配置模型
# =========================


@dataclass(frozen=True)
class PollCommand:
    label: str
    request: bytes
    response_length: int
    parser: Callable[[bytes], Mapping[str, float] | None]
    delay_after_write: float = 0.15


@dataclass(frozen=True)
class PortConfig:
    channels: tuple[str, ...]
    baudrate: int = 9600
    timeout: float = 1.0
    poll_commands: tuple[PollCommand, ...] = ()
    poll_interval: float = 0.5


@dataclass(frozen=True)
class TimePlotConfig:
    axis_id: str
    channel: str
    title: str
    color: str
    y_label: str
    y_range: tuple[float, float]


@dataclass(frozen=True)
class RelationSeriesConfig:
    x_channel: str
    y_channel: str
    label: str
    color: str
    max_points: int = 300
    marker_size: float = 5.0
    alpha: float = 0.55


@dataclass(frozen=True)
class RelationPlotConfig:
    axis_id: str
    title: str
    x_label: str
    y_label: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    series: tuple[RelationSeriesConfig, ...]
    auto_scale_x: bool = True
    auto_scale_y: bool = False


@dataclass(frozen=True)
class HistorySeriesConfig:
    y_channel: str
    label: str
    color: str
    marker_size: float = 5.0
    marker_alpha: float = 0.45
    line_width: float = 2.5


@dataclass(frozen=True)
class HistoryPlotConfig:
    axis_id: str
    x_channel: str
    x_label: str
    y_label: str
    title: str
    y_range: tuple[float, float]
    x_range: tuple[float, float] | None = None
    series: tuple[HistorySeriesConfig, ...] = ()
    variable_name: str = "x"
    max_points: int = 250
    fit_points: int = 100
    auto_scale_x: bool = True


@dataclass(frozen=True)
class MonitorConfig:
    title: str
    subtitle: str
    ports: Mapping[str, PortConfig]
    time_plots: tuple[TimePlotConfig, ...]
    relation_plots: tuple[RelationPlotConfig, ...]
    history_plot: HistoryPlotConfig
    export_dir: str
    status_label: str = "采集样本"
    discarded_label: str = "丢弃样本"
    experiment_note: str = "实时采集、变量关系、历史拟合和 CSV 导出集成在同一实验页面。"
    dashboard_columns: int = 2
    queue_size: int = 1000
    sync_timeout: float = 0.5
    max_sync_diff: float = 0.1
    max_time_points: int = 500
    time_render_points: int = 240
    time_window_seconds: float = 180.0
    history_capacity: int = 2400
    fit_degree: int = 3
    min_fit_points: int = 10
    plot_update_interval: int = 60
    slow_update_interval: float = 0.55
    max_process_per_frame: int = 120
    show_browser: bool = True
    server_port: int = 0
    derived_channel_fn: Callable[[Mapping[str, float]], Mapping[str, float]] | None = None


@dataclass(frozen=True)
class ExperimentSpec:
    key: str
    name: str
    category: str
    description: str
    config: MonitorConfig


# =========================
# Modbus 与传感器协议
# =========================


def crc16_modbus(data: bytes) -> int:
    """计算 Modbus RTU CRC16 校验值。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(body: bytes) -> bytes:
    """为请求帧追加低字节在前的 CRC。"""
    crc = crc16_modbus(body)
    return body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def has_valid_crc(response: bytes) -> bool:
    """校验响应帧 CRC，长度不足时直接判为无效。"""
    if len(response) < 5:
        return False
    received = response[-2] | (response[-1] << 8)
    return crc16_modbus(response[:-2]) == received


def build_read_request(address: int, function: int, start_register: int, register_count: int) -> bytes:
    """构造标准 Modbus RTU 读寄存器请求帧。"""
    body = bytes(
        [
            address,
            function,
            (start_register >> 8) & 0xFF,
            start_register & 0xFF,
            (register_count >> 8) & 0xFF,
            register_count & 0xFF,
        ]
    )
    return append_crc(body)


def response_registers(response: bytes) -> list[int]:
    """从已通过 CRC 的响应帧中提取 16 位寄存器。"""
    byte_count = response[2]
    data = response[3 : 3 + byte_count]
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


# 压力模块：0-5 V 对应 -100 到 300 kPa，RS485 模块返回 0-65535 ADC 计数。
PRESSURE_RANGE_KPA = (-100.0, 300.0)
PRESSURE_ADC_RANGE = (0.0, 65535.0)
PRESSURE_VOLTAGE_RANGE = (0.0, 5.0)
PRESSURE_REGISTER_INDEX = {"P1": 2, "P2": 4}


def raw_count_to_pressure_kpa(raw_count: int) -> float:
    count_min, count_max = PRESSURE_ADC_RANGE
    voltage_min, voltage_max = PRESSURE_VOLTAGE_RANGE
    pressure_min, pressure_max = PRESSURE_RANGE_KPA
    voltage_ratio = (raw_count - count_min) / (count_max - count_min)
    voltage = voltage_min + voltage_ratio * (voltage_max - voltage_min)
    pressure_ratio = (voltage - voltage_min) / (voltage_max - voltage_min)
    return pressure_min + pressure_ratio * (pressure_max - pressure_min)


def parse_pressure_response(response: bytes) -> Mapping[str, float] | None:
    if len(response) != 21 or not has_valid_crc(response):
        return None
    if response[0] != 0x01 or response[1] != 0x03 or response[2] != 16:
        return None
    registers = response_registers(response)
    return {
        channel: raw_count_to_pressure_kpa(registers[index])
        for channel, index in PRESSURE_REGISTER_INDEX.items()
    }


def build_pressure_port(baudrate: int = 9600, timeout: float = 0.5) -> PortConfig:
    return PortConfig(
        channels=tuple(PRESSURE_REGISTER_INDEX),
        baudrate=baudrate,
        timeout=timeout,
        poll_commands=(
            PollCommand(
                label="压力",
                request=build_read_request(0x01, 0x03, 0x0000, 0x0008),
                response_length=21,
                parser=parse_pressure_response,
            ),
        ),
        poll_interval=0.25,
    )


# 热敏风速传感器：说明书给出的固定查询帧，地址为 0x04。
WIND_SPEED_REQUEST = bytes.fromhex("04 03 00 00 00 02 C4 5E")
WIND_TEMP_REQUEST = bytes.fromhex("04 05 00 00 00 02 4C 5E")


def parse_wind_speed_response(response: bytes) -> Mapping[str, float] | None:
    if len(response) != 9 or not has_valid_crc(response):
        return None
    if response[0] != 0x04 or response[1] != 0x03 or response[2] != 0x04:
        return None
    raw_speed = (response[5] << 8) | response[6]
    return {"W_s": raw_speed / 10.0}


def parse_wind_temp_response(response: bytes) -> Mapping[str, float] | None:
    if len(response) != 9 or not has_valid_crc(response):
        return None
    if response[0] != 0x04 or response[1] != 0x05 or response[2] != 0x04:
        return None
    raw_temperature = (response[5] << 8) | response[6]
    return {"W_t": (raw_temperature - 400) / 10.0}


def build_wind_port(baudrate: int = 9600, timeout: float = 0.5) -> PortConfig:
    return PortConfig(
        channels=("W_s", "W_t"),
        baudrate=baudrate,
        timeout=timeout,
        poll_commands=(
            PollCommand("风速", WIND_SPEED_REQUEST, 9, parse_wind_speed_response),
            PollCommand("风温", WIND_TEMP_REQUEST, 9, parse_wind_temp_response),
        ),
        poll_interval=0.5,
    )


# K 型热电偶模块：地址 1，读 0x0003 起 3 个寄存器，T1/T2 分别在相对索引 0/2。
THERMO_REGISTER_INDEX = {"T1": 0, "T2": 2}


def register_to_celsius(register: int) -> float | None:
    if register == 0xFFFF:
        return None
    signed = register - 0x10000 if register & 0x8000 else register
    return signed / 10.0


def parse_thermocouple_response(response: bytes) -> Mapping[str, float] | None:
    if len(response) != 11 or not has_valid_crc(response):
        return None
    if response[0] != 0x01 or response[1] != 0x03 or response[2] != 6:
        return None
    registers = response_registers(response)
    values: dict[str, float] = {}
    for channel, index in THERMO_REGISTER_INDEX.items():
        temperature = register_to_celsius(registers[index])
        if temperature is None:
            return None
        values[channel] = temperature
    return values


def build_thermocouple_port(baudrate: int = 38400, timeout: float = 0.5) -> PortConfig:
    return PortConfig(
        channels=tuple(THERMO_REGISTER_INDEX),
        baudrate=baudrate,
        timeout=timeout,
        poll_commands=(
            PollCommand(
                label="K 型热电偶",
                request=build_read_request(0x01, 0x03, 0x0003, 0x0003),
                response_length=11,
                parser=parse_thermocouple_response,
                delay_after_write=0.08,
            ),
        ),
        poll_interval=0.25,
    )


# =========================
# 数据处理与采集线程
# =========================


def parse_line(line: bytes, expected_count: int) -> list[float] | None:
    """兼容被动串口 CSV 输出，当前主要使用主动 RS485 轮询。"""
    try:
        decoded = line.decode("utf-8", errors="ignore").strip()
        parts = [part.strip() for part in decoded.split(",")]
        if len(parts) != expected_count:
            return None
        return [float(part) for part in parts]
    except (TypeError, ValueError):
        return None


def format_polynomial(coefficients: Sequence[float] | None, variable_name: str) -> str:
    if coefficients is None:
        return "n/a"
    terms: list[str] = []
    degree = len(coefficients) - 1
    for index, coefficient in enumerate(coefficients):
        power = degree - index
        if abs(coefficient) < 1e-9:
            continue
        sign = "+" if coefficient > 0 else "-"
        magnitude = abs(coefficient)
        if power == 0:
            body = f"{magnitude:.4g}"
        elif power == 1:
            body = f"{magnitude:.4g}{variable_name}"
        else:
            body = f"{magnitude:.4g}{variable_name}^{power}"
        terms.append(body if not terms and sign == "+" else f"{sign} {body}")
    return " ".join(terms) if terms else "0"


def downsample_pair(x_values: np.ndarray, y_values: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    if len(x_values) != len(y_values):
        size = min(len(x_values), len(y_values))
        x_values = x_values[-size:]
        y_values = y_values[-size:]
    if max_points <= 0 or len(x_values) <= max_points:
        return x_values, y_values
    step = max(1, int(np.ceil(len(x_values) / max_points)))
    return x_values[::step], y_values[::step]


def auto_limits(values: list[np.ndarray], fallback: tuple[float, float], margin_ratio: float = 0.10) -> tuple[float, float]:
    arrays = [np.asarray(array, dtype=np.float64) for array in values if len(array) > 0]
    if not arrays:
        return fallback
    combined = np.concatenate(arrays)
    finite = combined[np.isfinite(combined)]
    if len(finite) == 0:
        return fallback
    minimum = float(np.min(finite))
    maximum = float(np.max(finite))
    if np.isclose(minimum, maximum):
        span = max(abs(minimum) * margin_ratio, (fallback[1] - fallback[0]) * margin_ratio, 1.0)
        return minimum - span, maximum + span
    margin = (maximum - minimum) * margin_ratio
    return minimum - margin, maximum + margin


def unit_from_label(label: str) -> str:
    match = re.search(r"\(([^()]*)\)\s*$", label)
    return match.group(1) if match else ""


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", text.strip())
    return cleaned.strip("_") or "experiment"


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


class SerialReaderThread(threading.Thread):
    """每个串口一个后台线程，避免页面刷新阻塞采集。"""

    def __init__(self, port_name: str, config: PortConfig, data_queue: queue.Queue[dict[str, object]]):
        super().__init__(daemon=True)
        self.port_name = port_name
        self.config = config
        self.data_queue = data_queue
        self.running = True
        self.serial_conn: serial.Serial | None = None
        self.last_data_time: float | None = None

    def run(self) -> None:
        while self.running:
            try:
                self.serial_conn = serial.Serial(
                    port=self.port_name,
                    baudrate=self.config.baudrate,
                    timeout=self.config.timeout,
                )
                print(f"已打开串口 {self.port_name} @ {self.config.baudrate}")
                self.last_data_time = time.monotonic()
                if self.config.poll_commands:
                    self._run_polling_loop()
                else:
                    self._run_line_loop()
            except Exception as exc:  # noqa: BLE001
                print(f"连接 {self.port_name} 失败: {exc}")
                self._sleep_while_running(2.0)
            finally:
                self.close_serial()

    def _run_line_loop(self) -> None:
        while self.running and self.serial_conn is not None:
            try:
                line = self.serial_conn.readline()
                if not line:
                    self._warn_if_idle()
                    continue
                parsed = parse_line(line, len(self.config.channels))
                if parsed is None:
                    print(f"忽略 {self.port_name} 异常数据: {line!r}")
                    continue
                self.last_data_time = time.monotonic()
                self._emit_values(parsed)
            except serial.SerialException:
                print(f"{self.port_name} 读取错误，准备重连")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"{self.port_name} 未预期读取错误: {exc}")
                self._sleep_while_running(0.1)

    def _run_polling_loop(self) -> None:
        while self.running and self.serial_conn is not None:
            sample: dict[str, float] = {}
            try:
                for command in self.config.poll_commands:
                    self.serial_conn.reset_input_buffer()
                    self.serial_conn.write(command.request)
                    self.serial_conn.flush()
                    time.sleep(command.delay_after_write)
                    response = self.serial_conn.read(command.response_length)
                    parsed = command.parser(response)
                    if parsed is None:
                        self._warn_if_idle()
                        if response:
                            print(f"忽略 {self.port_name} 异常{command.label}响应: {response.hex(' ')}")
                        continue
                    sample.update(parsed)
                    self.last_data_time = time.monotonic()

                if all(channel in sample for channel in self.config.channels):
                    self._emit_values([sample[channel] for channel in self.config.channels])
                self._sleep_while_running(self.config.poll_interval)
            except serial.SerialException:
                print(f"{self.port_name} 轮询错误，准备重连")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"{self.port_name} 未预期轮询错误: {exc}")
                self._sleep_while_running(0.1)

    def _emit_values(self, values: Sequence[float]) -> None:
        try:
            self.data_queue.put_nowait(
                {
                    "port": self.port_name,
                    "channels": self.config.channels,
                    "values": list(values),
                    "timestamp": time.monotonic(),
                    "wall_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except queue.Full:
            pass

    def close_serial(self) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:  # noqa: BLE001
                pass

    def stop(self) -> None:
        self.running = False
        self.close_serial()

    def _sleep_while_running(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while self.running and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def _warn_if_idle(self) -> None:
        now = time.monotonic()
        if self.last_data_time is None:
            self.last_data_time = now
            return
        if now - self.last_data_time >= 5.0:
            print(f"{self.port_name} 已 {now - self.last_data_time:.0f}s 未收到数据 @ {self.config.baudrate} baud")
            self.last_data_time = now


class SerialManager:
    def __init__(self, ports: Mapping[str, PortConfig], data_queue: queue.Queue[dict[str, object]]):
        self.ports = ports
        self.data_queue = data_queue
        self.readers: dict[str, SerialReaderThread] = {}

    def start_all(self) -> None:
        for port_name, port_config in self.ports.items():
            if port_name in self.readers and self.readers[port_name].is_alive():
                continue
            reader = SerialReaderThread(port_name, port_config, self.data_queue)
            reader.start()
            self.readers[port_name] = reader
            print(f"启动 {port_name}: {list(port_config.channels)}")

    def stop_all(self) -> None:
        for reader in self.readers.values():
            reader.stop()
        for reader in self.readers.values():
            reader.join(timeout=2.0)
        self.readers.clear()


class SyncManager:
    """多串口同步：把时间差较小的数据合并为一条实验样本。"""

    def __init__(self, expected_ports: Iterable[str], sync_timeout: float, max_sync_diff: float):
        self.expected_ports = tuple(expected_ports)
        self.sync_timeout = sync_timeout
        self.max_sync_diff = max_sync_diff
        self.buffer: dict[str, dict[str, object]] = {}

    def add_packet(self, packet: dict[str, object]) -> tuple[dict[str, float] | None, int]:
        discarded = self._drop_expired(time.monotonic())
        if len(self.expected_ports) == 1:
            return self._packet_to_values(packet), discarded

        port_name = str(packet["port"])
        if port_name in self.buffer:
            discarded += 1
        self.buffer[port_name] = packet
        if len(self.buffer) < len(self.expected_ports):
            return None, discarded

        timestamps = [float(item["timestamp"]) for item in self.buffer.values()]
        if max(timestamps) - min(timestamps) > self.max_sync_diff:
            oldest_port = min(self.buffer, key=lambda name: float(self.buffer[name]["timestamp"]))
            del self.buffer[oldest_port]
            return None, discarded + 1

        merged: dict[str, float] = {}
        for item in self.buffer.values():
            for channel, value in zip(item["channels"], item["values"]):
                merged[str(channel)] = float(value)
        self.buffer.clear()
        return merged, discarded

    def _packet_to_values(self, packet: dict[str, object]) -> dict[str, float]:
        return {str(channel): float(value) for channel, value in zip(packet["channels"], packet["values"])}

    def _drop_expired(self, now: float) -> int:
        expired_ports = [
            port_name
            for port_name, packet in self.buffer.items()
            if now - float(packet["timestamp"]) > self.sync_timeout
        ]
        for port_name in expired_ports:
            del self.buffer[port_name]
        return len(expired_ports)


class HistoryFitManager:
    """保存拟合用历史数据，不受实时窗口长度影响。"""

    def __init__(self, config: HistoryPlotConfig, capacity: int):
        self.config = config
        self.x_data: deque[float] = deque(maxlen=capacity)
        self.y_data: dict[str, deque[float]] = {
            series.y_channel: deque(maxlen=capacity) for series in config.series
        }
        self.fit_active = False
        self.fit_coefficients: dict[str, np.ndarray] = {}
        self.fit_x_range: tuple[float, float] | None = None
        self.last_fit_time: str | None = None

    def add_sample(self, sample: Mapping[str, float]) -> None:
        if self.config.x_channel not in sample:
            return
        if any(series.y_channel not in sample for series in self.config.series):
            return
        self.x_data.append(float(sample[self.config.x_channel]))
        for series in self.config.series:
            self.y_data[series.y_channel].append(float(sample[series.y_channel]))

    def reset(self) -> None:
        self.x_data.clear()
        for values in self.y_data.values():
            values.clear()
        self.clear_fit()

    def clear_fit(self) -> None:
        self.fit_active = False
        self.fit_coefficients = {}
        self.fit_x_range = None
        self.last_fit_time = None

    def calculate_fit(self, degree: int, min_fit_points: int) -> bool:
        required_points = max(min_fit_points, degree + 1)
        if len(self.x_data) < required_points:
            return False
        x_values = np.asarray(self.x_data, dtype=np.float64)
        valid_mask = np.isfinite(x_values)
        y_arrays: dict[str, np.ndarray] = {}
        for channel, values in self.y_data.items():
            array = np.asarray(values, dtype=np.float64)
            y_arrays[channel] = array
            valid_mask &= np.isfinite(array)
        x_valid = x_values[valid_mask]
        if len(x_valid) < required_points or np.unique(x_valid).size < degree + 1:
            return False
        self.fit_coefficients = {
            channel: np.polyfit(x_valid, values[valid_mask], degree)
            for channel, values in y_arrays.items()
        }
        self.fit_active = True
        self.fit_x_range = (float(np.min(x_valid)), float(np.max(x_valid)))
        self.last_fit_time = time.strftime("%H:%M:%S")
        return True

    def get_plot_data(self) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        return (
            np.asarray(self.x_data, dtype=np.float64),
            {channel: np.asarray(values, dtype=np.float64) for channel, values in self.y_data.items()},
        )

    def get_fit_curves(self, num_points: int) -> tuple[np.ndarray | None, dict[str, np.ndarray]]:
        if not self.fit_active or self.fit_x_range is None:
            return None, {}
        x_min, x_max = self.fit_x_range
        x_fit = np.linspace(x_min, x_max, num_points)
        curves = {
            channel: np.polyval(coefficients, x_fit)
            for channel, coefficients in self.fit_coefficients.items()
        }
        return x_fit, curves


# =========================
# Panel/HoloViews 实时页面
# =========================


class MonitorApp:
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.data_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=config.queue_size)
        self.serial_manager = SerialManager(config.ports, self.data_queue)
        self.sync_manager = SyncManager(config.ports.keys(), config.sync_timeout, config.max_sync_diff)
        self.history_manager = HistoryFitManager(config.history_plot, config.history_capacity)

        self.sample_count = 0
        self.discarded_count = 0
        self.paused_drop_count = 0
        self.fit_status = "未拟合"
        self.start_timestamp: float | None = None
        self.periodic_callback = None
        self.last_export_path: Path | None = None
        self.collecting = False
        self.last_status_refresh = 0.0
        self.last_plot_refresh = 0.0
        self.last_slow_refresh = 0.0
        self.last_sample_monotonic: float | None = None

        self.samples: deque[dict[str, object]] = deque(maxlen=config.history_capacity)
        self.latest_values: dict[str, float] = {}
        self.timestamps: deque[float] = deque(maxlen=config.max_time_points)
        self.channel_data = {
            channel: deque(maxlen=config.max_time_points) for channel in self._collect_channels()
        }
        self.channel_titles, self.channel_units, self.channel_colors = self._build_channel_metadata()
        self.display_channels = unique_preserve_order([plot.channel for plot in config.time_plots])

        self.start_button = pn.widgets.Button(name="开始采集", button_type="primary")
        self.stop_button = pn.widgets.Button(name="停止采集", button_type="light")
        self.pause_toggle = pn.widgets.Toggle(name="暂停记录", button_type="warning", value=False)
        self.autoscale_checkbox = pn.widgets.Checkbox(name="自动缩放坐标", value=True)
        self.time_window_slider = pn.widgets.IntSlider(
            name="实时窗口 / s",
            start=10,
            end=max(30, int(config.time_window_seconds * 4)),
            step=10,
            value=int(config.time_window_seconds),
        )
        self.fit_degree_spinner = pn.widgets.IntInput(name="多项式阶数", value=config.fit_degree, start=1, end=6)
        self.fit_button = pn.widgets.Button(name="计算拟合", button_type="primary")
        self.clear_fit_button = pn.widgets.Button(name="清除拟合", button_type="light")
        self.clear_data_button = pn.widgets.Button(name="清空本轮数据", button_type="danger")
        self.export_button = pn.widgets.Button(name="导出 CSV", button_type="success")
        self.stop_button.disabled = True
        self.pause_toggle.disabled = True

        self.summary_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.latest_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.equation_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.time_panes: dict[str, pn.pane.HoloViews] = {}
        self.relation_panes: dict[str, pn.pane.HoloViews] = {}
        self.history_pane = pn.pane.HoloViews(height=430, sizing_mode="stretch_width")
        self.data_table = pn.widgets.Tabulator(
            pd.DataFrame(),
            pagination="local",
            page_size=12,
            sizing_mode="stretch_width",
            height=360,
            disabled=True,
        )
        self._wire_callbacks()
        self._refresh_views(force=True)

    def _wire_callbacks(self) -> None:
        self.start_button.on_click(self._on_start_collection)
        self.stop_button.on_click(self._on_stop_collection)
        self.pause_toggle.param.watch(self._on_pause_toggle, "value")
        self.autoscale_checkbox.param.watch(lambda _event: self._refresh_views(force=True), "value")
        self.time_window_slider.param.watch(lambda _event: self._refresh_views(force=True), "value")
        self.fit_button.on_click(self._on_fit)
        self.clear_fit_button.on_click(self._on_clear_fit)
        self.clear_data_button.on_click(self._on_clear_data)
        self.export_button.on_click(self._on_export)

    def _collect_channels(self) -> set[str]:
        channels = {"elapsed"}
        for port_config in self.config.ports.values():
            channels.update(port_config.channels)
        for plot in self.config.time_plots:
            channels.add(plot.channel)
        for relation_plot in self.config.relation_plots:
            for series in relation_plot.series:
                channels.add(series.x_channel)
                channels.add(series.y_channel)
        channels.add(self.config.history_plot.x_channel)
        for series in self.config.history_plot.series:
            channels.add(series.y_channel)
        return channels

    def _build_channel_metadata(self) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        titles: dict[str, str] = {"elapsed": "实验时间"}
        units: dict[str, str] = {"elapsed": "s"}
        colors: dict[str, str] = {"elapsed": "#172033"}
        for plot in self.config.time_plots:
            titles[plot.channel] = plot.title
            units[plot.channel] = unit_from_label(plot.y_label)
            colors[plot.channel] = plot.color
        for series in self.config.history_plot.series:
            titles.setdefault(series.y_channel, series.label)
            colors.setdefault(series.y_channel, series.color)
        return titles, units, colors

    def start(self) -> None:
        if self.collecting:
            return
        self.collecting = True
        self.last_sample_monotonic = None
        self.sync_manager.buffer.clear()
        self.serial_manager.start_all()
        self.fit_status = "采集中"
        self._refresh_status_cards()
        self._refresh_latest_cards()

    def stop(self) -> None:
        self.collecting = False
        self.pause_toggle.value = False
        self.serial_manager.stop_all()
        self.sync_manager.buffer.clear()
        self._discard_pending_packets()
        self.fit_status = "采集已停止"
        self._refresh_status_cards()
        self._refresh_latest_cards()

    def shutdown(self) -> None:
        if self.periodic_callback is not None:
            self.periodic_callback.stop()
            self.periodic_callback = None
        self.collecting = False
        self.serial_manager.stop_all()

    def view(self):
        if self.periodic_callback is None:
            self.periodic_callback = pn.state.add_periodic_callback(
                self._periodic_update,
                period=self.config.plot_update_interval,
                start=True,
            )
        pn.state.on_session_destroyed(lambda _session_context: self.shutdown())
        return pn.template.FastListTemplate(
            title=self.config.title,
            header_background="#fbfbfd",
            header_color="#1d1d1f",
            accent_base_color="#0071e3",
            sidebar=[
                pn.Column(
                    pn.pane.Markdown("### 实验控制"),
                    self.start_button,
                    self.stop_button,
                    self.pause_toggle,
                    self.autoscale_checkbox,
                    self.time_window_slider,
                    pn.pane.Markdown("打开页面不会占用串口；点击开始采集后才连接硬件。"),
                    css_classes=["apple-panel"],
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    pn.pane.Markdown("### 数据拟合"),
                    self.fit_degree_spinner,
                    self.fit_button,
                    self.clear_fit_button,
                    css_classes=["apple-panel"],
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    pn.pane.Markdown("### 数据管理"),
                    self.export_button,
                    self.clear_data_button,
                    css_classes=["apple-panel"],
                    sizing_mode="stretch_width",
                ),
                pn.pane.HTML('<a href="/" target="_self">返回实验目录</a>'),
            ],
            main=[
                self._build_hero(),
                pn.Column(
                    self.summary_pane,
                    self.latest_pane,
                    css_classes=["apple-panel"],
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    pn.Tabs(
                        ("实时曲线", self._build_time_grid()),
                        ("关系图与拟合", self._build_relation_fit_layout()),
                        ("数据表", self._build_table_layout()),
                        dynamic=True,
                        tabs_location="above",
                        sizing_mode="stretch_width",
                    ),
                    css_classes=["tab-shell"],
                    sizing_mode="stretch_width",
                ),
            ],
        )

    def _build_hero(self) -> pn.pane.HTML:
        ports = " | ".join(
            f"{html.escape(port)} @ {config.baudrate} baud: {', '.join(config.channels)}"
            for port, config in self.config.ports.items()
        )
        return pn.pane.HTML(
            f"""
            <div class="lab-hero">
              <h1>{html.escape(self.config.title)}</h1>
              <p>{html.escape(self.config.subtitle)}</p>
              <p style="margin-top: 8px;">{html.escape(ports)}</p>
            </div>
            """,
            sizing_mode="stretch_width",
        )

    def _build_time_grid(self) -> pn.GridBox:
        cards = []
        for plot in self.config.time_plots:
            pane = pn.pane.HoloViews(self._make_time_plot(plot), height=285, sizing_mode="stretch_width")
            self.time_panes[plot.axis_id] = pane
            cards.append(
                pn.Column(
                    pn.pane.HTML(f'<div class="plot-caption">{html.escape(plot.title)}：可独立缩放、拖拽、框选和保存</div>'),
                    pane,
                    css_classes=["plot-card"],
                    sizing_mode="stretch_width",
                )
            )
        return pn.GridBox(*cards, ncols=max(1, self.config.dashboard_columns), sizing_mode="stretch_width")

    def _build_relation_fit_layout(self) -> pn.Column:
        relation_items = []
        for relation_plot in self.config.relation_plots:
            pane = pn.pane.HoloViews(self._make_relation_plot(relation_plot), height=330, sizing_mode="stretch_width")
            self.relation_panes[relation_plot.axis_id] = pane
            relation_items.append(
                pn.Column(
                    pn.pane.HTML(
                        f'<div class="plot-caption">{html.escape(relation_plot.title)}：每张图独立交互</div>'
                    ),
                    pane,
                    css_classes=["plot-card"],
                    sizing_mode="stretch_width",
                )
            )
        return pn.Column(
            pn.pane.HTML('<div class="section-title">变量关系</div>'),
            pn.GridBox(
                *relation_items,
                ncols=max(1, min(len(relation_items), self.config.dashboard_columns)),
                sizing_mode="stretch_width",
            ),
            pn.pane.HTML('<div class="section-title">历史拟合</div>'),
            pn.Column(
                pn.pane.HTML('<div class="plot-caption">历史拟合：独立缩放、拖拽、框选和保存</div>'),
                self.history_pane,
                css_classes=["plot-card"],
                sizing_mode="stretch_width",
            ),
            self.equation_pane,
            sizing_mode="stretch_width",
        )

    def _build_table_layout(self) -> pn.Column:
        return pn.Column(
            pn.pane.Markdown("最近 200 条同步样本。导出按钮会保存完整缓存数据。"),
            self.data_table,
            sizing_mode="stretch_width",
        )

    def _on_start_collection(self, _event) -> None:
        self.start()
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.pause_toggle.disabled = False
        self.start_button.button_type = "success"
        self.stop_button.button_type = "light"
        self._refresh_status_cards()

    def _on_stop_collection(self, _event) -> None:
        self.stop()
        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.pause_toggle.disabled = True
        self.start_button.button_type = "primary"
        self.stop_button.button_type = "warning"
        self._refresh_status_cards()

    def _on_pause_toggle(self, event) -> None:
        self.pause_toggle.name = "继续记录" if event.new else "暂停记录"
        self.pause_toggle.button_type = "success" if event.new else "warning"
        self._refresh_status_cards()

    def _on_fit(self, _event) -> None:
        degree = int(self.fit_degree_spinner.value)
        if self.history_manager.calculate_fit(degree, self.config.min_fit_points):
            self.fit_status = f"{degree} 阶拟合"
        else:
            self.fit_status = "拟合失败：样本不足或自变量重复"
        self._refresh_views(force=True)

    def _on_clear_fit(self, _event) -> None:
        self.history_manager.clear_fit()
        self.fit_status = "未拟合"
        self._refresh_views(force=True)

    def _on_clear_data(self, _event) -> None:
        self.samples.clear()
        self.timestamps.clear()
        for values in self.channel_data.values():
            values.clear()
        self.latest_values.clear()
        self.history_manager.reset()
        self.sample_count = 0
        self.discarded_count = 0
        self.paused_drop_count = 0
        self.fit_status = "未拟合"
        self.start_timestamp = None
        self.last_sample_monotonic = None
        self._refresh_views(force=True)

    def _on_export(self, _event) -> None:
        df = self._data_frame()
        if df.empty:
            self.fit_status = "暂无数据可导出"
            self._refresh_status_cards()
            return
        export_dir = Path(self.config.export_dir)
        if not export_dir.is_absolute():
            export_dir = Path(__file__).resolve().parent / export_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"{safe_filename(self.config.title)}_{timestamp}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        self.last_export_path = path
        self.fit_status = f"已导出 {path.name}"
        self._refresh_status_cards()

    def _periodic_update(self) -> None:
        now = time.monotonic()
        if not self.collecting:
            if now - self.last_status_refresh >= self.config.slow_update_interval:
                self._refresh_status_cards()
                self.last_status_refresh = now
            return

        if self.pause_toggle.value:
            self._drain_queue_when_paused()
            if now - self.last_status_refresh >= self.config.slow_update_interval:
                self._refresh_status_cards()
                self.last_status_refresh = now
            return

        if self._process_pending_packets():
            self._refresh_fast_views()
            self.last_plot_refresh = now
            if now - self.last_slow_refresh >= self.config.slow_update_interval:
                self._refresh_slow_views()
                self.last_slow_refresh = now
        else:
            if now - self.last_status_refresh >= self.config.slow_update_interval:
                self._refresh_status_cards()
                self.last_status_refresh = now

    def _drain_queue_when_paused(self) -> None:
        self.paused_drop_count += self._discard_pending_packets()

    def _discard_pending_packets(self) -> int:
        drained = 0
        while not self.data_queue.empty() and drained < self.config.max_process_per_frame:
            try:
                self.data_queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        return drained

    def _process_pending_packets(self) -> bool:
        processed = 0
        received_data = False
        while not self.data_queue.empty() and processed < self.config.max_process_per_frame:
            try:
                packet = self.data_queue.get_nowait()
            except queue.Empty:
                break
            values, discarded = self.sync_manager.add_packet(packet)
            self.discarded_count += discarded
            if values is not None:
                self._record_sample(values)
                received_data = True
            processed += 1
        return received_data

    def _apply_derived_channels(self, values: dict[str, float]) -> dict[str, float]:
        if self.config.derived_channel_fn is None:
            return values
        derived = self.config.derived_channel_fn(values)
        merged = dict(values)
        for key, value in derived.items():
            merged[str(key)] = float(value)
        return merged

    def _record_sample(self, values: dict[str, float]) -> None:
        now = time.monotonic()
        if self.start_timestamp is None:
            self.start_timestamp = now
        sample = self._apply_derived_channels(values)
        elapsed = now - self.start_timestamp
        sample["elapsed"] = elapsed
        self.timestamps.append(elapsed)
        for channel, history in self.channel_data.items():
            if channel in sample:
                history.append(float(sample[channel]))
        record: dict[str, object] = {"wall_time": time.strftime("%Y-%m-%d %H:%M:%S"), "elapsed": elapsed}
        record.update({key: float(value) for key, value in sample.items()})
        self.samples.append(record)
        self.latest_values = {key: float(value) for key, value in sample.items() if key != "elapsed"}
        self.last_sample_monotonic = now
        self.history_manager.add_sample(sample)
        self.sample_count += 1

    def _data_frame(self) -> pd.DataFrame:
        if not self.samples:
            return pd.DataFrame(columns=["wall_time", "elapsed", *self._export_channels()])
        return pd.DataFrame(list(self.samples))

    def _export_channels(self) -> list[str]:
        channels = []
        for port_config in self.config.ports.values():
            channels.extend(port_config.channels)
        channels.extend(channel for channel in self.display_channels if channel not in channels)
        return unique_preserve_order(channels)

    def _refresh_views(self, force: bool = False) -> None:
        self._refresh_status_cards()
        self._refresh_latest_cards()
        self._refresh_time_plots(force=force)
        self._refresh_relation_plots(force=force)
        self._refresh_history_plot()
        self._refresh_equations()
        self._refresh_table()

    def _refresh_fast_views(self) -> None:
        # 高频刷新只更新读数和实时曲线，保证页面帧率。
        self._refresh_status_cards()
        self._refresh_latest_cards()
        self._refresh_time_plots()

    def _refresh_slow_views(self) -> None:
        # 低频刷新关系图、拟合图、表格和公式区，兼顾速度与稳定性。
        self._refresh_relation_plots()
        self._refresh_history_plot()
        self._refresh_equations()
        self._refresh_table()

    def _refresh_status_cards(self) -> None:
        now = time.monotonic()
        elapsed = 0.0 if self.start_timestamp is None else max(0.0, now - self.start_timestamp)
        rate = self.sample_count / elapsed if elapsed > 0 else 0.0
        if not self.collecting:
            status = "待机"
        elif self.pause_toggle.value:
            status = "暂停记录"
        elif self.last_sample_monotonic is None:
            status = "等待数据"
        elif now - self.last_sample_monotonic > 3.0:
            status = "数据延迟"
        else:
            status = "实时采集"
        export_text = str(self.last_export_path) if self.last_export_path else "未导出"
        self.summary_pane.object = f"""
        <div class="metric-grid">
          <div class="metric-card"><div class="metric-name">状态</div><div class="metric-value">{html.escape(status)}</div></div>
          <div class="metric-card"><div class="metric-name">{html.escape(self.config.status_label)}</div><div class="metric-value">{self.sample_count}</div></div>
          <div class="metric-card"><div class="metric-name">采样速率</div><div class="metric-value">{rate:.2f}<span class="metric-unit">Hz</span></div></div>
          <div class="metric-card"><div class="metric-name">{html.escape(self.config.discarded_label)}</div><div class="metric-value">{self.discarded_count}</div></div>
          <div class="metric-card"><div class="metric-name">队列</div><div class="metric-value">{self.data_queue.qsize()}</div></div>
          <div class="metric-card"><div class="metric-name">拟合/导出</div><div class="metric-value" style="font-size: 15px;">{html.escape(self.fit_status)}</div></div>
        </div>
        <div style="margin-top: 8px;">
          <span class="status-pill">暂停丢弃: {self.paused_drop_count}</span>
          <span class="status-pill">缓存上限: {self.config.history_capacity}</span>
          <span class="status-pill">导出: {html.escape(export_text)}</span>
        </div>
        """

    def _refresh_latest_cards(self) -> None:
        if not self.latest_values:
            message = "点击“开始采集”后打开串口" if not self.collecting else "等待串口数据..."
            self.latest_pane.object = f"""
            <div class="metric-card">
              <div class="metric-name">实时读数</div>
              <div class="metric-value" style="font-size: 18px;">{html.escape(message)}</div>
            </div>
            """
            return
        cards = []
        for channel in self.display_channels:
            if channel not in self.latest_values:
                continue
            value = self.latest_values[channel]
            unit = self.channel_units.get(channel, "")
            title = self.channel_titles.get(channel, channel)
            color = self.channel_colors.get(channel, "#0f5c8c")
            cards.append(
                f"""
                <div class="metric-card" style="border-left-color: {html.escape(color)};">
                  <div class="metric-name">{html.escape(title)}</div>
                  <div class="metric-value">{value:.3f}<span class="metric-unit">{html.escape(unit)}</span></div>
                </div>
                """
            )
        self.latest_pane.object = f'<div class="metric-grid">{"".join(cards)}</div>'

    def _refresh_time_plots(self, force: bool = False) -> None:
        if not force and not self.time_panes:
            return
        for plot in self.config.time_plots:
            pane = self.time_panes.get(plot.axis_id)
            if pane is not None:
                pane.object = self._make_time_plot(plot)

    def _refresh_relation_plots(self, force: bool = False) -> None:
        if not force and not self.relation_panes:
            return
        for plot in self.config.relation_plots:
            pane = self.relation_panes.get(plot.axis_id)
            if pane is not None:
                pane.object = self._make_relation_plot(plot)

    def _refresh_history_plot(self) -> None:
        self.history_pane.object = self._make_history_plot()

    def _refresh_equations(self) -> None:
        rows = []
        history_plot = self.config.history_plot
        for series in history_plot.series:
            coefficients = self.history_manager.fit_coefficients.get(series.y_channel)
            equation = format_polynomial(coefficients, history_plot.variable_name)
            rows.append(
                f"<div><b style='color:{html.escape(series.color)}'>{html.escape(series.label)}</b>: "
                f"{html.escape(series.label)} = {html.escape(equation)}</div>"
            )
        fit_time = self.history_manager.last_fit_time or "未计算"
        self.equation_pane.object = f"""
        <div class="equation-box">
          <div><b>拟合模型</b>：多项式最小二乘，当前状态：{html.escape(self.fit_status)}，最后拟合：{html.escape(fit_time)}</div>
          {''.join(rows)}
        </div>
        """

    def _refresh_table(self) -> None:
        df = self._data_frame().tail(200).copy()
        for column in df.select_dtypes(include=[np.number]).columns:
            df[column] = df[column].round(4)
        self.data_table.value = df

    def _make_time_plot(self, plot: TimePlotConfig):
        x_values = np.asarray(self.timestamps, dtype=np.float64)
        y_values = np.asarray(self.channel_data.get(plot.channel, []), dtype=np.float64)
        x_values, y_values = downsample_pair(x_values, y_values, self.config.time_render_points)
        if len(x_values) > 0:
            window = float(self.time_window_slider.value)
            x_max = float(x_values[-1])
            x_min = max(0.0, x_max - window)
            mask = x_values >= x_min
            x_plot = x_values[mask]
            y_plot = y_values[mask]
        else:
            x_min, x_max = 0.0, max(1.0, float(self.time_window_slider.value))
            x_plot = np.asarray([], dtype=np.float64)
            y_plot = np.asarray([], dtype=np.float64)
        y_lim = auto_limits([y_plot], plot.y_range) if self.autoscale_checkbox.value else plot.y_range
        return hv.Curve(
            (x_plot, y_plot),
            kdims=[("elapsed", "实验时间 t (s)")],
            vdims=[(plot.channel, plot.y_label)],
            label=plot.title,
        ).opts(
            color=plot.color,
            line_width=2.4,
            tools=["hover", "pan", "wheel_zoom", "box_zoom", "reset", "save"],
            active_tools=["wheel_zoom"],
            shared_axes=False,
            axiswise=True,
            framewise=True,
            toolbar="above",
            title=plot.title,
            xlabel="实验时间 t (s)",
            ylabel=plot.y_label,
            xlim=(x_min, max(x_max, x_min + 1.0)),
            ylim=y_lim,
            width=520,
            height=285,
            show_grid=True,
            bgcolor="#ffffff",
            fontsize={"title": 12, "labels": 10, "ticks": 9},
        )

    def _make_relation_plot(self, plot: RelationPlotConfig):
        elements = []
        x_samples: list[np.ndarray] = []
        y_samples: list[np.ndarray] = []
        for series in plot.series:
            x_values = np.asarray(self.channel_data.get(series.x_channel, []), dtype=np.float64)[-series.max_points :]
            y_values = np.asarray(self.channel_data.get(series.y_channel, []), dtype=np.float64)[-series.max_points :]
            x_values, y_values = downsample_pair(x_values, y_values, series.max_points)
            if len(x_values) > 0:
                x_samples.append(x_values)
                y_samples.append(y_values)
            elements.append(
                hv.Scatter(
                    (x_values, y_values),
                    kdims=[(series.x_channel, plot.x_label)],
                    vdims=[(series.y_channel, plot.y_label)],
                    label=series.label,
                ).opts(
                    color=series.color,
                    size=series.marker_size,
                    alpha=series.alpha,
                    tools=["hover", "pan", "wheel_zoom", "box_zoom", "reset", "save"],
                    toolbar="above",
                    shared_axes=False,
                    axiswise=True,
                    framewise=True,
                    muted_alpha=0.12,
                )
            )
        x_lim = auto_limits(x_samples, plot.x_range) if self.autoscale_checkbox.value and plot.auto_scale_x else plot.x_range
        y_lim = auto_limits(y_samples, plot.y_range) if self.autoscale_checkbox.value and plot.auto_scale_y else plot.y_range
        return hv.Overlay(elements).opts(
            title=plot.title,
            xlabel=plot.x_label,
            ylabel=plot.y_label,
            xlim=x_lim,
            ylim=y_lim,
            width=520,
            height=330,
            show_grid=True,
            bgcolor="#ffffff",
            legend_position="right",
            toolbar="above",
            shared_axes=False,
            axiswise=True,
            framewise=True,
            fontsize={"title": 12, "labels": 10, "ticks": 9},
        )

    def _make_history_plot(self):
        history_plot = self.config.history_plot
        x_values, y_values = self.history_manager.get_plot_data()
        elements = []
        plotted_x: list[np.ndarray] = []
        for series in history_plot.series:
            y_series = y_values.get(series.y_channel, np.asarray([], dtype=np.float64))
            x_plot, y_plot = downsample_pair(x_values, y_series, history_plot.max_points)
            if len(x_plot) > 0:
                plotted_x.append(x_plot)
            elements.append(
                hv.Scatter(
                    (x_plot, y_plot),
                    kdims=[(history_plot.x_channel, history_plot.x_label)],
                    vdims=[(series.y_channel, history_plot.y_label)],
                    label=f"{series.label} 样本",
                ).opts(
                    color=series.color,
                    size=series.marker_size,
                    alpha=series.marker_alpha,
                    tools=["hover", "pan", "wheel_zoom", "box_zoom", "reset", "save"],
                    toolbar="above",
                    shared_axes=False,
                    axiswise=True,
                    framewise=True,
                    muted_alpha=0.12,
                )
            )
        fit_x, fit_curves = self.history_manager.get_fit_curves(history_plot.fit_points)
        if fit_x is not None:
            for series in history_plot.series:
                fit_y = fit_curves.get(series.y_channel)
                if fit_y is not None:
                    elements.append(
                        hv.Curve(
                            (fit_x, fit_y),
                            kdims=[(history_plot.x_channel, history_plot.x_label)],
                            vdims=[(series.y_channel, history_plot.y_label)],
                            label=f"{series.label} 拟合",
                        ).opts(
                            color=series.color,
                            line_width=series.line_width,
                            shared_axes=False,
                            axiswise=True,
                            framewise=True,
                        )
                    )
        if not elements:
            elements = [hv.Curve(([], []), kdims=[(history_plot.x_channel, history_plot.x_label)])]
        x_range = history_plot.x_range or (0.0, max(1.0, float(self.time_window_slider.value)))
        x_lim = auto_limits(plotted_x, x_range) if self.autoscale_checkbox.value and history_plot.auto_scale_x else x_range
        return hv.Overlay(elements).opts(
            title=history_plot.title,
            xlabel=history_plot.x_label,
            ylabel=history_plot.y_label,
            xlim=x_lim,
            ylim=history_plot.y_range,
            width=900,
            height=430,
            show_grid=True,
            bgcolor="#ffffff",
            legend_position="right",
            toolbar="above",
            shared_axes=False,
            axiswise=True,
            framewise=True,
            fontsize={"title": 13, "labels": 11, "ticks": 9},
        )


# =========================
# 实验配置
# =========================


def derive_average_temperature(values: Mapping[str, float]) -> Mapping[str, float]:
    """派生变量：双热电偶平均温度。"""
    return {"T_a": (values["T1"] + values["T2"]) / 2.0}


def pressure_config() -> MonitorConfig:
    pressure_range = PRESSURE_RANGE_KPA
    return MonitorConfig(
        title="平板引射器压力实时监测",
        subtitle="压力单变量实验 | COM11: P1, P2 | RS485 9600 baud",
        ports={"COM11": build_pressure_port()},
        time_plots=(
            TimePlotConfig("p1", "P1", "P1 压力", "#0071e3", "压力 (kPa)", pressure_range),
            TimePlotConfig("p2", "P2", "P2 压力", "#bf5a00", "压力 (kPa)", pressure_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel",
                "P1-P2 同步关系",
                "P1 (kPa)",
                "P2 (kPa)",
                pressure_range,
                pressure_range,
                (RelationSeriesConfig("P1", "P2", "P1/P2", "#248a3d"),),
                True,
                True,
            ),
        ),
        history_plot=HistoryPlotConfig(
            "hist",
            "elapsed",
            "实验时间 t (s)",
            "压力 (kPa)",
            "压力随时间变化拟合",
            pressure_range,
            (0, 180),
            (HistorySeriesConfig("P1", "P1", "#0071e3"), HistorySeriesConfig("P2", "P2", "#bf5a00")),
            "t",
        ),
        export_dir="exports/pressure_only",
        status_label="同步样本",
        discarded_label="丢弃样本",
        experiment_note="用于压力传感器标定、稳态判据和 P1/P2 耦合关系观察。",
    )


def wind_config() -> MonitorConfig:
    wind_range = (0.0, 50.0)
    temp_range = (0.0, 80.0)
    return MonitorConfig(
        title="热敏风速传感器实时监测",
        subtitle="风速/温度独立实验 | COM5: W_s, W_t | RS485 9600 baud",
        ports={"COM5": build_wind_port()},
        time_plots=(
            TimePlotConfig("ws", "W_s", "风速 W_s", "#248a3d", "风速 (m/s)", wind_range),
            TimePlotConfig("wt", "W_t", "风温 W_t", "#d70015", "温度 (C)", temp_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel",
                "风温-风速关系",
                "W_s (m/s)",
                "W_t (C)",
                wind_range,
                temp_range,
                (RelationSeriesConfig("W_s", "W_t", "W_t/W_s", "#af52de"),),
                True,
                True,
            ),
        ),
        history_plot=HistoryPlotConfig(
            "hist",
            "W_s",
            "风速 W_s (m/s)",
            "温度 W_t (C)",
            "风温关于风速的实验拟合",
            temp_range,
            wind_range,
            (HistorySeriesConfig("W_t", "W_t", "#af52de"),),
            "W_s",
            max_points=300,
            fit_points=100,
        ),
        export_dir="exports/wind_only",
        experiment_note="用于风速传感器响应测试、环境温漂观察和风速-温度耦合分析。",
    )


def temperature_config() -> MonitorConfig:
    temp_range = (0.0, 200.0)
    return MonitorConfig(
        title="平板引射器温度实时监测",
        subtitle="K 型热电偶温度实验 | COM7: T1, T2 | RS485 38400 baud",
        ports={"COM7": build_thermocouple_port()},
        time_plots=(
            TimePlotConfig("t1", "T1", "T1 温度", "#248a3d", "温度 (C)", temp_range),
            TimePlotConfig("t2", "T2", "T2 温度", "#d70015", "温度 (C)", temp_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel",
                "T1-T2 一致性",
                "T1 (C)",
                "T2 (C)",
                temp_range,
                temp_range,
                (RelationSeriesConfig("T1", "T2", "T1/T2", "#af52de"),),
                True,
                True,
            ),
        ),
        history_plot=HistoryPlotConfig(
            "hist",
            "elapsed",
            "实验时间 t (s)",
            "温度 (C)",
            "温度随时间变化拟合",
            temp_range,
            (0, 180),
            (HistorySeriesConfig("T1", "T1", "#248a3d"), HistorySeriesConfig("T2", "T2", "#d70015")),
            "t",
        ),
        export_dir="exports/temperature_only",
        experiment_note="用于热电偶连接检查、温度响应时间分析和双测点一致性评估。",
    )


def pressure_wind_config() -> MonitorConfig:
    pressure_range = PRESSURE_RANGE_KPA
    wind_range = (0.0, 50.0)
    temp_range = (0.0, 80.0)
    return MonitorConfig(
        title="平板引射器压力-风速耦合监测",
        subtitle="压力/风速同步实验 | COM11: P1, P2 | COM5: W_s, W_t",
        ports={"COM11": build_pressure_port(), "COM5": build_wind_port()},
        time_plots=(
            TimePlotConfig("p1", "P1", "P1 压力", "#0071e3", "压力 (kPa)", pressure_range),
            TimePlotConfig("p2", "P2", "P2 压力", "#bf5a00", "压力 (kPa)", pressure_range),
            TimePlotConfig("ws", "W_s", "风速 W_s", "#248a3d", "风速 (m/s)", wind_range),
            TimePlotConfig("wt", "W_t", "风温 W_t", "#d70015", "温度 (C)", temp_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel1",
                "P1-风速关系",
                "W_s (m/s)",
                "P1 (kPa)",
                wind_range,
                pressure_range,
                (RelationSeriesConfig("W_s", "P1", "P1", "#0071e3"),),
                True,
                False,
            ),
            RelationPlotConfig(
                "rel2",
                "P2-风速关系",
                "W_s (m/s)",
                "P2 (kPa)",
                wind_range,
                pressure_range,
                (RelationSeriesConfig("W_s", "P2", "P2", "#bf5a00"),),
                True,
                False,
            ),
        ),
        history_plot=HistoryPlotConfig(
            "hist",
            "W_s",
            "风速 W_s (m/s)",
            "压力 (kPa)",
            "压力关于风速的实验拟合",
            pressure_range,
            wind_range,
            (HistorySeriesConfig("P1", "P1", "#0071e3"), HistorySeriesConfig("P2", "P2", "#bf5a00")),
            "W_s",
            max_points=300,
            fit_points=100,
        ),
        export_dir="exports/pressure_wind",
        status_label="同步样本",
        discarded_label="丢弃样本",
        experiment_note="用于风速-压力响应曲线、稳态判据和压力标定拟合。",
    )


def pressure_temperature_config() -> MonitorConfig:
    pressure_range = PRESSURE_RANGE_KPA
    temp_range = (0.0, 200.0)
    return MonitorConfig(
        title="平板引射器压力-温度耦合监测",
        subtitle="压力/温度同步实验 | COM11: P1, P2 | COM7: T1, T2 | T_a=(T1+T2)/2",
        ports={"COM11": build_pressure_port(), "COM7": build_thermocouple_port()},
        time_plots=(
            TimePlotConfig("p1", "P1", "P1 压力", "#0071e3", "压力 (kPa)", pressure_range),
            TimePlotConfig("p2", "P2", "P2 压力", "#bf5a00", "压力 (kPa)", pressure_range),
            TimePlotConfig("t1", "T1", "T1 温度", "#248a3d", "温度 (C)", temp_range),
            TimePlotConfig("t2", "T2", "T2 温度", "#d70015", "温度 (C)", temp_range),
            TimePlotConfig("ta", "T_a", "平均温度 T_a", "#af52de", "温度 (C)", temp_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel",
                "压力-平均温度关系",
                "T_a (C)",
                "压力 (kPa)",
                temp_range,
                pressure_range,
                (
                    RelationSeriesConfig("T_a", "P1", "P1", "#0071e3"),
                    RelationSeriesConfig("T_a", "P2", "P2", "#bf5a00"),
                ),
                True,
                False,
            ),
        ),
        history_plot=HistoryPlotConfig(
            "hist",
            "T_a",
            "平均温度 T_a (C)",
            "压力 (kPa)",
            "压力关于平均温度的实验拟合",
            pressure_range,
            temp_range,
            (HistorySeriesConfig("P1", "P1", "#0071e3"), HistorySeriesConfig("P2", "P2", "#bf5a00")),
            "T_a",
        ),
        export_dir="exports/pressure_temperature",
        status_label="同步样本",
        discarded_label="丢弃样本",
        derived_channel_fn=derive_average_temperature,
        dashboard_columns=3,
        experiment_note="用于研究温度变化对压力读数和系统状态的影响，并支持多项式标定拟合。",
    )


EXPERIMENTS: tuple[ExperimentSpec, ...] = (
    ExperimentSpec("pressure", "压力单变量实验", "基础实验", "COM11 采集 P1/P2，两路压力时序与同步关系。", pressure_config()),
    ExperimentSpec("wind", "风速单变量实验", "基础实验", "COM5 采集 W_s/W_t，风速响应与环境温漂。", wind_config()),
    ExperimentSpec("temperature", "温度单变量实验", "基础实验", "COM7 采集 K 型热电偶 T1/T2，热响应与一致性。", temperature_config()),
    ExperimentSpec("pressure_wind", "压力-风速耦合实验", "耦合实验", "同步压力与风速，拟合 P=f(W_s)。", pressure_wind_config()),
    ExperimentSpec("pressure_temperature", "压力-温度耦合实验", "耦合实验", "同步压力与平均温度，拟合 P=f(T_a)。", pressure_temperature_config()),
)
CATEGORY_ORDER = ("基础实验", "耦合实验")


# =========================
# 门户页面与命令行入口
# =========================


def experiment_by_key(key: str) -> ExperimentSpec:
    for experiment in EXPERIMENTS:
        if experiment.key == key:
            return experiment
    raise KeyError(f"未知实验: {key}")


def grouped_experiments() -> dict[str, list[ExperimentSpec]]:
    grouped: dict[str, list[ExperimentSpec]] = {}
    for experiment in EXPERIMENTS:
        grouped.setdefault(experiment.category, []).append(experiment)
    return {
        category: grouped[category]
        for category in sorted(
            grouped,
            key=lambda item: CATEGORY_ORDER.index(item) if item in CATEGORY_ORDER else len(CATEGORY_ORDER),
        )
    }


def build_runtime_config(
    experiment: ExperimentSpec,
    *,
    export_root: str | None,
    show_browser: bool,
    server_port: int,
) -> MonitorConfig:
    export_dir = str(Path(export_root) / experiment.key) if export_root else experiment.config.export_dir
    return replace(experiment.config, export_dir=export_dir, show_browser=show_browser, server_port=server_port)


def make_experiment_view(experiment: ExperimentSpec, export_root: str | None, show_browser: bool, server_port: int):
    config = build_runtime_config(
        experiment,
        export_root=export_root,
        show_browser=show_browser,
        server_port=server_port,
    )
    return MonitorApp(config).view()


def make_portal_view() -> pn.template.FastListTemplate:
    cards = []
    for category, experiments in grouped_experiments().items():
        is_coupled = category == "耦合实验"
        section_class = "portal-section coupled-section" if is_coupled else "portal-section"
        cards.append(f'<section class="{section_class}">')
        cards.append(f'<div class="section-title">{html.escape(category)}</div>')
        cards.append('<div class="experiment-grid">')
        for experiment in experiments:
            card_class = "experiment-card experiment-card-coupled" if is_coupled else "experiment-card experiment-card-basic"
            port_badges = "".join(
                f'<span class="status-pill">{html.escape(port)} · {port_config.baudrate}</span>'
                for port, port_config in experiment.config.ports.items()
            )
            cards.append(
                f"""
                <div class="{card_class}">
                  <div class="metric-name">{html.escape(experiment.key)}</div>
                  <div class="metric-value" style="font-size: 20px;">{html.escape(experiment.name)}</div>
                  <div style="min-height: 28px;">{port_badges}</div>
                  <a href="/{html.escape(experiment.key)}" target="_self">进入实验页面</a>
                </div>
                """
            )
        cards.append("</div>")
        cards.append("</section>")
    return pn.template.FastListTemplate(
        title="平板引射器实验平台",
        header_background="#fbfbfd",
        header_color="#1d1d1f",
        accent_base_color="#0071e3",
        main=[
            pn.pane.HTML(
                """
                <div class="lab-hero">
                  <h1>平板引射器实验平台</h1>
                  <p>实时采集、交互图表、拟合分析与 CSV 导出。</p>
                </div>
                """,
                sizing_mode="stretch_width",
            ),
            pn.pane.HTML("".join(cards), sizing_mode="stretch_width"),
        ],
    )


def print_experiment_list() -> None:
    print("\n平板引射器实验平台 - 实验列表")
    print("=" * 60)
    for category, experiments in grouped_experiments().items():
        print(f"\n[{category}]")
        for experiment in experiments:
            print(f"  {experiment.key:<22} {experiment.name} - {experiment.description}")
    print()


def run_debug_checks() -> int:
    print("开始执行单文件全量 debug 检查...")
    for experiment in EXPERIMENTS:
        print(f"检查: {experiment.key} - {experiment.name}")
        app = MonitorApp(replace(experiment.config, show_browser=False, server_port=0))
        for time_plot in experiment.config.time_plots:
            hv.render(app._make_time_plot(time_plot), backend="bokeh")
        for relation_plot in experiment.config.relation_plots:
            hv.render(app._make_relation_plot(relation_plot), backend="bokeh")
        hv.render(app._make_history_plot(), backend="bokeh")
    print("全量 debug 检查通过：配置、采集对象、Panel 实例化、HoloViews 渲染均正常。")
    return 0


def serve_portal(show_browser: bool, server_port: int, export_root: str | None) -> None:
    routes = {"/": make_portal_view}
    for experiment in EXPERIMENTS:
        routes[f"/{experiment.key}"] = (
            lambda experiment=experiment: make_experiment_view(experiment, export_root, show_browser, server_port)
        )
    pn.serve(
        routes,
        title="平板引射器实验平台",
        show=show_browser,
        port=server_port,
    )


def run_monitor(config: MonitorConfig) -> None:
    pn.serve(
        lambda: MonitorApp(config).view(),
        title=config.title,
        show=config.show_browser,
        port=config.server_port,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="平板引射器实验平台：分类管理、实时采集、拟合和分目录导出。",
    )
    parser.add_argument(
        "-e",
        "--experiment",
        choices=[experiment.key for experiment in EXPERIMENTS],
        help="直接启动指定实验；不提供时启动分类门户页面。",
    )
    parser.add_argument("--list", action="store_true", help="列出全部实验类型后退出。")
    parser.add_argument("--check", action="store_true", help="不打开串口，执行导入和图表渲染检查。")
    parser.add_argument("--no-browser", action="store_true", help="启动服务但不自动打开浏览器。")
    parser.add_argument("--port", type=int, default=0, help="Panel 服务端口；0 表示自动分配。")
    parser.add_argument("--export-root", help="覆盖默认导出根目录；各实验仍写入不同子文件夹。")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list:
        print_experiment_list()
        return 0
    if args.check:
        return run_debug_checks()

    show_browser = not args.no_browser
    if args.experiment:
        experiment = experiment_by_key(args.experiment)
        config = build_runtime_config(
            experiment,
            export_root=args.export_root,
            show_browser=show_browser,
            server_port=args.port,
        )
        print(f"\n启动实验：{experiment.name}")
        print(f"导出目录：{config.export_dir}")
        run_monitor(config)
    else:
        print("\n启动分类门户页面。可在浏览器中选择实验类型。")
        serve_portal(show_browser=show_browser, server_port=args.port, export_root=args.export_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
