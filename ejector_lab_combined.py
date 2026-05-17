from __future__ import annotations

import argparse
import atexit
import html
import os
import queue
import re
import signal
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
from bokeh.models import ColumnDataSource, HoverTool, Range1d, WheelZoomTool
from bokeh.plotting import figure
from serial.tools import list_ports

hv.extension("bokeh")



SESSION_EXIT_DELAY_SECONDS = 3.0
_LIFECYCLE_LOCK = threading.RLock()
_ACTIVE_SESSIONS = 0
_ACTIVE_APPS: set[object] = set()
_EXIT_TIMER: threading.Timer | None = None
_CLEANING_UP = False


def register_app_instance(app: object) -> None:
    with _LIFECYCLE_LOCK:
        _ACTIVE_APPS.add(app)


def unregister_app_instance(app: object) -> None:
    with _LIFECYCLE_LOCK:
        _ACTIVE_APPS.discard(app)


def cleanup_runtime() -> None:
    global _CLEANING_UP
    with _LIFECYCLE_LOCK:
        if _CLEANING_UP:
            return
        _CLEANING_UP = True
        apps = list(_ACTIVE_APPS)
    for app in apps:
        shutdown = getattr(app, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:  # noqa: BLE001
                pass


def _exit_process_if_idle() -> None:
    with _LIFECYCLE_LOCK:
        should_exit = _ACTIVE_SESSIONS <= 0
    if not should_exit:
        return
    cleanup_runtime()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(0)


def schedule_process_exit_if_idle() -> None:
    global _EXIT_TIMER
    with _LIFECYCLE_LOCK:
        if _ACTIVE_SESSIONS > 0:
            return
        if _EXIT_TIMER is not None:
            _EXIT_TIMER.cancel()
        _EXIT_TIMER = threading.Timer(SESSION_EXIT_DELAY_SECONDS, _exit_process_if_idle)
        _EXIT_TIMER.daemon = True
        _EXIT_TIMER.start()


def register_page_session(app: object | None = None) -> None:
    global _ACTIVE_SESSIONS, _EXIT_TIMER
    with _LIFECYCLE_LOCK:
        _ACTIVE_SESSIONS += 1
        if _EXIT_TIMER is not None:
            _EXIT_TIMER.cancel()
            _EXIT_TIMER = None

    closed = False

    def _on_destroyed(_session_context) -> None:
        nonlocal closed
        global _ACTIVE_SESSIONS
        if closed:
            return
        closed = True
        if app is not None:
            shutdown = getattr(app, "shutdown", None)
            if callable(shutdown):
                shutdown()
        with _LIFECYCLE_LOCK:
            _ACTIVE_SESSIONS = max(0, _ACTIVE_SESSIONS - 1)
        schedule_process_exit_if_idle()

    pn.state.on_session_destroyed(_on_destroyed)


def _handle_exit_signal(_signum, _frame) -> None:
    cleanup_runtime()
    raise SystemExit(0)


atexit.register(cleanup_runtime)
for _signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
    _signal_value = getattr(signal, _signal_name, None)
    if _signal_value is not None:
        try:
            signal.signal(_signal_value, _handle_exit_signal)
        except (OSError, ValueError):
            pass




RAW_CSS = """
:root {
  --ios-bg: #f2f2f7;
  --ios-card: rgba(255, 255, 255, 0.96);
  --ios-card-solid: #ffffff;
  --ios-elevated: rgba(255, 255, 255, 0.82);
  --ios-label: #1c1c1e;
  --ios-secondary: #636366;
  --ios-tertiary: #8e8e93;
  --ios-separator: rgba(60, 60, 67, 0.16);
  --ios-fill: rgba(120, 120, 128, 0.12);
  --ios-blue: #007aff;
  --ios-green: #34c759;
  --ios-orange: #ff9500;
  --ios-purple: #af52de;
  --ios-red: #ff3b30;
  --ios-shadow: 0 12px 30px rgba(60, 60, 67, 0.10);
  --ios-shadow-soft: 0 6px 18px rgba(60, 60, 67, 0.08);
  --lab-ink: var(--ios-label);
  --lab-muted: var(--ios-secondary);
  --lab-line: var(--ios-separator);
  --lab-paper: var(--ios-bg);
  --lab-card: var(--ios-card);
  --lab-blue: var(--ios-blue);
  --lab-green: var(--ios-green);
  --lab-orange: var(--ios-orange);
  --lab-purple: var(--ios-purple);
  --lab-red: var(--ios-red);
  --lab-shadow: var(--ios-shadow-soft);
  --lab-shadow-strong: var(--ios-shadow);
}
html,
body {
  background: var(--ios-bg);
  min-height: 100%;
}
.bk-root, body {
  font-family: "SF Pro Display", "SF Pro Text", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
  background: var(--ios-bg);
  color: var(--lab-ink);
}
.bk-root * {
  box-sizing: border-box;
}
.bk-root .sidebar {
  backdrop-filter: saturate(180%) blur(22px);
  -webkit-backdrop-filter: saturate(180%) blur(22px);
  background: rgba(242, 242, 247, 0.88) !important;
  border-right: 1px solid var(--ios-separator);
  padding: 18px 14px !important;
}
.bk-root .main {
  max-width: 1480px;
  margin: 0 auto;
  padding: 18px 22px 36px !important;
}
#header,
.app-header,
.pn-template-header {
  backdrop-filter: saturate(180%) blur(22px);
  -webkit-backdrop-filter: saturate(180%) blur(22px);
  background: rgba(248, 248, 248, 0.82) !important;
  color: var(--lab-ink) !important;
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.22);
  box-shadow: none;
}
#header a,
.app-header a,
.pn-template-header a,
#header .title,
.app-header .title,
.pn-template-header .title {
  color: var(--lab-ink) !important;
  font-weight: 700;
  letter-spacing: 0;
}
.lab-hero {
  background: var(--ios-card);
  color: var(--lab-ink);
  border: 0.5px solid var(--ios-separator);
  border-radius: 20px;
  padding: 24px 26px 22px;
  box-shadow: var(--lab-shadow-strong);
}
.lab-hero h1 {
  margin: 0 0 8px 0;
  font-size: 34px;
  font-weight: 760;
  letter-spacing: 0;
}
.lab-hero p {
  margin: 0;
  color: var(--lab-muted);
  font-size: 15px;
  line-height: 1.55;
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.metric-grid, .experiment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(178px, 1fr));
  gap: 12px;
}
.metric-card, .experiment-card {
  background: var(--ios-card-solid);
  border: 0.5px solid var(--ios-separator);
  border-left: 3px solid transparent;
  border-radius: 18px;
  padding: 15px 16px;
  box-shadow: var(--lab-shadow);
}
.experiment-card {
  min-height: 142px;
  position: relative;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
  cursor: pointer;
}
.experiment-card::after {
  content: "›";
  color: var(--ios-tertiary);
  font-size: 30px;
  font-weight: 300;
  line-height: 1;
  position: absolute;
  right: 16px;
  top: 18px;
}
.experiment-card-basic {
  border-left-color: var(--ios-blue);
}
.experiment-card-coupled {
  border-left-color: var(--ios-purple);
  background: var(--ios-card-solid);
}
.experiment-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(60, 60, 67, 0.14);
}
.experiment-card-link {
  color: inherit;
  display: block;
  text-decoration: none;
}
.experiment-card-link:focus .experiment-card,
.experiment-card-link:hover .experiment-card {
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(60, 60, 67, 0.14);
}
.experiment-card-action {
  color: var(--ios-blue);
  display: inline-block;
  font-weight: 700;
  margin-top: 10px;
  text-decoration: none;
}
.metric-name {
  color: var(--lab-muted);
  font-size: 12px;
  font-weight: 640;
  letter-spacing: 0;
}
.metric-value {
  color: var(--lab-ink);
  font-size: 24px;
  font-weight: 720;
  margin-top: 4px;
  overflow-wrap: anywhere;
}
.metric-unit {
  color: var(--lab-muted);
  font-size: 12px;
  margin-left: 4px;
}
.section-title {
  color: var(--lab-ink);
  font-size: 20px;
  font-weight: 730;
  letter-spacing: 0;
  margin: 12px 2px 10px;
}
.portal-section {
  margin-top: 22px;
}
.section-kicker {
  color: var(--lab-muted);
  font-size: 13px;
  margin: 0 0 12px 0;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  background: rgba(0, 122, 255, 0.10);
  color: var(--ios-blue);
  border: 0.5px solid rgba(0, 122, 255, 0.20);
  border-radius: 999px;
  padding: 5px 10px;
  margin: 2px 6px 2px 0;
  font-size: 12px;
  font-weight: 650;
}
.port-map {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}
.port-line {
  background: rgba(120, 120, 128, 0.10);
  border-radius: 12px;
  color: var(--ios-secondary);
  font-size: 12px;
  line-height: 1.45;
  padding: 8px 10px;
}
.port-line strong {
  color: var(--ios-label);
  font-weight: 720;
}
.port-warning {
  color: var(--ios-orange);
  font-weight: 700;
}
.equation-box {
  background: var(--ios-card-solid);
  border: 0.5px solid var(--lab-line);
  border-radius: 18px;
  padding: 16px 18px;
  color: var(--lab-ink);
  box-shadow: var(--lab-shadow);
}
.apple-panel {
  background: var(--ios-card);
  border: 0.5px solid var(--ios-separator);
  border-radius: 20px;
  padding: 16px;
  box-shadow: var(--lab-shadow);
}
.metric-section {
  background: transparent;
  border: 0;
  box-shadow: none;
  padding: 0;
}
.apple-panel h3 {
  color: var(--ios-secondary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 10px;
}
.workflow-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.workflow-item {
  background: var(--ios-card-solid);
  border: 0.5px solid rgba(60,60,67,0.12);
  border-radius: 18px;
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
  background: var(--ios-blue);
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
  background: var(--ios-card-solid);
  border: 0.5px solid rgba(60, 60, 67, 0.14);
  border-radius: 20px;
  padding: 12px 14px 16px;
  box-shadow: var(--lab-shadow);
  overflow: hidden;
}
.plot-card-time {
  min-height: 420px;
}
.plot-card-relation {
  min-height: 400px;
}
.plot-card-history {
  min-height: 500px;
}
.plot-card-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 12px 2px;
}
.plot-title {
  color: var(--lab-ink);
  font-size: 14px;
  font-weight: 720;
}
.tab-shell {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
}
.bk-root .bk-btn {
  border: 0.5px solid transparent !important;
  border-radius: 13px !important;
  box-shadow: none !important;
  font-weight: 700 !important;
  min-height: 36px !important;
  transition: opacity 160ms ease, transform 160ms ease, background 160ms ease;
}
.bk-root .bk-btn:hover {
  opacity: 0.88;
  transform: translateY(-1px);
}
.bk-root .bk-btn:disabled {
  opacity: 0.45 !important;
  transform: none;
}
.bk-root .bk-btn-primary {
  background: var(--ios-blue) !important;
  border-color: var(--ios-blue) !important;
  color: #ffffff !important;
}
.bk-root .bk-btn-success {
  background: var(--ios-green) !important;
  border-color: var(--ios-green) !important;
  color: #ffffff !important;
}
.bk-root .bk-btn-warning {
  background: var(--ios-orange) !important;
  border-color: var(--ios-orange) !important;
  color: #ffffff !important;
}
.bk-root .bk-btn-danger {
  background: var(--ios-red) !important;
  border-color: var(--ios-red) !important;
  color: #ffffff !important;
}
.bk-root .bk-btn-light,
.bk-root .bk-btn-default {
  background: var(--ios-fill) !important;
  border-color: transparent !important;
  color: var(--ios-blue) !important;
}
.bk-root .bk-input,
.bk-root input,
.bk-root select {
  background: var(--ios-card-solid) !important;
  border: 0.5px solid var(--ios-separator) !important;
  border-radius: 12px !important;
  color: var(--ios-label) !important;
  min-height: 34px !important;
}
.bk-root .bk-slider-title,
.bk-root label {
  color: var(--ios-secondary) !important;
  font-size: 13px !important;
  font-weight: 650 !important;
}
.bk-root .bk-tabs-header {
  background: var(--ios-fill) !important;
  border: 0 !important;
  border-radius: 14px !important;
  gap: 3px;
  margin-bottom: 14px;
  padding: 3px !important;
}
.bk-root .bk-tab {
  background: transparent !important;
  border: 0 !important;
  border-radius: 11px !important;
  color: var(--ios-secondary) !important;
  font-weight: 700;
  letter-spacing: 0;
  min-height: 34px;
  padding: 8px 14px !important;
}
.bk-root .bk-tab.bk-active,
.bk-root .bk-tab[aria-selected="true"] {
  background: var(--ios-card-solid) !important;
  box-shadow: 0 2px 8px rgba(60, 60, 67, 0.16);
  color: var(--ios-label) !important;
}
.bk-root .bk-toolbar {
  background: rgba(255, 255, 255, 0.78) !important;
  border: 0.5px solid var(--ios-separator) !important;
  border-radius: 12px !important;
  padding: 3px !important;
}
.bk-root .bk-toolbar-button {
  border-radius: 9px !important;
}
.bk-root .bk-DataTable,
.bk-root .tabulator {
  border: 0.5px solid var(--ios-separator) !important;
  border-radius: 16px !important;
  overflow: hidden;
}
.bk-root .tabulator .tabulator-header {
  background: #f9f9fb !important;
  border-bottom: 0.5px solid var(--ios-separator) !important;
}
.bk-root .tabulator-row {
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.10) !important;
}
.nav-link-button {
  align-items: center;
  background: var(--ios-fill);
  border: 0.5px solid transparent;
  border-radius: 13px;
  color: var(--ios-blue) !important;
  display: flex;
  font-size: 14px;
  font-weight: 720;
  justify-content: center;
  min-height: 38px;
  text-decoration: none !important;
  width: 100%;
}
.nav-link-button::before {
  content: "‹";
  font-size: 22px;
  font-weight: 400;
  line-height: 1;
  margin-right: 4px;
}
.nav-link-button:hover {
  background: rgba(0, 122, 255, 0.16);
}
@media (max-width: 760px) {
  .bk-root .main {
    padding: 12px 12px 24px !important;
  }
  .lab-hero {
    border-radius: 18px;
    padding: 20px;
  }
  .lab-hero h1 {
    font-size: 28px;
  }
  .metric-grid,
  .experiment-grid {
    grid-template-columns: 1fr;
  }
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
    delay_after_write: float = 0.0


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
    max_time_points: int = 0
    time_render_points: int = 1200
    time_window_seconds: float = 180.0
    history_capacity: int = 2400
    fit_degree: int = 3
    min_fit_points: int = 10
    plot_update_interval: int = 120
    status_update_interval: float = 0.35
    plot_redraw_interval: float = 1.2
    slow_update_interval: float = 0.8
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
FASTEST_POLL_INTERVAL_SECONDS = 0.0
SERIAL_FRAME_BITS_PER_BYTE = 10.0


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
        poll_interval=FASTEST_POLL_INTERVAL_SECONDS,
    )


# 热敏风速传感器：按冠拓电子 485 输出说明书读取。
# 注意 0x05 在该设备上是厂家自定义温度读数帧，不按标准 Modbus 写线圈语义处理。
WIND_SENSOR_ADDRESS = 0x04
WIND_REGISTER_START = 0x0000
WIND_REGISTER_COUNT = 0x0002
WIND_RESPONSE_LENGTH = 9
WIND_READ_DELAY_SECONDS = 0.0
WINDTEST_DEFAULT_INTERVAL_SECONDS = 0.1
WIND_POLL_INTERVAL_SECONDS = WINDTEST_DEFAULT_INTERVAL_SECONDS
WIND_SPEED_SCALE = 10.0
WIND_TEMPERATURE_OFFSET = 400.0
WIND_TEMPERATURE_SCALE = 10.0
WIND_SPEED_RAW_BYTE_INDEX = 6
WIND_TEMPERATURE_RAW_HIGH_BYTE_INDEX = 5
WIND_TEMPERATURE_RAW_LOW_BYTE_INDEX = 6
WIND_SPEED_RANGE_MPS = (0.0, 15.0)
WIND_TEMPERATURE_RANGE_C = (0.0, 80.0)
WIND_SPEED_REQUEST = build_read_request(
    WIND_SENSOR_ADDRESS,
    0x03,
    WIND_REGISTER_START,
    WIND_REGISTER_COUNT,
)
WIND_TEMPERATURE_REQUEST = build_read_request(
    WIND_SENSOR_ADDRESS,
    0x05,
    WIND_REGISTER_START,
    WIND_REGISTER_COUNT,
)


def has_valid_wind_response(response: bytes, function: int) -> bool:
    if len(response) != WIND_RESPONSE_LENGTH or not has_valid_crc(response):
        return False
    if response[0] != WIND_SENSOR_ADDRESS or response[1] != function or response[2] != 0x04:
        return False
    return True


def raw_wind_speed_to_mps(raw_speed: int) -> float:
    return raw_speed / WIND_SPEED_SCALE


def raw_wind_temperature_to_celsius(raw_temperature: int) -> float:
    temperature = (raw_temperature - WIND_TEMPERATURE_OFFSET) / WIND_TEMPERATURE_SCALE
    return min(max(temperature, WIND_TEMPERATURE_RANGE_C[0]), WIND_TEMPERATURE_RANGE_C[1])


def format_latest_value(channel: str, value: float) -> str:
    if channel in {"W_s", "W_t"}:
        return f"{value:.1f}"
    return f"{value:.3f}"


def parse_wind_speed_response(response: bytes) -> Mapping[str, float] | None:
    if not has_valid_wind_response(response, 0x03):
        return None
    raw_speed = response[WIND_SPEED_RAW_BYTE_INDEX]
    return {"W_s": raw_wind_speed_to_mps(raw_speed)}


def parse_wind_temp_response(response: bytes) -> Mapping[str, float] | None:
    if not has_valid_wind_response(response, 0x05):
        return None
    raw_temperature = (
        response[WIND_TEMPERATURE_RAW_HIGH_BYTE_INDEX] << 8
    ) | response[WIND_TEMPERATURE_RAW_LOW_BYTE_INDEX]
    return {"W_t": raw_wind_temperature_to_celsius(raw_temperature)}


def build_wind_port(baudrate: int = 9600, timeout: float = 0.5) -> PortConfig:
    return PortConfig(
        channels=("W_s", "W_t"),
        baudrate=baudrate,
        timeout=timeout,
        poll_commands=(
            PollCommand(
                "风速",
                WIND_SPEED_REQUEST,
                WIND_RESPONSE_LENGTH,
                parse_wind_speed_response,
                delay_after_write=WIND_READ_DELAY_SECONDS,
            ),
            PollCommand(
                "温度",
                WIND_TEMPERATURE_REQUEST,
                WIND_RESPONSE_LENGTH,
                parse_wind_temp_response,
                delay_after_write=WIND_READ_DELAY_SECONDS,
            ),
        ),
        poll_interval=WIND_POLL_INTERVAL_SECONDS,
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
                delay_after_write=0.0,
            ),
        ),
        poll_interval=FASTEST_POLL_INTERVAL_SECONDS,
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
    x_sampled = x_values[::step]
    y_sampled = y_values[::step]
    if x_sampled[-1] != x_values[-1]:
        x_sampled = np.append(x_sampled, x_values[-1])
        y_sampled = np.append(y_sampled, y_values[-1])
    return x_sampled, y_sampled


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


def serial_port_sort_key(port_name: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", str(port_name).strip())
    if match:
        return match.group(1).upper(), int(match.group(2)), str(port_name).upper()
    return str(port_name).upper(), 10**9, str(port_name).upper()


def detect_serial_ports() -> dict[str, str]:
    detected: dict[str, str] = {}
    try:
        ports = list(list_ports.comports())
    except Exception:  # noqa: BLE001
        return detected
    for port in sorted(ports, key=lambda item: serial_port_sort_key(item.device)):
        description = (port.description or "").strip()
        if description and description != "n/a":
            detected[port.device] = f"{port.device} - {description}"
        else:
            detected[port.device] = port.device
    return detected


def merge_port_configs(base: PortConfig, extra: PortConfig, port_name: str) -> PortConfig:
    if base.baudrate != extra.baudrate:
        raise ValueError(f"{port_name} 不能同时用于不同波特率模块")
    channels = tuple(unique_preserve_order((*base.channels, *extra.channels)))
    return PortConfig(
        channels=channels,
        baudrate=base.baudrate,
        timeout=max(base.timeout, extra.timeout),
        poll_commands=(*base.poll_commands, *extra.poll_commands),
        poll_interval=min(base.poll_interval, extra.poll_interval),
    )


def estimate_polling_transfer_limit_hz(port_config: PortConfig) -> float | None:
    if not port_config.poll_commands or port_config.baudrate <= 0:
        return None
    bytes_per_cycle = sum(len(command.request) + command.response_length for command in port_config.poll_commands)
    if bytes_per_cycle <= 0:
        return None
    transfer_seconds = bytes_per_cycle * SERIAL_FRAME_BITS_PER_BYTE / port_config.baudrate
    cycle_seconds = max(port_config.poll_interval, transfer_seconds)
    if cycle_seconds <= 0:
        return None
    return 1.0 / cycle_seconds


def estimate_config_transfer_limit_hz(ports: Mapping[str, PortConfig]) -> float | None:
    limits = [
        limit
        for port_config in ports.values()
        if (limit := estimate_polling_transfer_limit_hz(port_config)) is not None
    ]
    return min(limits) if limits else None


def is_wind_port_config(port_config: PortConfig) -> bool:
    return "W_s" in port_config.channels or "W_t" in port_config.channels


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
                print(f"串口打开: {self.port_name} @ {self.config.baudrate}")
                self.last_data_time = time.monotonic()
                if self.config.poll_commands:
                    self._run_polling_loop()
                else:
                    self._run_line_loop()
            except Exception as exc:  # noqa: BLE001
                print(f"连接失败: {self.port_name}: {exc}")
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
                    print(f"异常数据: {self.port_name}: {line!r}")
                    continue
                self.last_data_time = time.monotonic()
                self._emit_values(parsed)
            except serial.SerialException:
                print(f"读取错误: {self.port_name}")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"读取异常: {self.port_name}: {exc}")
                self._sleep_while_running(0.1)

    def _run_polling_loop(self) -> None:
        while self.running and self.serial_conn is not None:
            cycle_started = time.monotonic()
            sample: dict[str, float] = {}
            try:
                for command in self.config.poll_commands:
                    self.serial_conn.reset_input_buffer()
                    self.serial_conn.write(command.request)
                    self.serial_conn.flush()
                    if command.delay_after_write > 0:
                        time.sleep(command.delay_after_write)
                    response = self.serial_conn.read(command.response_length)
                    parsed = command.parser(response)
                    if parsed is None:
                        self._warn_if_idle()
                        if response:
                            print(f"异常响应: {self.port_name} {command.label}: {response.hex(' ')}")
                        continue
                    sample.update(parsed)
                    self.last_data_time = time.monotonic()

                if all(channel in sample for channel in self.config.channels):
                    self._emit_values([sample[channel] for channel in self.config.channels])
                elapsed = time.monotonic() - cycle_started
                self._sleep_while_running(max(0.0, self.config.poll_interval - elapsed))
            except serial.SerialException:
                print(f"轮询错误: {self.port_name}")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"轮询异常: {self.port_name}: {exc}")
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
            print(f"{self.port_name} 无数据 {now - self.last_data_time:.0f}s")
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
            print(f"启动: {port_name} {list(port_config.channels)}")

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
        self._shutdown_lock = threading.RLock()
        self._shutdown_complete = False
        register_app_instance(self)
        self.data_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=config.queue_size)
        self.serial_manager = SerialManager(config.ports, self.data_queue)
        self.sync_manager = SyncManager(config.ports.keys(), config.sync_timeout, config.max_sync_diff)
        self.history_manager = HistoryFitManager(config.history_plot, config.history_capacity)
        self.transfer_limit_hz = estimate_config_transfer_limit_hz(config.ports)
        self.uses_windtest_interval = any(is_wind_port_config(port_config) for port_config in config.ports.values())

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
        self.refreshing_views = False
        self.last_sample_monotonic: float | None = None

        self.time_capacity = (
            None if config.max_time_points <= 0 else max(config.max_time_points, config.history_capacity)
        )
        self.samples: deque[dict[str, object]] = deque(maxlen=config.history_capacity)
        self.latest_values: dict[str, float] = {}
        self.timestamps: deque[float] = deque(maxlen=self.time_capacity)
        self.channel_data = {
            channel: deque(maxlen=self.time_capacity) for channel in self._collect_channels()
        }
        self.channel_titles, self.channel_units, self.channel_colors = self._build_channel_metadata()
        self.display_channels = unique_preserve_order([plot.channel for plot in config.time_plots])

        self.start_button = pn.widgets.Button(name="开始采集", button_type="primary")
        self.stop_button = pn.widgets.Button(name="停止采集", button_type="light")
        self.pause_toggle = pn.widgets.Toggle(name="暂停记录", button_type="warning", value=False)
        self.autoscale_checkbox = pn.widgets.Checkbox(name="视图跟随数据", value=False)
        self.sample_interval_ms_input = pn.widgets.IntInput(
            name="时间间隔 / ms",
            value=self._default_windtest_interval_ms(),
            start=0,
            end=60000,
        )
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
        self.refresh_plot_button = pn.widgets.Button(name="重置当前视图", button_type="primary")
        self.clear_data_button = pn.widgets.Button(name="清空本轮数据", button_type="danger")
        self.export_button = pn.widgets.Button(name="导出 CSV", button_type="success")
        self.stop_button.disabled = True
        self.pause_toggle.disabled = True

        self.summary_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.latest_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.equation_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.time_panes: dict[str, pn.pane.Bokeh] = {}
        self.relation_panes: dict[str, pn.pane.Bokeh] = {}
        self.time_figure = None
        self.relation_figures = {}
        self.relation_sources: dict[str, dict[str, ColumnDataSource]] = {}
        self.time_sources: dict[str, ColumnDataSource] = {}
        self.history_figure = None
        self.history_sources: dict[str, ColumnDataSource] = {}
        self.history_fit_sources: dict[str, ColumnDataSource] = {}
        self.history_pane = pn.pane.Bokeh(height=430, sizing_mode="stretch_width")
        self.content_tabs: pn.Tabs | None = None
        self.data_table = pn.widgets.Tabulator(
            pd.DataFrame(),
            pagination="local",
            page_size=12,
            sizing_mode="stretch_width",
            height=360,
            disabled=True,
        )
        self.detected_port_labels = detect_serial_ports()
        self.refresh_ports_button = pn.widgets.Button(name="刷新端口", button_type="light")
        self.port_status_pane = pn.pane.HTML(sizing_mode="stretch_width")
        self.port_selectors = self._build_port_selectors()
        self._refresh_port_status()
        self._wire_callbacks()
        self._refresh_views(force=True)

    def _wire_callbacks(self) -> None:
        self.start_button.on_click(self._on_start_collection)
        self.stop_button.on_click(self._on_stop_collection)
        self.pause_toggle.param.watch(self._on_pause_toggle, "value")
        self.autoscale_checkbox.param.watch(lambda _event: self._reset_active_view(), "value")
        self.time_window_slider.param.watch(lambda _event: self._reset_active_view(), "value")
        self.fit_button.on_click(self._on_fit)
        self.clear_fit_button.on_click(self._on_clear_fit)
        self.refresh_plot_button.on_click(lambda _event: self._reset_active_view())
        self.clear_data_button.on_click(self._on_clear_data)
        self.export_button.on_click(self._on_export)
        self.refresh_ports_button.on_click(self._on_refresh_ports)
        self.sample_interval_ms_input.param.watch(self._on_sample_interval_change, "value")
        for selector in self.port_selectors.values():
            selector.param.watch(lambda _event: self._refresh_port_status(), "value")

    def _default_windtest_interval_ms(self) -> int:
        for port_config in self.config.ports.values():
            if is_wind_port_config(port_config):
                return int(round(max(0.0, port_config.poll_interval) * 1000.0))
        return 0

    def _windtest_poll_interval_seconds(self) -> float:
        try:
            interval_ms = int(self.sample_interval_ms_input.value)
        except (TypeError, ValueError):
            interval_ms = self._default_windtest_interval_ms()
        return max(0.0, interval_ms / 1000.0)

    def _runtime_port_config(self, port_config: PortConfig) -> PortConfig:
        if not is_wind_port_config(port_config):
            return port_config
        return replace(port_config, poll_interval=self._windtest_poll_interval_seconds())

    def _on_sample_interval_change(self, _event) -> None:
        if not self.uses_windtest_interval:
            return
        try:
            self.transfer_limit_hz = estimate_config_transfer_limit_hz(self._effective_port_configs())
        except ValueError:
            self.transfer_limit_hz = estimate_config_transfer_limit_hz(self.config.ports)
        self._refresh_port_status()
        self._refresh_status_cards()

    def _build_port_selectors(self) -> dict[str, pn.widgets.Select]:
        selectors: dict[str, pn.widgets.Select] = {}
        for default_port, port_config in self.config.ports.items():
            preferred_port = self._preferred_port(default_port)
            selectors[default_port] = pn.widgets.Select(
                name=f"{default_port} · {', '.join(port_config.channels)}",
                options=self._port_options(default_port, preferred_port),
                value=preferred_port,
                sizing_mode="stretch_width",
            )
        return selectors

    def _preferred_port(self, default_port: str) -> str:
        detected_ports = list(self.detected_port_labels)
        if default_port in self.detected_port_labels:
            return default_port
        if len(self.config.ports) == 1 and detected_ports:
            return detected_ports[0]
        return default_port

    def _port_options(self, default_port: str, current_port: str | None = None) -> dict[str, str]:
        ports = set(self.detected_port_labels)
        ports.add(default_port)
        if current_port:
            ports.add(current_port)
        ordered_ports = sorted(ports, key=serial_port_sort_key)
        options: dict[str, str] = {}
        for port in ordered_ports:
            label = self.detected_port_labels.get(port, port)
            if port == default_port and port not in self.detected_port_labels:
                label = f"{port} - 默认端口"
            options[label] = port
        return options

    def _selected_port_map(self) -> dict[str, str]:
        return {
            default_port: str(selector.value or default_port).strip()
            for default_port, selector in self.port_selectors.items()
        }

    def _effective_port_configs(self) -> dict[str, PortConfig]:
        effective_ports: dict[str, PortConfig] = {}
        selected_ports = self._selected_port_map()
        for default_port, port_config in self.config.ports.items():
            selected_port = selected_ports.get(default_port, default_port)
            if not selected_port:
                raise ValueError("请选择有效串口")
            runtime_config = self._runtime_port_config(port_config)
            if selected_port in effective_ports:
                effective_ports[selected_port] = merge_port_configs(
                    effective_ports[selected_port],
                    runtime_config,
                    selected_port,
                )
            else:
                effective_ports[selected_port] = runtime_config
        return effective_ports

    def _refresh_port_options(self) -> None:
        self.detected_port_labels = detect_serial_ports()
        for default_port, selector in self.port_selectors.items():
            current_port = str(selector.value or self._preferred_port(default_port))
            selector.options = self._port_options(default_port, current_port)
            selector.value = current_port if current_port in selector.options.values() else self._preferred_port(default_port)
        self._refresh_port_status()

    def _refresh_port_status(self) -> None:
        selected_ports = self._selected_port_map() if hasattr(self, "port_selectors") else {}
        detected_count = len(self.detected_port_labels)
        lines = [
            f'<div class="port-line"><strong>识别端口</strong>：{detected_count} 个</div>',
        ]
        for default_port, selected_port in selected_ports.items():
            port_config = self.config.ports[default_port]
            detected_label = self.detected_port_labels.get(selected_port)
            state = "已识别" if detected_label else "未识别"
            channels = ", ".join(port_config.channels)
            interval_text = (
                f" · 间隔 {int(round(self._windtest_poll_interval_seconds() * 1000.0))} ms"
                if is_wind_port_config(port_config)
                else ""
            )
            lines.append(
                f'<div class="port-line"><strong>{html.escape(default_port)}</strong>'
                f' → {html.escape(selected_port)} · {html.escape(channels)} · {state}{interval_text}</div>'
            )
        try:
            self._effective_port_configs()
        except ValueError as exc:
            lines.append(f'<div class="port-line port-warning">{html.escape(str(exc))}</div>')
        self.port_status_pane.object = f'<div class="port-map">{"".join(lines)}</div>'

    def _set_port_controls_disabled(self, disabled: bool) -> None:
        self.refresh_ports_button.disabled = disabled
        self.sample_interval_ms_input.disabled = disabled
        for selector in self.port_selectors.values():
            selector.disabled = disabled

    def _on_refresh_ports(self, _event) -> None:
        self._refresh_port_options()

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

    def start(self) -> bool:
        if self.collecting:
            return True
        try:
            effective_ports = self._effective_port_configs()
        except ValueError as exc:
            self.fit_status = str(exc)
            self._refresh_port_status()
            self._refresh_status_cards()
            return False
        self.serial_manager.stop_all()
        self.serial_manager = SerialManager(effective_ports, self.data_queue)
        self.sync_manager = SyncManager(effective_ports.keys(), self.config.sync_timeout, self.config.max_sync_diff)
        self.transfer_limit_hz = estimate_config_transfer_limit_hz(effective_ports)
        self.collecting = True
        self.last_sample_monotonic = None
        self.sync_manager.buffer.clear()
        self.serial_manager.start_all()
        self.fit_status = "采集中"
        self._set_port_controls_disabled(True)
        self._refresh_port_status()
        self._refresh_status_cards()
        self._refresh_latest_cards()
        return True

    def stop(self) -> None:
        self.collecting = False
        self.pause_toggle.value = False
        self.serial_manager.stop_all()
        self.sync_manager.buffer.clear()
        self._discard_pending_packets()
        self.fit_status = "采集已停止"
        self._set_port_controls_disabled(False)
        self._refresh_port_status()
        self._refresh_status_cards()
        self._refresh_latest_cards()

    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._shutdown_complete:
                return
            self._shutdown_complete = True
            if self.periodic_callback is not None:
                self.periodic_callback.stop()
                self.periodic_callback = None
            self.collecting = False
            self.serial_manager.stop_all()
            self.sync_manager.buffer.clear()
            self._discard_pending_packets()
            unregister_app_instance(self)

    def view(self):
        if self.periodic_callback is None:
            self.periodic_callback = pn.state.add_periodic_callback(
                self._periodic_update,
                period=self.config.plot_update_interval,
                start=True,
            )
        register_page_session(self)
        self._clear_plot_models()
        self.content_tabs = pn.Tabs(
            ("实时曲线", self._build_time_grid()),
            ("关系与拟合", self._build_relation_fit_layout()),
            ("数据表", self._build_table_layout()),
            dynamic=False,
            tabs_location="above",
            sizing_mode="stretch_width",
        )
        self.content_tabs.param.watch(lambda _event: self._refresh_active_tab(force=True), "active")
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
                    self.refresh_plot_button,
                    *([self.sample_interval_ms_input] if self.uses_windtest_interval else []),
                    self.time_window_slider,
                    css_classes=["apple-panel"],
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    pn.pane.Markdown("### 端口设置"),
                    self.refresh_ports_button,
                    *self.port_selectors.values(),
                    self.port_status_pane,
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
                pn.pane.HTML('<a class="nav-link-button" href="/" target="_self">返回目录</a>', sizing_mode="stretch_width"),
            ],
            main=[
                self._build_hero(),
                pn.Column(
                    self.summary_pane,
                    self.latest_pane,
                    css_classes=["metric-section"],
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    self.content_tabs,
                    css_classes=["tab-shell"],
                    sizing_mode="stretch_width",
                ),
            ],
        )

    def _build_hero(self) -> pn.pane.HTML:
        ports = "".join(
            f'<span class="status-pill">{html.escape(port)} · {config.baudrate} · '
            f'{html.escape(", ".join(config.channels))}</span>'
            for port, config in self.config.ports.items()
        )
        return pn.pane.HTML(
            f"""
            <div class="lab-hero">
              <h1>{html.escape(self.config.title)}</h1>
              <p>{html.escape(self.config.subtitle)}</p>
              <div class="hero-meta">{ports}</div>
            </div>
            """,
            sizing_mode="stretch_width",
        )

    def _make_plot_header(self, title: str) -> pn.Row:
        return pn.Row(
            pn.pane.HTML(f'<div class="plot-title">{html.escape(title)}</div>', sizing_mode="stretch_width"),
            css_classes=["plot-card-header"],
            sizing_mode="stretch_width",
        )

    def _clear_plot_models(self) -> None:
        self.time_panes.clear()
        self.relation_panes.clear()
        self.time_figure = None
        self.relation_figures = {}
        self.time_sources.clear()
        self.relation_sources.clear()
        self.history_figure = None
        self.history_sources.clear()
        self.history_fit_sources.clear()

    def _build_time_grid(self) -> pn.Column:
        figure_model = self._create_combined_time_plot(width=980, height=430)
        pane = pn.pane.Bokeh(figure_model, height=430, sizing_mode="stretch_width")
        self.time_panes["combined"] = pane
        return pn.Column(
            self._make_plot_header("实时曲线总览"),
            pane,
            css_classes=["plot-card", "plot-card-time"],
            sizing_mode="stretch_width",
        )

    def _build_relation_fit_layout(self) -> pn.Column:
        relation_items = []
        for relation_plot in self.config.relation_plots:
            figure_model = self._create_relation_plot(relation_plot, width=520, height=330)
            pane = pn.pane.Bokeh(figure_model, height=330, sizing_mode="stretch_width")
            self.relation_panes[relation_plot.axis_id] = pane
            relation_items.append(
                pn.Column(
                    self._make_plot_header(relation_plot.title),
                    pane,
                    css_classes=["plot-card", "plot-card-relation"],
                    sizing_mode="stretch_width",
                )
            )
        self.history_figure = self._create_history_plot(width=900, height=430)
        self.history_pane.object = self.history_figure
        return pn.Column(
            pn.pane.HTML('<div class="section-title">变量关系</div>'),
            pn.GridBox(
                *relation_items,
                ncols=max(1, min(len(relation_items), self.config.dashboard_columns)),
                sizing_mode="stretch_width",
            ),
            pn.pane.HTML('<div class="section-title">历史拟合</div>'),
            pn.Column(
                self._make_plot_header(self.config.history_plot.title),
                self.history_pane,
                css_classes=["plot-card", "plot-card-history"],
                sizing_mode="stretch_width",
            ),
            self.equation_pane,
            sizing_mode="stretch_width",
        )

    def _build_table_layout(self) -> pn.Column:
        return pn.Column(
            pn.pane.Markdown("最近样本"),
            self.data_table,
            sizing_mode="stretch_width",
        )

    def _new_figure(
        self,
        *,
        title: str,
        x_label: str,
        y_label: str,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        width: int,
        height: int,
    ):
        fig = figure(
            title=title,
            width=width,
            height=height,
            x_range=Range1d(*x_range),
            y_range=Range1d(*y_range),
            tools="pan,wheel_zoom,xwheel_zoom,ywheel_zoom,box_zoom,xbox_zoom,ybox_zoom,reset,save",
            toolbar_location="above",
            sizing_mode="stretch_width",
        )
        fig.xaxis.axis_label = x_label
        fig.yaxis.axis_label = y_label
        fig.background_fill_color = "#ffffff"
        fig.border_fill_color = "#ffffff"
        fig.outline_line_color = "#d1d1d6"
        fig.grid.grid_line_color = "#d1d1d6"
        fig.grid.grid_line_alpha = 0.28
        fig.axis.major_label_text_color = "#3a3a3c"
        fig.axis.axis_label_text_color = "#636366"
        fig.title.text_color = "#1c1c1e"
        fig.title.text_font_size = "12pt"
        fig.title.text_font_style = "bold"
        fig.xaxis.axis_label_text_font_size = "10pt"
        fig.yaxis.axis_label_text_font_size = "10pt"
        fig.toolbar.logo = None
        wheel_zoom_tools = [tool for tool in fig.tools if isinstance(tool, WheelZoomTool)]
        for tool in wheel_zoom_tools:
            if tool.dimensions == "both":
                fig.toolbar.active_scroll = tool
                break
        return fig

    def _combined_time_y_range(self) -> tuple[float, float]:
        y_starts = [plot.y_range[0] for plot in self.config.time_plots]
        y_ends = [plot.y_range[1] for plot in self.config.time_plots]
        if not y_starts or not y_ends:
            return (0.0, 1.0)
        return (float(min(y_starts)), float(max(y_ends)))

    def _create_combined_time_plot(self, width: int, height: int):
        y_range = self._combined_time_y_range()
        fig = self._new_figure(
            title="实时曲线总览",
            x_label="实验时间 t (s)",
            y_label="采集值（按图例区分单位）",
            x_range=(0.0, max(1.0, float(self.time_window_slider.value))),
            y_range=y_range,
            width=width,
            height=height,
        )
        fig.x_range.bounds = (0.0, 1_000_000_000.0)
        fig.y_range.bounds = y_range
        self.time_figure = fig
        self.time_sources.clear()
        for plot in self.config.time_plots:
            source = ColumnDataSource(data={"x": [], "y": []})
            unit = unit_from_label(plot.y_label)
            legend_label = f"{plot.title} ({unit})" if unit else plot.title
            renderer = fig.line(
                "x",
                "y",
                source=source,
                color=plot.color,
                line_width=2.4,
                legend_label=legend_label,
            )
            fig.add_tools(
                HoverTool(
                    renderers=[renderer],
                    tooltips=[("t", "@x{0.00} s"), (legend_label, "@y{0.000}")],
                    mode="mouse",
                )
            )
            self.time_sources[plot.axis_id] = source
        if len(self.config.time_plots) > 1:
            fig.legend.location = "top_left"
            fig.legend.click_policy = "hide"
            fig.legend.label_text_font_size = "9pt"
            fig.legend.background_fill_alpha = 0.78
        self._update_all_time_sources(reset_view=True)
        return fig

    def _create_relation_plot(self, plot: RelationPlotConfig, width: int, height: int):
        fig = self._new_figure(
            title=plot.title,
            x_label=plot.x_label,
            y_label=plot.y_label,
            x_range=plot.x_range,
            y_range=plot.y_range,
            width=width,
            height=height,
        )
        sources: dict[str, ColumnDataSource] = {}
        for series in plot.series:
            source = ColumnDataSource(data={"x": [], "y": []})
            fig.scatter(
                "x",
                "y",
                source=source,
                color=series.color,
                size=series.marker_size,
                alpha=series.alpha,
                legend_label=series.label,
            )
            sources[series.y_channel] = source
        fig.add_tools(HoverTool(tooltips=[("x", "@x{0.000}"), ("y", "@y{0.000}")], mode="mouse"))
        if len(plot.series) > 1:
            fig.legend.location = "top_left"
            fig.legend.click_policy = "hide"
        self.relation_sources[plot.axis_id] = sources
        self.relation_figures[plot.axis_id] = fig
        self._update_relation_sources(plot, reset_view=True)
        return fig

    def _create_history_plot(self, width: int, height: int):
        history_plot = self.config.history_plot
        x_range = history_plot.x_range or (0.0, max(1.0, float(self.time_window_slider.value)))
        fig = self._new_figure(
            title=history_plot.title,
            x_label=history_plot.x_label,
            y_label=history_plot.y_label,
            x_range=x_range,
            y_range=history_plot.y_range,
            width=width,
            height=height,
        )
        self.history_figure = fig
        self.history_sources.clear()
        self.history_fit_sources.clear()
        for series in history_plot.series:
            sample_source = ColumnDataSource(data={"x": [], "y": []})
            fit_source = ColumnDataSource(data={"x": [], "y": []})
            fig.scatter(
                "x",
                "y",
                source=sample_source,
                color=series.color,
                size=series.marker_size,
                alpha=series.marker_alpha,
                legend_label=f"{series.label} 样本",
            )
            fig.line(
                "x",
                "y",
                source=fit_source,
                color=series.color,
                line_width=series.line_width,
                legend_label=f"{series.label} 拟合",
            )
            self.history_sources[series.y_channel] = sample_source
            self.history_fit_sources[series.y_channel] = fit_source
        fig.add_tools(HoverTool(tooltips=[("x", "@x{0.000}"), ("y", "@y{0.000}")], mode="mouse"))
        if len(history_plot.series) > 1:
            fig.legend.location = "top_left"
            fig.legend.click_policy = "hide"
        self._update_history_sources(reset_view=True)
        return fig

    def _on_start_collection(self, _event) -> None:
        if not self.start():
            return
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
        self._set_port_controls_disabled(False)
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
            self.fit_status = "拟合失败"
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
            if now - self.last_status_refresh >= self.config.status_update_interval:
                self._refresh_live_status()
                self.last_status_refresh = now
            if now - self.last_plot_refresh >= self.config.plot_redraw_interval:
                self._sync_active_plot_data()
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

    def _set_range(self, figure_model, x_range: tuple[float, float], y_range: tuple[float, float] | None = None) -> None:
        if figure_model is None:
            return
        x_start, x_end = x_range
        if np.isfinite(x_start) and np.isfinite(x_end) and not np.isclose(x_start, x_end):
            figure_model.x_range.start = float(x_start)
            figure_model.x_range.end = float(x_end)
        if y_range is not None:
            y_start, y_end = y_range
            if np.isfinite(y_start) and np.isfinite(y_end) and not np.isclose(y_start, y_end):
                figure_model.y_range.start = float(y_start)
                figure_model.y_range.end = float(y_end)

    def _time_plot_arrays(self, plot: TimePlotConfig) -> tuple[np.ndarray, np.ndarray]:
        x_values = np.asarray(self.timestamps, dtype=np.float64)
        y_values = np.asarray(self.channel_data.get(plot.channel, []), dtype=np.float64)
        return downsample_pair(x_values, y_values, self.config.time_render_points)

    def _combined_time_plot_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        x_values = np.asarray(self.timestamps, dtype=np.float64)
        default_x_range = (0.0, max(1.0, float(self.time_window_slider.value)))
        default_y_range = self._combined_time_y_range()
        if len(x_values) == 0:
            return default_x_range, default_y_range
        x_max = float(x_values[-1])
        return (0.0, max(x_max, default_x_range[1])), default_y_range

    def _update_all_time_sources(self, reset_view: bool = False) -> None:
        for plot in self.config.time_plots:
            source = self.time_sources.get(plot.axis_id)
            if source is None:
                continue
            x_values, y_values = self._time_plot_arrays(plot)
            source.data = {"x": x_values, "y": y_values}
        if reset_view or self.autoscale_checkbox.value:
            self._set_range(self.time_figure, *self._combined_time_plot_ranges())

    def _relation_series_arrays(self, series: RelationSeriesConfig) -> tuple[np.ndarray, np.ndarray]:
        x_values = np.asarray(self.channel_data.get(series.x_channel, []), dtype=np.float64)[-series.max_points :]
        y_values = np.asarray(self.channel_data.get(series.y_channel, []), dtype=np.float64)[-series.max_points :]
        return downsample_pair(x_values, y_values, series.max_points)

    def _relation_ranges(self, plot: RelationPlotConfig) -> tuple[tuple[float, float], tuple[float, float]]:
        x_samples: list[np.ndarray] = []
        y_samples: list[np.ndarray] = []
        for series in plot.series:
            x_values, y_values = self._relation_series_arrays(series)
            if len(x_values) > 0:
                x_samples.append(x_values)
                y_samples.append(y_values)
        x_range = auto_limits(x_samples, plot.x_range) if plot.auto_scale_x else plot.x_range
        y_range = auto_limits(y_samples, plot.y_range) if plot.auto_scale_y else plot.y_range
        return x_range, y_range

    def _update_relation_sources(self, plot: RelationPlotConfig, reset_view: bool = False) -> None:
        sources = self.relation_sources.get(plot.axis_id, {})
        for series in plot.series:
            source = sources.get(series.y_channel)
            if source is None:
                continue
            x_values, y_values = self._relation_series_arrays(series)
            source.data = {"x": x_values, "y": y_values}
        if reset_view or self.autoscale_checkbox.value:
            self._set_range(self.relation_figures.get(plot.axis_id), *self._relation_ranges(plot))

    def _history_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        history_plot = self.config.history_plot
        x_values, _y_values = self.history_manager.get_plot_data()
        x_range = history_plot.x_range or (0.0, max(1.0, float(self.time_window_slider.value)))
        if len(x_values) > 0 and history_plot.auto_scale_x:
            x_range = auto_limits([x_values], x_range)
        return x_range, history_plot.y_range

    def _update_history_sources(self, reset_view: bool = False) -> None:
        history_plot = self.config.history_plot
        x_values, y_values = self.history_manager.get_plot_data()
        for series in history_plot.series:
            sample_source = self.history_sources.get(series.y_channel)
            if sample_source is not None:
                y_series = y_values.get(series.y_channel, np.asarray([], dtype=np.float64))
                x_plot, y_plot = downsample_pair(x_values, y_series, history_plot.max_points)
                sample_source.data = {"x": x_plot, "y": y_plot}
        fit_x, fit_curves = self.history_manager.get_fit_curves(history_plot.fit_points)
        for series in history_plot.series:
            fit_source = self.history_fit_sources.get(series.y_channel)
            if fit_source is None:
                continue
            fit_y = fit_curves.get(series.y_channel) if fit_x is not None else None
            fit_source.data = {
                "x": np.asarray([], dtype=np.float64) if fit_x is None else fit_x,
                "y": np.asarray([], dtype=np.float64) if fit_y is None else fit_y,
            }
        if reset_view or self.autoscale_checkbox.value:
            self._set_range(self.history_figure, *self._history_ranges())

    def _refresh_views(self, force: bool = False) -> None:
        self._refresh_status_cards()
        self._refresh_latest_cards()
        self._refresh_active_tab(force=force)

    def _refresh_live_status(self) -> None:
        self._refresh_status_cards()
        self._refresh_latest_cards()

    def _refresh_slow_views(self) -> None:
        active = self._active_tab_index()
        if active == 2:
            self._refresh_table()
        elif active == 1:
            self._refresh_equations()

    def _active_tab_index(self) -> int:
        if self.content_tabs is None:
            return 0
        return int(self.content_tabs.active or 0)

    def _sync_active_plot_data(self) -> None:
        active = self._active_tab_index()
        if active == 0:
            self._refresh_time_plots()
        elif active == 1:
            self._refresh_relation_plots()
            self._refresh_history_plot()
        elif active == 2:
            self._refresh_table()

    def _refresh_active_tab(self, force: bool = False) -> None:
        if self.refreshing_views:
            return
        self.refreshing_views = True
        try:
            self._refresh_active_tab_unlocked(force=force)
        finally:
            self.refreshing_views = False

    def _refresh_active_tab_unlocked(self, force: bool = False) -> None:
        active = self._active_tab_index()
        if active == 0:
            self._refresh_time_plots(force=force)
        elif active == 1:
            self._refresh_relation_plots(force=force)
            self._refresh_history_plot()
            self._refresh_equations()
        elif active == 2:
            self._refresh_table()

    def _reset_active_view(self) -> None:
        active = self._active_tab_index()
        if active == 0:
            self._set_range(self.time_figure, *self._combined_time_plot_ranges())
        elif active == 1:
            for plot in self.config.relation_plots:
                self._set_range(self.relation_figures.get(plot.axis_id), *self._relation_ranges(plot))
            self._set_range(self.history_figure, *self._history_ranges())

    def _refresh_status_cards(self) -> None:
        now = time.monotonic()
        elapsed = 0.0 if self.start_timestamp is None else max(0.0, now - self.start_timestamp)
        rate = self.sample_count / elapsed if elapsed > 0 else 0.0
        transfer_limit = f"{self.transfer_limit_hz:.1f}" if self.transfer_limit_hz is not None else "n/a"
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
        export_text = (
            f'<div style="margin-top: 8px;"><span class="status-pill">导出: '
            f"{html.escape(str(self.last_export_path))}</span></div>"
            if self.last_export_path
            else ""
        )
        self.summary_pane.object = f"""
        <div class="metric-grid">
          <div class="metric-card"><div class="metric-name">状态</div><div class="metric-value">{html.escape(status)}</div></div>
          <div class="metric-card"><div class="metric-name">{html.escape(self.config.status_label)}</div><div class="metric-value">{self.sample_count}</div></div>
          <div class="metric-card"><div class="metric-name">采样速率</div><div class="metric-value">{rate:.2f}<span class="metric-unit">Hz</span></div></div>
          <div class="metric-card"><div class="metric-name">当前理论上限</div><div class="metric-value">{transfer_limit}<span class="metric-unit">Hz</span></div></div>
          <div class="metric-card"><div class="metric-name">{html.escape(self.config.discarded_label)}</div><div class="metric-value">{self.discarded_count}</div></div>
          <div class="metric-card"><div class="metric-name">队列</div><div class="metric-value">{self.data_queue.qsize()}</div></div>
          <div class="metric-card"><div class="metric-name">拟合/导出</div><div class="metric-value" style="font-size: 15px;">{html.escape(self.fit_status)}</div></div>
        </div>
        {export_text}
        """

    def _refresh_latest_cards(self) -> None:
        if not self.latest_values:
            message = "未采集" if not self.collecting else "等待数据"
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
            formatted_value = format_latest_value(channel, value)
            cards.append(
                f"""
                <div class="metric-card" style="border-left-color: {html.escape(color)};">
                  <div class="metric-name">{html.escape(title)}</div>
                  <div class="metric-value">{formatted_value}<span class="metric-unit">{html.escape(unit)}</span></div>
                </div>
                """
            )
        self.latest_pane.object = f'<div class="metric-grid">{"".join(cards)}</div>'

    def _refresh_time_plots(self, force: bool = False) -> None:
        if not force and not self.time_sources:
            return
        self._update_all_time_sources(reset_view=force)

    def _refresh_relation_plots(self, force: bool = False) -> None:
        if not force and not self.relation_sources:
            return
        for plot in self.config.relation_plots:
            self._update_relation_sources(plot, reset_view=False)

    def _refresh_history_plot(self) -> None:
        self._update_history_sources(reset_view=False)

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
          <div><b>拟合模型</b>：{html.escape(self.fit_status)} | {html.escape(fit_time)}</div>
          {''.join(rows)}
        </div>
        """

    def _refresh_table(self) -> None:
        df = self._data_frame().tail(200).copy()
        for column in df.select_dtypes(include=[np.number]).columns:
            df[column] = df[column].round(4)
        self.data_table.value = df

    def _make_time_plot(self, plot: TimePlotConfig, width: int = 520, height: int = 285):
        x_values = np.asarray(self.timestamps, dtype=np.float64)
        y_values = np.asarray(self.channel_data.get(plot.channel, []), dtype=np.float64)
        x_values, y_values = downsample_pair(x_values, y_values, self.config.time_render_points)
        if len(x_values) > 0:
            x_max = float(x_values[-1])
            x_min = 0.0
            x_plot = x_values
            y_plot = y_values
        else:
            x_min, x_max = 0.0, max(1.0, float(self.time_window_slider.value))
            x_plot = np.asarray([], dtype=np.float64)
            y_plot = np.asarray([], dtype=np.float64)
        y_lim = plot.y_range
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
            xlim=(x_min, max(x_max, float(self.time_window_slider.value), x_min + 1.0)),
            ylim=y_lim,
            width=width,
            height=height,
            show_grid=True,
            bgcolor="#ffffff",
            fontsize={"title": 12, "labels": 10, "ticks": 9},
        )

    def _make_relation_plot(self, plot: RelationPlotConfig, width: int = 520, height: int = 330):
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
            width=width,
            height=height,
            show_grid=True,
            bgcolor="#ffffff",
            legend_position="right",
            toolbar="above",
            shared_axes=False,
            axiswise=True,
            framewise=True,
            fontsize={"title": 12, "labels": 10, "ticks": 9},
        )

    def _make_history_plot(self, width: int = 900, height: int = 430):
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
            width=width,
            height=height,
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
    wind_range = WIND_SPEED_RANGE_MPS
    temp_range = WIND_TEMPERATURE_RANGE_C
    return MonitorConfig(
        title="热敏风速传感器实时监测",
        subtitle="风速/温度独立实验 | COM5: W_s, W_t | RS485 9600 baud",
        ports={"COM5": build_wind_port()},
        time_plots=(
            TimePlotConfig("ws", "W_s", "风速 W_s", "#248a3d", "风速 (m/s)", wind_range),
            TimePlotConfig("wt", "W_t", "温度 W_t", "#d70015", "温度 (C)", temp_range),
        ),
        relation_plots=(
            RelationPlotConfig(
                "rel",
                "温度-风速关系",
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
            "温度关于风速的实验拟合",
            temp_range,
            wind_range,
            (HistorySeriesConfig("W_t", "W_t", "#af52de"),),
            "W_s",
            max_points=300,
            fit_points=100,
        ),
        export_dir="exports/wind_only",
        experiment_note="用于风速传感器响应测试、温度通道观察和风速-温度耦合分析。",
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
    wind_range = WIND_SPEED_RANGE_MPS
    temp_range = WIND_TEMPERATURE_RANGE_C
    return MonitorConfig(
        title="平板引射器压力-风速耦合监测",
        subtitle="压力/风速同步实验 | COM11: P1, P2 | COM5: W_s, W_t",
        ports={"COM11": build_pressure_port(), "COM5": build_wind_port()},
        time_plots=(
            TimePlotConfig("p1", "P1", "P1 压力", "#0071e3", "压力 (kPa)", pressure_range),
            TimePlotConfig("p2", "P2", "P2 压力", "#bf5a00", "压力 (kPa)", pressure_range),
            TimePlotConfig("ws", "W_s", "风速 W_s", "#248a3d", "风速 (m/s)", wind_range),
            TimePlotConfig("wt", "W_t", "温度 W_t", "#d70015", "温度 (C)", temp_range),
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
        sync_timeout=1.5,
        max_sync_diff=0.45,
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
    ExperimentSpec("wind", "风速单变量实验", "基础实验", "COM5 采集 W_s/W_t，风速响应与温度通道变化。", wind_config()),
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
    register_page_session(None)
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
                <a class="experiment-card-link" href="/{html.escape(experiment.key)}" target="_self">
                  <div class="{card_class}">
                    <div class="metric-name">{html.escape(experiment.key)}</div>
                    <div class="metric-value" style="font-size: 20px;">{html.escape(experiment.name)}</div>
                    <div style="min-height: 28px;">{port_badges}</div>
                    <span class="experiment-card-action">进入实验</span>
                  </div>
                </a>
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
                  <p>实时采集 · 拟合分析 · CSV 导出</p>
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
    print("debug 检查...")
    for experiment in EXPERIMENTS:
        print(f"{experiment.key}: {experiment.name}")
        app = MonitorApp(replace(experiment.config, show_browser=False, server_port=0))
        app.view()
        sample = {channel: 1.0 for channel in app._collect_channels() if channel != "elapsed"}
        if "T_a" in sample:
            sample.pop("T_a", None)
        app._record_sample(sample)
        for active in range(3):
            if app.content_tabs is not None:
                app.content_tabs.active = active
            app._refresh_active_tab(force=True)
            app._reset_active_view()
    print("debug 检查通过")
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
