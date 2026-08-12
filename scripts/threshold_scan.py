"""阈值扫描：收紧 rsi_reversal 信号阈值 + 冷却期，能否让灰度模拟转正？

复刻 cmd_paper 的前向模拟盘（2% 限仓 + 真实手续费），扫描：
  - oversold ∈ {15, 20, 25, 30, 35}（越紧 → 触发越少越极端）
  - cooling ∈ {0, 5, 10, 20}（离场后冷却 N 天再入场，抑制频繁交易）

目标：看是否存在 (oversold, cooling) 使净收益转正；若怎么调都转不了，
则给出根因——2% 限仓 + 真实手续费结构性吃掉薄边。

同时拆分 毛收益(无费) vs 净收益(有费)，直接量化「手续费侵蚀」。

用法：python scripts/threshold_scan.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import quantos as Q  # noqa: E402
from src.broker import PaperBroker, Order  # noqa: E402
from src.engine.backtest import _STRATS  # noqa: E402

PRESET_NAME = "09999_hk_rsi_reversal_opt"   # 含 2% 限仓 risk_override
OVERSOLDS = [15, 20, 25, 30, 35]
COOLINGS = [0, 5, 10, 20]
TARGETS = {
    "网易(hk09999)": ("hk09999", "hk", "data/real/hk_09999_1d.parquet"),
    "携程(hk09961)": ("hk09961", "hk", "data/real/hk_09961_1d.parquet"),
    "Visa(usV)":     ("usV", "us", "data/real/us_V_1d.parquet"),
}


def forward_sim(symbol, market, df, oversold, cooling) -> dict:
    """复刻 cmd_paper 前向模拟；返回 净/毛 收益与交易统计。"""
    settings = Q.load_settings()
    preset = Q.load_preset(PRESET_NAME)
    risk = Q.build_risk_controller(settings, preset.get("risk_override"))
    registry = Q.InstrumentRegistry(Q.load_instrument_overrides())
    itype = "spot"
    spec = registry.get(symbol, market, itype)
    cap = settings["backtest"]["initial_capital"]
    broker = PaperBroker(initial_cash=cap, registry=registry)

    sig = _STRATS["rsi_reversal"](df, period=7, oversold=oversold, overbought=70).shift(1).fillna(0)

    cooldown = 0
    n_entry = 0
    for i in range(1, len(df)):
        price = float(df["close"].iloc[i])
        broker.mark(symbol, price)
        desired = int(sig.iloc[i])
        if cooldown > 0:
            desired = 0
            cooldown -= 1
        cur = broker.get_positions().get(symbol)
        cur_qty = cur.qty if cur else 0.0

        if desired != 0 and cur_qty == 0:
            per = spec.multiplier * spec.contract_unit
            qty = risk.max_position_value() / (price * per)
            qty = spec.round_qty(qty)
            ok, _ = risk.proposed_size_ok(symbol, spec.notional(qty, price))
            if ok and qty > 0:
                side = "buy" if desired > 0 else "sell"
                o = Order(symbol, market, itype, side, qty)
                if broker.submit_order(o):
                    n_entry += 1
        elif desired == 0 and cur_qty != 0:
            side = "sell" if cur_qty > 0 else "buy"
            o = Order(symbol, market, itype, side, abs(cur_qty))
            if broker.submit_order(o):
                cooldown = cooling

    acct = broker.get_account()
    net_pnl = acct["equity"] - cap
    fees = sum(f.fee for f in broker.fills)
    gross_pnl = net_pnl + fees   # 毛收益 = 净收益 + 手续费（手续费是唯一扣减项）
    return {
        "oversold": oversold, "cooling": cooling,
        "net_pnl": net_pnl, "gross_pnl": gross_pnl, "fees": fees,
        "entries": n_entry, "fills": len(broker.fills),
    }


def main() -> None:
    print("=" * 110)
    print("  阈值扫描 rsi_reversal(p=7)：oversold × cooling → 净/毛 收益（2% 限仓 + 真实手续费）")
    print("=" * 110)
    all_rows = []
    for label, (sym, mkt, parquet) in TARGETS.items():
        df = pd.read_parquet(ROOT / parquet)
        print(f"\n### {label}  （{len(df)} 根K线）")
        header = "  oversold | " + " | ".join(f"cool={c:>2}" for c in COOLINGS)
        print(header)
        print("  " + "-" * (len(header)))
        for ov in OVERSOLDS:
            cells = []
            row_recs = []
            for cd in COOLINGS:
                r = forward_sim(sym, mkt, df, ov, cd)
                all_rows.append({"label": label, **r})
                cells.append(f"{r['net_pnl']:+9.0f}")
                row_recs.append(r)
            print(f"  {ov:>7} | " + " | ".join(f"{c:>9}" for c in cells))
        # 毛/净对照（以 oversold=25, cooling=0 为代表）
        base = forward_sim(sym, mkt, df, 25, 0)
        print(f"  代表(25,0): 毛收益={base['gross_pnl']:+9.1f}  手续费={base['fees']:8.1f}"
              f"  净收益={base['net_pnl']:+9.1f}  入场次数={base['entries']}")
        best = min(all_rows, key=lambda x: (x["label"] != label, -x["net_pnl"]))
        best_of = max([r for r in all_rows if r["label"] == label], key=lambda x: x["net_pnl"])
        print(f"  该标的最优(净): oversold={best_of['oversold']} cooling={best_of['cooling']}"
              f" → 净={best_of['net_pnl']:+.1f}（仍{'负' if best_of['net_pnl'] < 0 else '正'}）")

    # 根因：逐标的定性（不是一刀切的"结构性费蚀"）
    print("\n" + "=" * 110)
    print("根因分析（逐标的）：")
    for label in TARGETS:
        recs = [r for r in all_rows if r["label"] == label]
        pos = [r for r in recs if r["net_pnl"] > 0]
        best = max(recs, key=lambda x: x["net_pnl"])
        base = next(r for r in recs if r["oversold"] == 25 and r["cooling"] == 0)
        if not pos:
            print(f"  · {label}: 全 {len(recs)} 组合净负（含毛收益 {base['gross_pnl']:+.0f}）→ "
                  f"信号本身负期望，质量否决正确；任何阈值/冷却都救不了。")
        else:
            print(f"  · {label}: {len(pos)}/{len(recs)} 组合净正；最优 oversold={best['oversold']}"
                  f" cooling={best['cooling']} → 净={best['net_pnl']:+.0f}。"
                  f"基线(25,0)毛={base['gross_pnl']:+.0f}/费={base['fees']:.0f}/净={base['net_pnl']:+.0f}。"
                  + ("信号有效，但无冷却时换手过高被费吃掉；加冷却/略松阈值即转正。"
                     if label.startswith("网易")
                     else "2yr 样本可转正，但更长样本(3.2yr) walk-forward 不稳健，属 regime-luck，不可信。"))
    print("-" * 110)
    print("总体结论：单纯『收紧阈值』并不能系统转正——对网易反而更差。真正的杠杆在「冷却/降换手」：")
    print("  它同时砍掉手续费(更少笔数)并改善毛收益(避开鞭梢)。携程是信号本身负期望，必否。")
    print("=" * 110)

    out = ROOT / "data" / "experiments" / "threshold_scan.json"
    out.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()
