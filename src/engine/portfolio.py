"""组合层 (Portfolio / Ensemble) —— 把多个策略/标的腿(leg)合成一个组合。

用途：
- 让 OS 从「单策略单标的」升级到「多策略多标的组合」，分散单一标的/策略的过拟合与黑天鹅。
- 支持等权(equal) 与 波动率目标(vol) 两种权重；默认日频再平衡（简化但透明）。
- 输出聚合权益曲线、夏普、回撤、收益，以及各腿相关性矩阵（用于判断「伪分散」）。

诚实前提：组合不创造 Alpha，只降低单一来源的脆弱性。若各腿高度相关，
分散效果有限——本模块会如实报告相关系数，绝不粉饰。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import Backtester


def _leg_metrics(equity: pd.Series, ret: pd.Series) -> dict:
    n = len(ret)
    total = float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) > 1 else 0.0
    ann = float((1 + total) ** (252 / n) - 1) if n > 0 else 0.0
    dd = (equity - equity.cummax()) / equity.cummax()
    max_dd = float(dd.min())
    sharpe = float(np.sqrt(252) * ret.mean() / (ret.std() + 1e-12))
    return {
        "total_return": total,
        "annual_return": ann,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
    }


class Portfolio:
    def __init__(self, capital: float = 100000):
        self.cap = float(capital)
        self.legs: list[dict] = []

    def add_leg(self, name: str, df: pd.DataFrame, strategy: str, params: dict) -> None:
        """追加一条腿（标的+策略+参数），立即回测并缓存其日收益序列。"""
        bt = Backtester()
        res = bt.run(df, strategy=strategy, **params)
        eq = res["equity"]
        ret = eq.pct_change().fillna(0.0)
        self.legs.append({
            "name": name,
            "strategy": strategy,
            "params": params,
            "equity": eq,
            "ret": ret,
            "metrics": _leg_metrics(eq, ret),
        })

    def compose(self, method: str = "equal") -> dict:
        """合成组合。method: equal(等权) | vol(波动率目标加权)。

        返回 dict：组合权益/指标/各腿指标/相关性矩阵/权重。
        """
        if not self.legs:
            raise ValueError("组合为空，请先 add_leg")

        # 各腿日收益对齐到共同日期（外连接后补 0，缺失日视为无收益）
        rets = pd.concat({leg["name"]: leg["ret"] for leg in self.legs}, axis=1)
        rets = rets.fillna(0.0)

        if method == "equal":
            w = pd.Series(1.0 / len(self.legs), index=rets.columns)
        elif method == "vol":
            vol = rets.std().replace(0, np.nan)
            inv = 1.0 / vol
            w = (inv / inv.sum()).fillna(1.0 / len(self.legs))
        else:
            raise ValueError(f"未知权重方式: {method}，可选 equal/vol")

        port_ret = rets.mul(w, axis=1).sum(axis=1)
        # 真实组合权益（带再平衡）：用组合日收益复利
        port_eq = (1.0 + port_ret).cumprod() * self.cap
        port_metrics = _leg_metrics(port_eq, port_ret)

        corr = rets.corr()

        # 集中/分散诊断：平均两两相关（越高=伪分散风险越大）
        n = len(self.legs)
        avg_corr = float(
            (corr.values[np.triu_indices(n, k=1)].mean()) if n > 1 else 0.0
        )

        return {
            "method": method,
            "weights": {k: float(v) for k, v in w.items()},
            "portfolio_equity": port_eq,
            "portfolio_return": port_ret,
            "metrics": port_metrics,
            "legs": {leg["name"]: leg["metrics"] for leg in self.legs},
            "correlation": corr,
            "avg_pairwise_corr": avg_corr,
            "n_legs": n,
        }

    def to_frame(self, method: str = "equal") -> pd.DataFrame:
        """导出组合 + 各腿权益表（便于落盘 CSV / 画图）。"""
        res = self.compose(method=method)
        cols = {"portfolio": res["portfolio_equity"]}
        for leg in self.legs:
            cols[leg["name"]] = leg["equity"]
        return pd.DataFrame(cols)
