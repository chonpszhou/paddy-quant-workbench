#!/usr/bin/env python3
"""全宇宙参数寻优：遍历 多标的 × 多策略，walk-forward 样本外排序，找可部署候选。

用法（无需联网，读本地 data/real 落库 parquet）:
  python scripts/optimize_universe.py

输出: data/experiments/universe_opt.csv + 控制台 Top 表，并列出评分≥70 且未过拟合的候选。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.common import load_settings
from src.engine.optimizer import ParameterOptimizer, DEFAULT_SPACES, PASS_SCORE

ROOT = Path(__file__).parent.parent

# (symbol, market) —— 覆盖 A股/港股/美股/数字货币 四大市场
UNIVERSE = [
    # A股
    ("600519", "a"), ("300750", "a"), ("002594", "a"),
    ("600036", "a"), ("601318", "a"), ("000858", "a"),
    # 港股
    ("00700", "hk"), ("03690", "hk"), ("09988", "hk"),
    ("01810", "hk"), ("09618", "hk"), ("09999", "hk"),
    # 美股
    ("AAPL", "us"), ("MSFT", "us"), ("NVDA", "us"), ("TSLA", "us"),
    ("AMZN", "us"), ("GOOGL", "us"), ("META", "us"), ("AMD", "us"),
    ("JPM", "us"), ("COST", "us"),
    # 数字货币（真实数据，样本不足时降级 holdout）
    ("BTCUSDT", "crypto"),
]


def load(symbol: str, market: str) -> pd.DataFrame | None:
    p = ROOT / "data" / "real" / f"{market}_{symbol}_1d.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return None


def main() -> None:
    settings = load_settings()
    opt = ParameterOptimizer(settings)
    rows: list[dict] = []

    for symbol, market in UNIVERSE:
        df = load(symbol, market)
        if df is None or len(df) < 60:
            print(f"SKIP {symbol}({market}) 无数据或不足")
            continue
        for strat in DEFAULT_SPACES:
            try:
                res = opt.optimize(df, strat, top_k=1)
            except Exception as e:  # noqa: BLE001
                print(f"ERR {symbol} {strat}: {e}")
                continue
            if not res:
                continue
            r = res[0]
            oos = r.out_sample
            rows.append({
                "symbol": symbol,
                "market": market,
                "strategy": strat,
                "score": r.score,
                "verdict": r.verdict,
                "params": str(r.params),
                "is_sharpe": round(r.in_sample["sharpe"], 2),
                "oos_sharpe": round(oos.get("sharpe", float("nan")), 2) if oos else None,
                "oos_dd": round(oos.get("max_drawdown", float("nan")), 3) if oos else None,
                "overfit": r.overfit_flag,
                "method": oos.get("method", "") if oos else "",
                "n_bars": len(df),
            })

    rows.sort(key=lambda x: x["score"], reverse=True)
    out = ROOT / "data" / "experiments" / "universe_opt.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    print(f"\n扫描完成: {len(rows)} 组合 | 落库 {out}")
    passed = [r for r in rows if r["score"] >= PASS_SCORE and not r["overfit"]]
    print(f"✅ 可部署(≥{PASS_SCORE} 且未过拟合): {len(passed)} 个")
    for r in passed[:30]:
        print(f"  {r['symbol']:8s} {r['market']:6s} {r['strategy']:14s} "
              f"score={r['score']:.1f} OOS夏普={r['oos_sharpe']} {r['params']}")

    print("\n=== Top 30（按样本外评分）===")
    for r in rows[:30]:
        print(f"  {r['score']:5.1f} {r['verdict']:12s} {r['symbol']:8s} {r['market']:6s} "
              f"{r['strategy']:14s} IS={r['is_sharpe']:.2f} OOS={r['oos_sharpe']} "
              f"[{r['method']}] {r['params']}")


if __name__ == "__main__":
    main()
