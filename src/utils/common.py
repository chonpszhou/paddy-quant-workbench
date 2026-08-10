"""通用工具函数与常量。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# 涨跌配色: 目标市场为美股/港股/加密, 采用国际惯例 涨=绿 跌=红
COLOR_UP = "#16a34a"    # 涨 (绿)
COLOR_DOWN = "#dc2626"  # 跌 (红)
COLOR_FLAT = "#6b7280"  # 平

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_settings(path: str | None = None) -> dict:
    """加载 config/settings.yaml。"""
    cfg_path = Path(path) if path else PROJECT_ROOT / "config" / "settings.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dir(path: str | os.PathLike) -> Path:
    """确保目录存在并返回 Path。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def tf_to_yf_interval(timeframe: str) -> str:
    """把内部周期映射为 yfinance interval。"""
    mapping = {"1d": "1d", "4h": "4h", "1h": "1h", "15m": "15m"}
    if timeframe not in mapping:
        raise ValueError(f"不支持的周期: {timeframe}")
    return mapping[timeframe]


def tf_to_binance_interval(timeframe: str) -> str:
    """把内部周期映射为 Binance klines interval。"""
    mapping = {"1d": "1d", "4h": "4h", "1h": "1h", "15m": "15m"}
    if timeframe not in mapping:
        raise ValueError(f"不支持的周期: {timeframe}")
    return mapping[timeframe]
