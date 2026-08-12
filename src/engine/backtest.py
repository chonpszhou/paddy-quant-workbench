"""轻量向量化回测引擎 (不依赖 vectorbt, 纯 pandas/numpy)。

支持策略:
  sma_cross(双均线) / momentum(动量) / mean_reversion(均值回归, z-score)
  donchian(通道突破·趋势跟踪) / dual_thrust(日内突破) /
  rsi_reversal(RSI 逆向均值回归) / atr_channel(ATR 通道突破·波动自适应)

严格防未来函数: 信号使用 shift(1) 后的仓位。
信号函数统一接收整张 df（可取 open/high/low/close），便于 OHLC 类策略。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# —— 指标基元 ——
def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - 100.0 / (1.0 + rs)


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window).mean()


# —— 信号函数（统一接收 df，返回与索引等长的 -1/0/1 仓位信号）——
def sma_cross_signals(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.Series:
    close = df["close"]
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()
    sig = pd.Series(0, index=close.index)
    sig[ma_f > ma_s] = 1
    sig[ma_f < ma_s] = -1
    return sig


def momentum_signals(df: pd.DataFrame, window: int = 20) -> pd.Series:
    close = df["close"]
    ret = close.pct_change(window)
    sig = pd.Series(0, index=close.index)
    sig[ret > 0] = 1
    sig[ret < 0] = -1
    return sig


def mean_reversion_signals(df: pd.DataFrame, window: int = 20, n_std: float = 2.0) -> pd.Series:
    close = df["close"]
    ma = close.rolling(window).mean()
    sd = close.rolling(window).std()
    z = (close - ma) / (sd + 1e-12)
    sig = pd.Series(0, index=close.index)
    sig[z < -n_std] = 1
    sig[z > n_std] = -1
    return sig


def donchian_signals(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """通道突破（海龟式趋势跟踪）。突破 N 日最高/最低后持仓，直到反向突破。"""
    high, low, close = df["high"], df["low"], df["close"]
    upper = high.rolling(window).max().shift(1)   # 用 t-1 的通道，避免未来函数
    lower = low.rolling(window).min().shift(1)
    sig = pd.Series(0, index=close.index)
    sig[close > upper] = 1
    sig[close < lower] = -1
    # 突破后持仓直到反向突破（ffill 保留上一次方向）；初始未突破则为空仓
    sig = sig.replace(0, np.nan).ffill().fillna(0)
    return sig


def dual_thrust_signals(df: pd.DataFrame, k1: float = 0.5, k2: float = 0.5) -> pd.Series:
    """Dual Thrust 日内突破：以前一日波动区间构造上下触发线。"""
    open_, high, low, close = df["open"], df["high"], df["low"], df["close"]
    hh = high.shift(1)
    ll = low.shift(1)
    lc = close.shift(1)          # HC == LC，区间 = max(HH-LC, LC-LL)
    rng = (hh - lc).abs()
    buy_trigger = open_ + k1 * rng
    sell_trigger = open_ - k2 * rng
    sig = pd.Series(0, index=close.index)
    sig[close > buy_trigger] = 1
    sig[close < sell_trigger] = -1
    return sig


def rsi_reversal_signals(df: pd.DataFrame, period: int = 14,
                         oversold: float = 30.0, overbought: float = 70.0,
                         cooldown: int = 0) -> pd.Series:
    """RSI 逆向均值回归：超卖做多、超买卖空。

    参数:
        cooldown: 信号冷却期（K线数）。当信号从非零变为零后，接下来
                  cooldown 根K线强制空仓（sig=0），抑制反复开平。
                  默认 0 表示不启用冷却。
    """
    close = df["close"]
    r = _rsi(close, period)
    sig = pd.Series(0, index=close.index)
    sig[r < oversold] = 1
    sig[r > overbought] = -1
    if cooldown > 0:
        cd = 0
        for i in range(len(sig)):
            if cd > 0:
                sig.iloc[i] = 0
                cd -= 1
            elif i > 0 and sig.iloc[i] == 0 and sig.iloc[i - 1] != 0:
                cd = cooldown
    return sig


def atr_channel_signals(df: pd.DataFrame, window: int = 20, mult: float = 3.0) -> pd.Series:
    """ATR 通道突破（波动自适应趋势跟踪）：中轨±mult×ATR 构造通道。"""
    close = df["close"]
    center = close.rolling(window).mean()
    atr = _atr(df, window)
    upper = center + mult * atr
    lower = center - mult * atr
    sig = pd.Series(0, index=close.index)
    sig[close > upper] = 1
    sig[close < lower] = -1
    sig = sig.replace(0, np.nan).ffill().fillna(0)
    return sig


# 需要 OHLC 列的策略（缺列时给出清晰报错）
_OHLC_STRATS = {"donchian", "dual_thrust", "atr_channel"}

_STRATS = {
    "sma_cross": sma_cross_signals,
    "momentum": momentum_signals,
    "mean_reversion": mean_reversion_signals,
    "donchian": donchian_signals,
    "dual_thrust": dual_thrust_signals,
    "rsi_reversal": rsi_reversal_signals,
    "atr_channel": atr_channel_signals,
}


class Backtester:
    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        self.cap = initial_capital
        self.comm = commission

    def run(self, df: pd.DataFrame, strategy: str = "sma_cross", **params):
        if strategy not in _STRATS:
            raise ValueError(f"未知策略: {strategy}, 可选 {list(_STRATS)}")
        if strategy in _OHLC_STRATS:
            missing = [c for c in ("open", "high", "low") if c not in df.columns]
            if missing:
                raise ValueError(f"策略 {strategy} 需要 OHLC 列，缺少: {missing}（请使用含开高低收的行情）")

        raw_sig = _STRATS[strategy](df, **params)
        pos = raw_sig.shift(1).fillna(0)  # 防止未来函数

        ret = df["close"].pct_change().fillna(0)
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
        wins = strat_ret[strat_ret > 0]
        losses = -strat_ret[strat_ret < 0]
        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss = float(losses.mean()) if len(losses) else 0.0
        pl_ratio = float(avg_win / (avg_loss + 1e-12))

        return {
            "strategy": strategy,
            "equity": equity,
            "total_return": float(total_ret),
            "annual_return": float(ann_ret),
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "win_rate": win_rate,
            "profit_loss_ratio": pl_ratio,
            "n_trades": int(trade.sum()),
        }

    @staticmethod
    def walk_forward(df: pd.DataFrame, strategy: str = "sma_cross",
                     train_size: int = 252, test_size: int = 63,
                     step: int = 63, **params) -> list[dict]:
        """滚动窗口样本外验证（反过拟合核心）。返回每段样本外绩效。"""
        results = []
        n = len(df)
        i = train_size
        while i + test_size <= n:
            test = df.iloc[i:i + test_size]
            bt = Backtester()
            try:
                r = bt.run(test, strategy=strategy, **params)
                r["window_start"] = str(test.index[0].date())
                results.append(r)
            except Exception:
                pass
            i += step
        return results
