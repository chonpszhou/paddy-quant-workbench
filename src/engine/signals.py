"""多周期买卖点信号引擎 (参考小隐寺信号形态)。

计算:
- 快慢均线交叉 -> 金叉 BUY / 死叉 SELL
- RSI 超买超卖
- 量能 z-score -> 异常换手提醒 (E)
- 趋势方向 (up/down/side)
- 连续性: 当前持仓状态 HOLD_LONG / HOLD_SHORT
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.common import load_settings


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100 - 100 / (1 + rs)


class SignalEngine:
    def __init__(self, settings: dict | None = None):
        self.s = settings or load_settings()
        sig = self.s["signal"]
        self.fast = sig["fast_ma"]
        self.slow = sig["slow_ma"]
        self.rsi_p = sig["rsi_period"]
        self.vol_win = sig["volume_zscore_window"]
        self.anom_z = sig["anomaly_volume_z"]

    def analyze(self, df: pd.DataFrame, timeframe: str = "1d"):
        if df is None or df.empty:
            return df, {"signal": "N/A", "trend": "N/A"}

        d = df.copy()
        d["ma_fast"] = d["close"].rolling(self.fast).mean()
        d["ma_slow"] = d["close"].rolling(self.slow).mean()
        d["rsi"] = _rsi(d["close"], self.rsi_p)

        vol_mean = d["volume"].rolling(self.vol_win).mean()
        vol_std = d["volume"].rolling(self.vol_win).std()
        d["vol_z"] = (d["volume"] - vol_mean) / (vol_std + 1e-9)
        d["anomaly_vol"] = d["vol_z"] > self.anom_z

        diff = d["ma_fast"] - d["ma_slow"]
        diff_prev = diff.shift(1)
        d["cross"] = 0
        d.loc[(diff > 0) & (diff_prev <= 0), "cross"] = 1   # 金叉
        d.loc[(diff < 0) & (diff_prev >= 0), "cross"] = -1   # 死叉

        d["trend"] = np.where(diff > 0, "up", np.where(diff < 0, "down", "side"))

        last = d.dropna().iloc[-1]
        if last["cross"] == 1:
            sig = "BUY"
        elif last["cross"] == -1:
            sig = "SELL"
        elif last["trend"] == "up":
            sig = "HOLD_LONG"
        elif last["trend"] == "down":
            sig = "HOLD_SHORT"
        else:
            sig = "HOLD"

        extra = {
            "signal": sig,
            "trend": last["trend"],
            "close": float(last["close"]),
            "rsi": float(last["rsi"]),
            "ma_fast": float(last["ma_fast"]),
            "ma_slow": float(last["ma_slow"]),
            "anomaly_vol": bool(last["anomaly_vol"]),
            "vol_z": float(last["vol_z"]),
            "timeframe": timeframe,
        }
        return d, extra
