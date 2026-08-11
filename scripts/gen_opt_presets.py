#!/usr/bin/env python3
"""从 universe_opt.csv 中为「评分≥70 且未过拟合」的候选生成可部署策略预设。

用法:
  python scripts/gen_opt_presets.py

输出: config/strategies/<symbol>_<market>_<strategy>_opt.yaml
"""
from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
CSV = ROOT / "data" / "experiments" / "universe_opt.csv"
OUT_DIR = ROOT / "config" / "strategies"


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"找不到 {CSV}，请先跑 optimize_universe.py")
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    made = 0
    for r in rows:
        # 仅生成「可进模拟盘」(verdict 含该词，即 score≥70 且未过拟合)
        if "可进模拟盘" not in r["verdict"]:
            continue
        symbol, market, strategy = r["symbol"], r["market"], r["strategy"]
        try:
            params = ast.literal_eval(r["params"])
        except Exception:
            params = {}
        name = f"{symbol}_{market}_{strategy}_opt"
        preset = {
            "name": f"寻优·{symbol}({market})·{strategy}",
            "profile": "optimized",
            "strategy": strategy,
            "params": params,
            "markets": [market],
            "instruments": ["spot", "etf"],
            "risk_override": {
                "max_single_position_pct": 0.02,
                "max_strategy_position_pct": 0.30,
                "max_total_position_pct": 0.50,
                "stop_loss_pct": 0.03,
                "daily_loss_circuit_pct": 0.05,
                "max_drawdown_circuit_pct": 0.20,
            },
            "note": (f"参数寻优自动生成（评分 {r['score']}，样本外夏普 {r['oos_sharpe']}，"
                     f"{r['method']}）。须先经 PaperBroker 模拟盘灰度验证，且仅小资金实盘。"),
        }
        out = OUT_DIR / f"{name}.yaml"
        out.write_text(yaml.safe_dump(preset, allow_unicode=True), encoding="utf-8")
        print(f"  ✅ {out.name}  score={r['score']} OOS夏普={r['oos_sharpe']} {params}")
        made += 1
    print(f"\n共生成 {made} 个可部署预设 → {OUT_DIR}")


if __name__ == "__main__":
    main()
