"""通用工具函数与常量。"""
from __future__ import annotations

import os
import tempfile
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


def resolve_data_path(configured: str) -> Path:
    """将数据路径解析为可写位置, 兼容本地 / Docker / Streamlit Cloud 等环境。

    - 展开 `~`; 相对路径基于 PROJECT_ROOT。
    - 若所在目录可写则优先使用 (本地开发 / Docker volume 映射的 /app/data)。
    - 否则回退到 `~/.paddy-quant/<文件名>`; 若 home 也不可写再回退系统临时目录
      (Streamlit Cloud 等云端应用目录只读时, 避免保存失败导致 App 崩溃)。
    """
    import warnings

    raw = os.path.expanduser(configured)
    p = Path(raw) if os.path.isabs(raw) else (PROJECT_ROOT / raw)
    d = p.parent
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write_test"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return p
    except OSError:
        fallback_dir = Path(os.path.expanduser("~")) / ".paddy-quant"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback_dir = Path(tempfile.gettempdir()) / "paddy-quant"
            fallback_dir.mkdir(parents=True, exist_ok=True)
        warnings.warn(
            f"数据目录不可写, 已回退到 {fallback_dir} (原配置: {configured})"
        )
        return fallback_dir / p.name


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
