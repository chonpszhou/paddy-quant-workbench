#!/usr/bin/env python3
"""用真实行情（通达信/腾讯自选股等 MCP 拉取的 K线 JSON）跑回测 + 风控评审。

用途：把"连不上 East Money"的市场数据（通过 MCP 连接器拉取）接进本系统的
回测 + 风控引擎，完成「真实数据 → 回测 → 风控报告」的闭环验证。

输入 K 线 JSON 格式（兼容 tdx-connector 输出）：
  {"Rows": [ {"Data":"20241217","Open":...,"High":...,"Low":...,"Close":...,"Volume":...}, ... ]}

用法：
  python scripts/validate_kline.py --kline <kline.json> --preset conservative --market a --symbol 600519
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.common import load_settings
from src.engine.backtest import Backtester
from src.risk.risk_control import RiskConfig, RiskController
from quantos import build_risk_controller, load_preset, print_report, norm_market


def parse_kline_json(path: str) -> pd.DataFrame:
    text = Path(path).read_text(encoding="utf-8")
    # 去掉可能的前导说明行，从第一个 { 开始解析
    start = text.find("{")
    if start < 0:
        raise ValueError("文件里找不到 JSON")
    obj = json.loads(text[start:])
    rows = obj.get("Rows") or obj.get("rows") or []
    if not rows:
        raise ValueError("Rows 为空，疑似无数据（检查 code/setcode/period）")
    recs = []
    for r in rows:
        try:
            recs.append({
                "date": pd.to_datetime(str(r["Data"])),
                "open": float(r.get("Open", 0) or 0),
                "high": float(r.get("High", 0) or 0),
                "low": float(r.get("Low", 0) or 0),
                "close": float(r.get("Close", 0) or 0),
                "volume": float(r.get("Volume", 0) or 0),
            })
        except (KeyError, ValueError, TypeError):
            continue
    df = pd.DataFrame(recs).set_index("date").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    if df.empty:
        raise ValueError("解析后无有效 K 线")
    return df


def main():
    ap = argparse.ArgumentParser(description="真实行情 K线 → 回测 + 风控评审")
    ap.add_argument("--kline", required=True, help="K线 JSON 文件路径")
    ap.add_argument("--preset", default="balanced")
    ap.add_argument("--market", default="a")
    ap.add_argument("--symbol", default="UNKNOWN")
    ap.add_argument("--save", default=None, help="落库 parquet 路径（可选）")
    args = ap.parse_args()

    df = parse_kline_json(args.kline)
    print(f"✅ 解析到 {len(df)} 根 K 线：{df.index[0].date()} ~ {df.index[-1].date()}，"
          f"最新收盘 {df['close'].iloc[-1]:.2f}")

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(args.save)
        print(f"   已落库：{args.save}")

    settings = load_settings()
    preset = load_preset(args.preset)
    risk = build_risk_controller(settings, preset.get("risk_override"))

    bt = Backtester(
        initial_capital=settings["backtest"]["initial_capital"],
        commission=settings["backtest"]["commission"],
    )
    result = bt.run(df, strategy=preset["strategy"], **preset.get("params", {}))
    print_report(result, risk, args.symbol, norm_market(args.market))

    if len(df) >= 400:
        wf = bt.walk_forward(df, preset["strategy"], **preset.get("params", {}))
        if wf:
            sharpe_wf = float(np.mean([w["sharpe"] for w in wf]))
            dd_wf = min([w["max_drawdown"] for w in wf])
            print(f"  🔁 walk-forward 样本外 {len(wf)} 段：平均夏普 {sharpe_wf:.2f} ｜ 最差回撤 {dd_wf*100:.2f}%")
            if sharpe_wf < 0.5:
                print("  ⚠️ 样本外平均夏普偏低，警惕过拟合——勿直接上实盘")


if __name__ == "__main__":
    main()
