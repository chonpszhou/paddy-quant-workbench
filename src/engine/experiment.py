"""实验运行器 (Experiment Runner)。

把"回测 + 样本外 + 风控"封装成可批量、可复现的实验：
- 一次扫 多个标的 × 多个预设，产出横向对比表。
- 自动算"可上实盘评分"，帮小白在众多回测结果里挑出真正稳健的组合。
- 与 PaperBroker 配合：评分达标的组合才允许进模拟盘，模拟盘达标才允许实盘。

反过拟合是核心：任何只靠样本内夏普"好看"的策略，都会被 walk-forward 样本外
与"回撤是否超熔断"两道关筛掉。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .backtest import Backtester
from ..engine.instruments import InstrumentRegistry

_ROOT = Path(__file__).resolve().parents[2]


def load_preset(name: str) -> dict:
    p = _ROOT / "config" / "strategies" / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"预设不存在: {name}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


class ExperimentRunner:
    def __init__(self, settings: dict | None = None, registry: InstrumentRegistry | None = None):
        self.settings = settings or {}
        self.registry = registry or InstrumentRegistry()
        self.records: list[dict] = []

    def run_one(self, symbol: str, market: str, df: pd.DataFrame,
                preset_name: str) -> dict:
        preset = load_preset(preset_name)
        bt = Backtester(
            initial_capital=self.settings.get("backtest", {}).get("initial_capital", 100000),
            commission=self.settings.get("backtest", {}).get("commission", 0.001),
        )
        res = bt.run(df, strategy=preset["strategy"], **preset.get("params", {}))

        wf = bt.walk_forward(df, preset["strategy"], **preset.get("params", {})) if len(df) >= 400 else []
        wf_sharpe = float(np.mean([w["sharpe"] for w in wf])) if wf else float("nan")
        wf_dd = min([w["max_drawdown"] for w in wf]) if wf else float("nan")
        wf_win = float(np.mean([w["win_rate"] for w in wf])) if wf else float("nan")

        dd_circuit = preset.get("risk_override", {}).get(
            "max_drawdown_circuit_pct",
            self.settings.get("risk", {}).get("max_drawdown_circuit_pct", 0.20),
        )

        # —— 可上实盘评分 (0-100) ——
        score = 0.0
        score += max(0, min(40, res["sharpe"] * 20))           # 样本内夏普，上限40
        if not np.isnan(wf_sharpe):
            score += max(0, min(30, wf_sharpe * 15))           # 样本外夏普，上限30
        if res["max_drawdown"] > -dd_circuit:
            score += 15                                          # 回撤未超熔断 +15
        if not np.isnan(wf_dd) and wf_dd > -dd_circuit:
            score += 15                                          # 样本外回撤未超熔断 +15
        score = round(min(100, score), 1)

        verdict = "✅ 可进模拟盘" if score >= 70 else ("⚠️ 模拟盘观察" if score >= 50 else "❌ 暂不采用")

        rec = {
            "symbol": symbol, "market": market, "preset": preset_name,
            "strategy": preset["strategy"],
            "total_return": round(res["total_return"] * 100, 2),
            "sharpe": round(res["sharpe"], 2),
            "max_dd": round(res["max_drawdown"] * 100, 2),
            "win_rate": round(res["win_rate"] * 100, 2),
            "pl_ratio": round(res["profit_loss_ratio"], 2),
            "wf_sharpe": round(wf_sharpe, 2) if not np.isnan(wf_sharpe) else None,
            "wf_dd": round(wf_dd * 100, 2) if not np.isnan(wf_dd) else None,
            "score": score, "verdict": verdict,
        }
        self.records.append(rec)
        return rec

    def run(self, jobs: list[tuple[str, str, pd.DataFrame, str]]) -> pd.DataFrame:
        """jobs: [(symbol, market, df, preset_name), ...]"""
        for sym, mkt, df, pre in jobs:
            if df is None or df.empty:
                continue
            try:
                self.run_one(sym, mkt, df, pre)
            except Exception as e:  # 单任务失败不影响整体
                self.records.append({"symbol": sym, "market": mkt, "preset": pre,
                                     "error": str(e)})
        df = pd.DataFrame(self.records)
        if not df.empty and "score" in df:
            df = df.sort_values("score", ascending=False).reset_index(drop=True)
        return df

    @staticmethod
    def print_table(df: pd.DataFrame) -> None:
        if df is None or df.empty:
            print("（无实验结果）")
            return
        cols = [c for c in ["symbol", "market", "preset", "strategy", "total_return",
                           "sharpe", "max_dd", "win_rate", "pl_ratio",
                           "wf_sharpe", "wf_dd", "score", "verdict"] if c in df.columns]
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df[cols].to_string(index=False))
