"""参数寻优器 (Parameter Optimizer) —— 反过拟合是核心。

设计原则（与整个 OS 一致：不承诺稳定获利，只承诺"严谨地找稳健参数"）：
1. 对每个参数组合，同时算「样本内」(全样本回测) 与「样本外」(walk-forward 滚动窗) 指标。
2. **用样本外指标排序**，而非样本内——样本内好看的参数很可能是过拟合。
3. 显式检测过拟合：若 样本内夏普 / 样本外夏普 > 阈值(OVERFIT_RATIO)，标记为 ⚠️ 可能过拟合 并扣分。
4. 评分 ≥ PASS_SCORE(70) 才视为"可进模拟盘"的候选，再由 PaperBroker 灰度验证。

只有 len(df) >= MIN_BARS_FOR_WF 才用 walk-forward；否则退化为「70/30 单期样本外」，
并在结果里标注 holdout，提醒样本外证据较弱。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from .backtest import Backtester

# —— 阈值常量 ——
MIN_BARS_FOR_WF = 400          # 不足此样本量则降级为单期 holdout
WF_TRAIN, WF_TEST, WF_STEP = 252, 63, 63
OVERFIT_RATIO = 1.8            # 样本内/样本外夏普比超过此值视为可能过拟合
PASS_SCORE = 70                # 可进模拟盘门槛
HOLDOUT_FRAC = 0.30            # 样本不足时的样本外占比


# —— 各策略默认参数空间 ——
DEFAULT_SPACES = {
    "sma_cross": {
        "fast": [3, 5, 8, 10, 15],
        "slow": [20, 30, 50, 60, 120],
    },
    "momentum": {
        "window": [10, 20, 40, 60, 90, 120],
    },
    "mean_reversion": {
        "window": [10, 20, 40],
        "n_std": [1.5, 2.0, 2.5],
    },
}


@dataclass
class OptResult:
    params: dict
    in_sample: dict                  # 全样本回测指标
    out_sample: dict                 # 样本外聚合指标
    score: float
    overfit_flag: bool
    verdict: str
    note: str = ""


def _score(in_s: dict, out_s: dict | None, dd_circuit: float) -> tuple[float, bool, str]:
    """按样本外为主评分；返回 (score, overfit_flag, verdict)。"""
    score = 0.0
    overfit = False

    is_sharpe = in_s.get("sharpe", float("nan"))
    oos_sharpe = out_s.get("sharpe", float("nan")) if out_s else float("nan")
    oos_dd = out_s.get("max_drawdown", float("nan")) if out_s else float("nan")
    oos_win = out_s.get("win_rate", float("nan")) if out_s else float("nan")

    # 过拟合检测（仅当两侧夏普都有效，且样本外为正）
    if not np.isnan(is_sharpe) and not np.isnan(oos_sharpe) and oos_sharpe > 0:
        if is_sharpe / oos_sharpe > OVERFIT_RATIO:
            overfit = True

    # 样本外夏普（核心，上限 55）
    if not np.isnan(oos_sharpe):
        score += max(0.0, min(55.0, oos_sharpe * 22))
    # 样本外回撤未超熔断（+20）
    if not np.isnan(oos_dd) and oos_dd > -dd_circuit:
        score += 20.0
    # 样本内夏普（一致性检查，上限 15，仅防纯样本内好看，不奖励过拟合）
    if not np.isnan(is_sharpe):
        score += max(0.0, min(15.0, is_sharpe * 7))
    # 样本外胜率（上限 10，胜率>0.5 起给分）
    if not np.isnan(oos_win):
        score += max(0.0, min(10.0, (oos_win - 0.4) * 25))

    score = round(min(100.0, score), 1)
    if overfit:
        verdict = "❌ 可能过拟合"
    elif score >= PASS_SCORE:
        verdict = "✅ 可进模拟盘"
    elif score >= 50:
        verdict = "⚠️ 模拟盘观察"
    else:
        verdict = "❌ 暂不采用"
    return score, overfit, verdict


class ParameterOptimizer:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or {}
        self.dd_circuit = self.settings.get("risk", {}).get("max_drawdown_circuit_pct", 0.20)

    def _out_of_sample(self, df, strategy: str, params: dict) -> dict | None:
        """返回样本外聚合指标；样本不足则降级 holdout。"""
        n = len(df)
        bt = Backtester()
        if n >= MIN_BARS_FOR_WF:
            windows = bt.walk_forward(df, strategy, WF_TRAIN, WF_TEST, WF_STEP, **params)
            if windows:
                return {
                    "method": "walk_forward",
                    "n_windows": len(windows),
                    "sharpe": float(np.mean([w["sharpe"] for w in windows])),
                    "max_drawdown": min([w["max_drawdown"] for w in windows]),
                    "win_rate": float(np.mean([w["win_rate"] for w in windows])),
                    "total_return": float(np.mean([w["total_return"] for w in windows])),
                    "profit_loss_ratio": float(np.mean([w["profit_loss_ratio"] for w in windows])),
                }
        # 降级 holdout：最后 HOLDOUT_FRAC 作为样本外
        k = max(30, int(n * HOLDOUT_FRAC))
        test = df.iloc[-k:]
        if len(test) < 20:
            return None
        r = bt.run(test, strategy=strategy, **params)
        r["method"] = "holdout"
        r["n_windows"] = 1
        return r

    def optimize(self, df, strategy: str = "sma_cross",
                 space: dict | None = None, top_k: int = 5) -> list[OptResult]:
        space = space or DEFAULT_SPACES.get(strategy)
        if space is None:
            raise ValueError(f"策略 {strategy} 无默认参数空间，请显式传入 space")

        keys = list(space.keys())
        combos = [dict(zip(keys, vals)) for vals in itertools.product(*(space[k] for k in keys))]
        # sma_cross 必须 fast < slow
        if strategy == "sma_cross":
            combos = [c for c in combos if c["fast"] < c["slow"]]

        bt = Backtester()
        results: list[OptResult] = []
        for params in combos:
            try:
                in_s = bt.run(df, strategy=strategy, **params)
                out_s = self._out_of_sample(df, strategy, params)
            except Exception:
                continue
            if out_s is None:
                # 样本外证据不足，给最低分并标注
                res = OptResult(params=params, in_sample=in_s, out_sample={},
                                score=0.0, overfit_flag=False,
                                verdict="❌ 样本外证据不足", note="数据不足，无法做样本外验证")
                results.append(res)
                continue
            score, overfit, verdict = _score(in_s, out_s, self.dd_circuit)
            note = ""
            if overfit:
                note = f"样本内夏普 {in_s['sharpe']:.2f} / 样本外 {out_s['sharpe']:.2f} 差距过大"
            if out_s.get("method") == "holdout":
                note = (note + "；" if note else "") + "样本外仅单期 holdout，证据较弱"
            results.append(OptResult(
                params=params, in_sample=in_s, out_sample=out_s,
                score=score, overfit_flag=overfit, verdict=verdict, note=note,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def print_results(results: list[OptResult], strategy: str, symbol: str = "") -> None:
        print(f"\n{'=' * 78}")
        print(f"参数寻优 · 策略={strategy}  标的={symbol or '—'}  (按样本外评分排序)")
        print(f"{'=' * 78}")
        for i, r in enumerate(results, 1):
            p = "  ".join(f"{k}={v}" for k, v in r.params.items())
            oos = r.out_sample
            oos_str = (f"OOS夏普={oos.get('sharpe', float('nan')):.2f} "
                       f"OOS回撤={oos.get('max_drawdown', float('nan'))*100:.1f}% "
                       f"[{oos.get('method', '?')}]") if oos else "OOS=无"
            print(f"\n#{i} 评分={r.score:5.1f}  {r.verdict}")
            print(f"    参数: {p}")
            print(f"    IS夏普={r.in_sample['sharpe']:.2f}  IS回撤={r.in_sample['max_drawdown']*100:.1f}%  "
                  f"IS收益={r.in_sample['total_return']*100:.1f}%")
            print(f"    {oos_str}")
            if r.note:
                print(f"    ⚠️ {r.note}")
