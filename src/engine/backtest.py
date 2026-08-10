"""轻量向量化回测引擎 (不依赖 vectorbt, 纯 pandas/numpy)。

支持策略: sma_cross(双均线) / momentum(动量) / mean_reversion(均值回归)
严格防未来函数: 信号使用 shift(1) 后的仓位。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma_cross_signals(close: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()
    sig = pd.Series(0, index=close.index)
    sig[ma_f > ma_s] = 1
    sig[ma_f < ma_s] = -1
    return sig


def momentum_signals(close: pd.Series, window: int = 20) -> pd.Series:
    ret = close.pct_change(window)
    sig = pd.Series(0, index=close.index)
    sig[ret > 0] = 1
    sig[ret < 0] = -1
    return sig


def mean_reversion_signals(close: pd.Series, window: int = 20, n_std: float = 2) -> pd.Series:
    ma = close.rolling(window).mean()
    sd = close.rolling(window).std()
    z = (close - ma) / sd
    sig = pd.Series(0, index=close.index)
    sig[z < -n_std] = 1
    sig[z > n_std] = -1
    return sig


_STRATS = {
    "sma_cross": sma_cross_signals,
    "momentum": momentum_signals,
    "mean_reversion": mean_reversion_signals,
}


class Backtester:
    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        self.cap = initial_capital
        self.comm = commission

    def run(self, df: pd.DataFrame, strategy: str = "sma_cross", **params):
        if strategy not in _STRATS:
            raise ValueError(f"未知策略: {strategy}, 可选 {list(_STRATS)}")

        close = df["close"]
        raw_sig = _STRATS[strategy](close, **params)
        pos = raw_sig.shift(1).fillna(0)  # 防止未来函数

        ret = close.pct_change().fillna(0)
        strat_ret = pos * ret

        # 仅在仓位变化时收佣金
        trade = pos.diff().abs() > 0
        strat_ret = strat_ret - trade.astype(float) * self.comm

        equity = (1 + strat_ret).cumprod() * self.cap

        total_ret = equity.iloc[-1] / self.cap - 1
        n = len(strat_ret)
        ann_ret = (1 + total_ret) ** (252 / n) - 1 if n > 0 else 0.0
        roll_max = equity.cummax()
        dd = (equity - roll_max) / roll_max
        max_dd = float(dd.min())
        sharpe = float(np.sqrt(252) * strat_ret.mean() / (strat_ret.std() + 1e-12))
        nonzero = strat_ret[strat_ret != 0]
        win_rate = float((strat_ret > 0).sum() / (len(nonzero) + 1e-12))

        return {
            "strategy": strategy,
            "equity": equity,
            "total_return": float(total_ret),
            "annual_return": float(ann_ret),
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "win_rate": win_rate,
            "n_trades": int(trade.sum()),
        }
