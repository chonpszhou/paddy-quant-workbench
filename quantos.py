#!/usr/bin/env python3
"""量化交易操作系统 · 小白向导 (QuantOS CLI)

面向金融小白的统一入口：
  python quantos.py init      交互式问卷 → 生成 config/user_profile.yaml
  python quantos.py backtest  跑策略回测 + 中文风控报告（模拟盘，无实盘）
  python quantos.py check     校验当前配置与风控是否自洽
  python quantos.py selftest  用合成数据自检模块（无需联网/无需装 akshare）

诚实前提：本系统不承诺"稳定获利"。它只保证——任何策略在实盘前
必须过回测、过样本外、且强制套用风控最小集。盈亏由市场决定。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.common import load_settings
from src.data.unified import DataHub
from src.engine.backtest import Backtester
from src.risk.risk_control import RiskConfig, RiskController

ROOT = Path(__file__).parent
PROFILE_PATH = ROOT / "config" / "user_profile.yaml"

# 市场代码别名：小白输入的短码(a/h/u/c) 与 DataHub 规范码(a/hk/us/crypto) 互认，
# 避免新手敲 --market u 直接报错。
MARKET_ALIAS = {
    "a": "a", "cn": "a", "h": "hk", "hk": "hk",
    "u": "us", "us": "us", "c": "crypto", "crypto": "crypto",
}


def norm_market(m: str | None) -> str:
    if not m:
        return "us"
    return MARKET_ALIAS.get(m.strip().lower(), m.strip().lower())


# ---------------------------------------------------------------------------
# 配置与风控装配
# ---------------------------------------------------------------------------
def build_risk_controller(settings: dict, risk_override: dict | None = None) -> RiskController:
    base = settings.get("risk", {})
    if risk_override:
        base = {**base, **risk_override}
    cfg = RiskConfig(**{k: v for k, v in base.items() if k in RiskConfig.__dataclass_fields__})
    equity = settings.get("backtest", {}).get("initial_capital", 100000)
    return RiskController(cfg, total_equity=float(equity))


def load_preset(name: str) -> dict:
    p = ROOT / "config" / "strategies" / f"{name}.yaml"
    if not p.exists():
        raise SystemExit(f"预设不存在: {name}，可选 conservative/balanced/aggressive")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 中文报告
# ---------------------------------------------------------------------------
def fmt_pct(x: float) -> str:
    return f"{x*100:.2f}%"


def print_report(result: dict, risk: RiskController, symbol: str, market: str) -> None:
    eq = result["equity"]
    print("\n" + "=" * 52)
    print(f"  📊 {symbol}（{market}）回测报告 · 模拟盘")
    print("=" * 52)
    print(f"  策略           : {result['strategy']}")
    print(f"  总收益率       : {fmt_pct(result['total_return'])}")
    print(f"  年化收益       : {fmt_pct(result['annual_return'])}")
    print(f"  最大回撤       : {fmt_pct(result['max_drawdown'])}")
    print(f"  夏普比率       : {result['sharpe']:.2f}")
    print(f"  胜率           : {fmt_pct(result['win_rate'])}")
    print(f"  盈亏比         : {result['profit_loss_ratio']:.2f}")
    print(f"  交易次数       : {result['n_trades']}")
    print("-" * 52)
    print("  🛡️ 强制风控最小集（实盘前硬门槛）")
    s = risk.summary()
    print(f"  单笔仓位上限   : {fmt_pct(s['max_single_position_pct'])}")
    print(f"  单策略仓位上限 : {fmt_pct(s['max_strategy_position_pct'])}")
    print(f"  总开仓上限     : {fmt_pct(s['max_total_position_pct'])}")
    print(f"  单笔止损       : {fmt_pct(s['stop_loss_pct'])}")
    print(f"  单日熔断       : 亏损 {fmt_pct(s['daily_loss_circuit_pct'])} 停手")
    print(f"  总回撤熔断     : {fmt_pct(s['max_drawdown_circuit_pct'])} 全面暂停")
    print("=" * 52)
    # 极简结论
    verdict = []
    if result["max_drawdown"] < -s["max_drawdown_circuit_pct"]:
        verdict.append("⚠️ 回测最大回撤已超过熔断线，实盘必须先降仓位或换参数")
    if result["sharpe"] < 1.0:
        verdict.append("⚠️ 夏普<1，风险调整收益偏弱，建议先模拟盘打磨")
    else:
        verdict.append("✅ 夏普≥1，样本内表现可接受，但仍需 walk-forward 样本外验证")
    for v in verdict:
        print("  " + v)
    print()


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
def cmd_init(args) -> None:
    print("\n🤖 量化交易操作系统 · 小白开户向导（仅生成配置，不碰实盘）\n")
    name = input("  你的称呼（随便写）: ").strip() or "小白"
    print("\n  能接受的最大回撤是多少？(输入数字，如 10 表示 10%)")
    dd = float(input("  最大回撤上限 %: ").strip() or "20")
    print("\n  想做哪些市场？(输入字母组合 a/h/u/c，默认全要 ahu) ")
    print("    a=A股  h=港股  u=美股  c=数字货币")
    mk = input("  市场: ").strip().lower() or "ahuc"
    markets = [MARKET_ALIAS[m] for m in ["a", "h", "u", "c"] if m in mk]
    capital = float(input("\n  计划投入总金额(元，模拟也可填): ").strip() or "100000")

    profile = {
        "user": name,
        "markets": markets,
        "capital": capital,
        "risk_appetite": "conservative" if dd <= 12 else ("balanced" if dd <= 20 else "aggressive"),
        "max_drawdown_pct": dd / 100,
        "recommended_preset": "conservative" if dd <= 12 else ("balanced" if dd <= 20 else "aggressive"),
        "phase": "paper",  # 永远从模拟盘开始
    }
    PROFILE_PATH.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    print(f"\n✅ 已生成 {PROFILE_PATH}")
    print(f"   推荐预设: {profile['recommended_preset']} ｜ 阶段: 模拟盘")
    print("   下一步: python quantos.py backtest --preset "
          f"{profile['recommended_preset']} --symbol AAPL --market us")


def cmd_backtest(args) -> None:
    settings = load_settings()
    preset = load_preset(args.preset)
    risk = build_risk_controller(settings, preset.get("risk_override"))

    if args.symbol and args.market:
        market = norm_market(args.market)
        hub = DataHub(settings)
        df = hub.get(args.symbol, market, args.timeframe, args.limit)
        if df is None or df.empty:
            raise SystemExit("拉不到数据（检查代码/网络/数据源）")
    else:
        # 无标的时用合成数据演示流程
        print("⚠️ 未给 --symbol，使用合成数据演示回测流程")
        rng = np.random.default_rng(42)
        ret = rng.normal(0.0005, 0.02, 600)
        close = pd.Series(100 * (1 + pd.Series(ret)).cumprod())
        df = pd.DataFrame({"close": close})
        market = "demo"

    bt = Backtester(
        initial_capital=settings["backtest"]["initial_capital"],
        commission=settings["backtest"]["commission"],
    )
    result = bt.run(df, strategy=preset["strategy"], **preset.get("params", {}))
    print_report(result, risk, args.symbol or "SYNTH", market)

    # walk-forward 样本外（若有足够长度）
    if len(df) >= 400:
        wf = bt.walk_forward(df, preset["strategy"], **preset.get("params", {}))
        if wf:
            sharpe_wf = np.mean([w["sharpe"] for w in wf])
            dd_wf = min([w["max_drawdown"] for w in wf])
            print(f"  🔁 walk-forward 样本外 {len(wf)} 段：平均夏普 {sharpe_wf:.2f} ｜ 最差回撤 {fmt_pct(dd_wf)}")
            if sharpe_wf < 0.5:
                print("  ⚠️ 样本外平均夏普偏低，警惕过拟合——勿直接上实盘")


def cmd_check(args) -> None:
    settings = load_settings()
    risk = build_risk_controller(settings)
    s = risk.summary()
    ok = True
    msgs = []
    if s["max_total_position_pct"] < s["max_single_position_pct"]:
        ok = False
        msgs.append("总开仓上限 < 单笔上限，逻辑矛盾")
    if s["stop_loss_pct"] <= 0:
        ok = False
        msgs.append("止损必须为正数")
    print("✅ 风控配置自洽" if ok else "❌ 发现问题:")
    for m in msgs:
        print("  - " + m)
    print(json.dumps(s, indent=2, ensure_ascii=False))


def cmd_selftest(args) -> None:
    """无需联网/无需 akshare，验证风控与回测模块可用。"""
    settings = load_settings()
    risk = build_risk_controller(settings)
    # 风控单测
    assert risk.proposed_size_ok("X", risk.max_position_value() * 0.9)[0]
    assert not risk.proposed_size_ok("X", risk.max_position_value() * 2.0)[0]
    from src.risk.risk_control import PositionState
    pos = PositionState("ETH", 1.0, 2000.0, current_price=1850.0, atr=80.0,
                        highest_since_entry=2050.0)
    stop = risk.compute_stop(pos)
    assert risk.check_exit(pos)[0], "应触发止损"
    # 回测单测（合成数据）
    rng = np.random.default_rng(0)
    close = pd.Series(100 * (1 + pd.Series(rng.normal(0.0004, 0.018, 500))).cumprod())
    df = pd.DataFrame({"close": close})
    bt = Backtester()
    r = bt.run(df, "sma_cross")
    assert "profit_loss_ratio" in r and "sharpe" in r
    print("✅ selftest 通过：风控 + 回测模块正常工作")
    print_report(r, risk, "SELFTEST", "demo")


def main():
    ap = argparse.ArgumentParser(description="量化交易操作系统 · 小白向导")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("init", help="交互式生成用户配置").set_defaults(func=cmd_init)
    b = sub.add_parser("backtest", help="跑回测 + 风控报告")
    b.add_argument("--preset", default="balanced")
    b.add_argument("--symbol", default=None)
    b.add_argument("--market", default=None)
    b.add_argument("--timeframe", default="1d")
    b.add_argument("--limit", type=int, default=400)
    b.set_defaults(func=cmd_backtest)
    sub.add_parser("check", help="校验风控配置").set_defaults(func=cmd_check)
    sub.add_parser("selftest", help="模块自检").set_defaults(func=cmd_selftest)
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
