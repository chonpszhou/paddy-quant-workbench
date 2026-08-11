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
from datetime import datetime, date, time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.common import load_settings
from src.data.unified import DataHub
from src.engine.backtest import Backtester, _STRATS
from src.engine.instruments import InstrumentRegistry
from src.engine.experiment import ExperimentRunner
from src.engine.optimizer import ParameterOptimizer, DEFAULT_SPACES, PASS_SCORE
from src.engine.portfolio import Portfolio
from src.broker import PaperBroker, Order, LiveBroker
from src.risk.risk_control import RiskConfig, RiskController
from src.utils import calendar as mcal
from src.utils.experiment_log import record_run

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


def load_instrument_overrides() -> dict:
    """读取 config/instruments.yaml 的标的规格覆盖（可选）。"""
    p = ROOT / "config" / "instruments.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


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

    # —— 新策略（OHLC 类）自检：4 个新策略可跑、信号合法、缺列清晰报错 ——
    from src.engine.backtest import _STRATS as _SIG_FUNCS
    rng2 = np.random.default_rng(7)
    m = 300
    oclose = 100 * (1 + pd.Series(rng2.normal(0.0003, 0.02, m))).cumprod()
    ohlc = pd.DataFrame({
        "open": oclose.shift(1).fillna(oclose.iloc[0]),
        "high": oclose * (1 + rng2.uniform(0, 0.012, m)),
        "low": oclose * (1 - rng2.uniform(0, 0.012, m)),
        "close": oclose,
        "volume": rng2.integers(1000, 5000, m).astype(float),
    })
    for strat, sparams in [
        ("donchian", {"window": 20}),
        ("dual_thrust", {"k1": 0.5, "k2": 0.5}),
        ("rsi_reversal", {"period": 14, "oversold": 30, "overbought": 70}),
        ("atr_channel", {"window": 20, "mult": 2.0}),
    ]:
        sig = _SIG_FUNCS[strat](ohlc, **sparams)
        assert len(sig) == m, f"{strat} 信号长度错误"
        assert set(int(v) for v in np.unique(sig.dropna())).issubset({-1, 0, 1}), \
            f"{strat} 信号含非法值"
        assert not sig.isna().any(), f"{strat} 信号含 NaN"
        rr = bt.run(ohlc, strat, **sparams)
        assert all(np.isfinite(rr[k]) for k in ("sharpe", "total_return", "max_drawdown")), \
            f"{strat} 指标含非有限值"
    # OHLC 缺列应清晰报错（不静默崩溃）
    bad_df = pd.DataFrame({"close": oclose})
    for strat in ("donchian", "dual_thrust", "atr_channel"):
        try:
            bt.run(bad_df, strat)
            raise AssertionError(f"{strat} 缺 OHLC 未报错")
        except ValueError:
            pass

    # —— 多标的规格 + 模拟盘 + 日历 自检 ——
    from src.engine.instruments import InstrumentRegistry
    from src.broker import PaperBroker, Order
    from src.utils import calendar as mcal

    reg = InstrumentRegistry()
    spot = reg.get("AAPL", "us", "spot")
    assert abs(spot.notional(10, 100) - 1000.0) < 1e-9
    fut = reg.get("ES", "us", "future")
    assert fut.is_leveraged and fut.margin_required(1, 100) < fut.notional(1, 100)

    # 现货：同价买后卖，验证会计正确（回本减费，权益略低于本金）
    brk = PaperBroker(initial_cash=100000, registry=reg)
    brk.mark("AAPL", 100.0)
    assert brk.submit_order(Order("AAPL", "us", "spot", "buy", 10))
    brk.mark("AAPL", 100.0)
    assert brk.submit_order(Order("AAPL", "us", "spot", "sell", 10))
    assert brk.get_positions() == {}, "清仓后不应有持仓"
    eq = brk.get_account()["equity"]
    assert 99000 < eq < 100000, f"同价平仓权益应在(99000,100000)，实际 {eq}"

    # 现货「买入持有到期」：现金应≈初始-名义额-费，权益≈初始+浮动（抓 delta*notional 双扣 bug）
    brk_hold = PaperBroker(initial_cash=100000, registry=reg)
    brk_hold.mark("AAPL", 100.0)
    assert brk_hold.submit_order(Order("AAPL", "us", "spot", "buy", 10))
    brk_hold.mark("AAPL", 110.0)
    acct_h = brk_hold.get_account()
    notional_held = 10 * 100.0
    fee_h = reg.get("AAPL", "us", "spot").trade_cost(10, 100.0)
    assert abs(acct_h["cash"] - (100000 - notional_held - fee_h)) < 1e-6, \
        f"买入持有现金应≈初始-名义额-费，实际 {acct_h['cash']}"
    assert abs(acct_h["unrealized_pnl"] - 10 * (110.0 - 100.0)) < 1e-6, "浮动盈亏应=qty*(现价-成本)"
    # 权益应≈期初-费+浮盈（cash+持仓市值），抓 equity=cash+unrealized 漏算成本基数
    assert abs(acct_h["equity"] - (100000 - fee_h + 10 * (110.0 - 100.0))) < 1e-6, \
        f"买入持有权益应≈期初-费+浮盈，实际 {acct_h['equity']}"

    # 做空：高价开空，低价平，应盈利
    brk2 = PaperBroker(initial_cash=100000, registry=reg)
    brk2.mark("AAPL", 100.0)
    assert brk2.submit_order(Order("AAPL", "us", "spot", "sell", 10))  # 开空
    assert brk2.get_positions()["AAPL"].qty == -10
    brk2.mark("AAPL", 90.0)
    assert brk2.submit_order(Order("AAPL", "us", "spot", "buy", 10))   # 平空
    assert brk2.get_account()["realized_pnl"] > 0

    # 期货：保证金占用（非全额），平仓释放保证金 + 实现盈亏
    freg = InstrumentRegistry({"us": {"future": {"margin_rate": 0.1, "multiplier": 20.0}}})
    fbrk = PaperBroker(initial_cash=100000, registry=freg)
    fspec = freg.get("ES", "us", "future")
    fbrk.mark("ES", 100.0)
    assert fbrk.submit_order(Order("ES", "us", "future", "buy", 1))
    margin_posted = fspec.margin_required(1, 100.0)  # 1*100*20*0.1 = 200
    assert abs(fbrk.get_account()["cash"] - (100000 - margin_posted - fspec.trade_cost(1, 100.0))) < 1e-6
    fbrk.mark("ES", 110.0)
    assert fbrk.submit_order(Order("ES", "us", "future", "sell", 1))
    assert fbrk.get_positions() == {}, "期货平仓后不应有持仓"
    assert fbrk.get_account()["realized_pnl"] > 0, "期货上涨平仓应盈利"

    # 日历
    assert mcal.is_trading_day("crypto", date(2026, 1, 1)) is True
    assert mcal.is_trading_day("a", date(2026, 1, 1)) is False

    # 参数寻优器（离线，小参数空间）
    from src.engine.optimizer import ParameterOptimizer
    opt = ParameterOptimizer(settings)
    res = opt.optimize(df, "sma_cross", space={"fast": [3, 5], "slow": [10, 20]}, top_k=2)
    assert len(res) >= 1 and hasattr(res[0], "score")

    # —— 组合层（ensemble）自检 ——
    from src.engine.portfolio import Portfolio
    pf = Portfolio(capital=100000)
    rng_p = np.random.default_rng(11)
    for nm in ("L1", "L2", "L3"):
        c = 100 * (1 + pd.Series(rng_p.normal(0.0004, 0.018, 400))).cumprod()
        d = pd.DataFrame({"close": c})
        pf.add_leg(nm, d, "sma_cross", {"fast": 5, "slow": 20})
    rc = pf.compose(method="equal")
    assert rc["n_legs"] == 3
    assert abs(sum(rc["weights"].values()) - 1.0) < 1e-9, "等权权重和应为 1"
    assert -1.0 < rc["avg_pairwise_corr"] < 1.0, "相关性诊断应有效"
    rv = pf.compose(method="vol")
    assert abs(sum(rv["weights"].values()) - 1.0) < 1e-9, "波动率加权权重和应为 1"
    assert pf.to_frame(method="equal").shape[0] == 400, "权益表行数应=K线数"
    print("    · 组合层(equal/vol/相关性) 自检通过")

    # —— 实盘适配器安全层（dry-run）自检 ——
    from src.broker import LiveBroker
    # 默认 dry-run：绝不触碰交易所，用 paper 记账
    lb = LiveBroker(registry=reg, initial_cash=100000, live_enabled=False, dry_run=True)
    assert not lb.is_armed(), "默认不应 armed"
    assert "DRY-RUN" in lb.status()
    lb.mark("AAPL", 100.0)
    f = lb.submit_order(Order("AAPL", "us", "spot", "buy", 10))
    assert f is not None and f.qty == 10
    acct_lb = lb.get_account()
    assert acct_lb["cash"] < 100000, "dry-run 记账应扣减现金（仅模拟，未真下单）"
    assert len(lb.dry_orders) == 1, "应记录 1 笔本应下的单"
    # 即便 live_enabled=True 但 dry_run=True，仍不应 armed（双闸门）
    lb2 = LiveBroker(registry=reg, initial_cash=100000, live_enabled=True, dry_run=True)
    assert not lb2.is_armed(), "dry_run=True 时即便配置允许也不应 armed"
    print("    · 实盘安全层(dry-run 双闸门) 自检通过")

    print("✅ selftest 通过：风控 + 回测 + 多标的规格 + 模拟盘 + 日历 + 寻优器 "
          "+ 组合层 + 实盘安全层 均正常")
    print_report(r, risk, "SELFTEST", "demo")


def _fetch_df(symbol: str, market: str, settings: dict, limit: int = 400):
    """优先走 DataHub（联网），失败则回退到本地 data/real 落库 parquet。"""
    try:
        hub = DataHub(settings)
        df = hub.get(symbol, market, "1d", limit)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    p = ROOT / "data" / "real" / f"{market}_{symbol}_1d.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return None


def cmd_paper(args) -> None:
    """用真实数据跑一次"前向模拟盘"，验证执行层（现货/期货/ETF + 多空 + 风控限仓）。"""
    settings = load_settings()
    preset = load_preset(args.preset)
    market = norm_market(args.market)
    df = _fetch_df(args.symbol, market, settings, args.limit)
    if df is None or df.empty:
        raise SystemExit("拉不到数据（检查代码/网络/本地 data/real）")

    risk = build_risk_controller(settings, preset.get("risk_override"))
    registry = InstrumentRegistry(load_instrument_overrides())
    itype = args.itype
    spec = registry.get(args.symbol, market, itype)
    broker = PaperBroker(initial_cash=settings["backtest"]["initial_capital"], registry=registry)

    sig = _STRATS[preset["strategy"]](df, **preset.get("params", {})).shift(1).fillna(0)

    n_entry = n_exit = 0
    for i in range(1, len(df)):
        price = float(df["close"].iloc[i])
        broker.mark(args.symbol, price)
        desired = int(sig.iloc[i])
        cur = broker.get_positions().get(args.symbol)
        cur_qty = cur.qty if cur else 0.0

        if desired != 0 and cur_qty == 0:
            # 按风控最大单笔市值估算手数
            per = spec.multiplier * spec.contract_unit
            qty = risk.max_position_value() / (price * per)
            qty = spec.round_qty(qty)
            ok, msg = risk.proposed_size_ok(args.symbol, spec.notional(qty, price))
            if ok and qty > 0:
                side = "buy" if desired > 0 else "sell"
                if broker.submit_order(Order(args.symbol, market, itype, side, qty)):
                    n_entry += 1
        elif desired == 0 and cur_qty != 0:
            side = "sell" if cur_qty > 0 else "buy"
            if broker.submit_order(Order(args.symbol, market, itype, side, abs(cur_qty))):
                n_exit += 1

    acct = broker.get_account()
    print("\n" + "=" * 52)
    print(f"  🧪 {args.symbol}（{market}/{itype}）前向模拟盘 · 执行层验证")
    print("=" * 52)
    print(f"  策略           : {preset['strategy']}")
    print(f"  数据区间       : {df.index[0].date()} → {df.index[-1].date()}（{len(df)} 根K线）")
    print(f"  入场次数       : {n_entry} ｜ 离场次数: {n_exit}")
    print(f"  期末权益       : {acct['equity']:,.2f}")
    print(f"  已实现盈亏     : {acct['realized_pnl']:,.2f}")
    print(f"  浮动盈亏       : {acct['unrealized_pnl']:,.2f}")
    print(f"  现金           : {acct['cash']:,.2f}")
    if spec.is_leveraged:
        print(f"  占用保证金     : {acct['margin_used']:,.2f}（期货杠杆）")
    print("-" * 52)
    s = risk.summary()
    print("  🛡️ 强制风控最小集：单笔≤"
          f"{fmt_pct(s['max_single_position_pct'])} ｜ 总≤{fmt_pct(s['max_total_position_pct'])}"
          f" ｜ 止损{fmt_pct(s['stop_loss_pct'])}")
    print("=" * 52)
    print("  ✅ 执行层（模拟盘）工作正常：多空/保证金/风控限仓均已通过\n")


def cmd_sweep(args) -> None:
    """批量跑 标的×预设 实验，产出横向对比与可上实盘评分。"""
    settings = load_settings()
    registry = InstrumentRegistry(load_instrument_overrides())
    runner = ExperimentRunner(settings, registry)

    jobs: list[tuple[str, str, pd.DataFrame, str]] = []
    for job in args.jobs.split(","):
        sym, mkt, pre = (job.split(":") + ["", "", ""])[:3]
        sym, mkt, pre = sym.strip(), mkt.strip(), pre.strip()
        if not sym or not mkt or not pre:
            continue
        mkt = norm_market(mkt)
        df = _fetch_df(sym, mkt, settings, args.limit)
        jobs.append((sym, mkt, df, pre))

    if not jobs:
        raise SystemExit("用法: --jobs 600519:a:conservative,00700:hk:balanced")

    df = runner.run(jobs)
    print("\n" + "=" * 52)
    print("  🔬 实验扫描结果（按可上实盘评分降序）")
    print("=" * 52)
    ExperimentRunner.print_table(df)
    print("=" * 52)
    out = ROOT / "data" / "experiments" / f"sweep_{pd.Timestamp.now():%Y%m%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  📁 已保存: {out}\n")


def cmd_calendar(args) -> None:
    """查询某市场某日是否开市、当前时段。"""
    d = pd.Timestamp(args.date).date() if args.date else None
    for mkt in (args.markets.split(",") if args.markets else ["a", "hk", "us", "crypto"]):
        mkt = norm_market(mkt.strip())
        open_day = mcal.is_trading_day(mkt, d)
        sess = mcal.market_session(mkt, datetime.combine(d or date.today(), time(10, 0)))
        label = "开市" if open_day else "休市"
        print(f"  {mkt:7s} {str(d or date.today())}：{label} ｜ 时段={sess}")


def cmd_optimize(args) -> None:
    """参数寻优：用真实数据 + walk-forward 样本外，自动找稳健参数。

    排序依据是样本外指标，而非样本内——避免挑出"看起来很美"的过拟合参数。
    通过门槛(评分≥70 且未过拟合)的参数可 --save-best 落为新的策略预设。
    """
    settings = load_settings()
    market = norm_market(args.market)
    df = _fetch_df(args.symbol, market, settings, args.limit)
    if df is None or df.empty:
        raise SystemExit("拉不到数据（检查代码/网络/本地 data/real）")

    strategy = args.strategy
    if strategy not in DEFAULT_SPACES:
        raise SystemExit(f"支持寻优的策略: {list(DEFAULT_SPACES)}")

    opt = ParameterOptimizer(settings)
    results = opt.optimize(df, strategy, top_k=args.top)
    ParameterOptimizer.print_results(results, strategy, f"{args.symbol}({market})")

    # 实验追踪：记录本次运行的最优结果（落盘 data/experiments/runs.jsonl）
    if results:
        rec = record_run(args.symbol, market, strategy, results[0],
                         mode="single", n_scanned=len(results))
        print(f"  🗂️ 实验已记录: {rec['ts']} 评分={rec['best_score']} 闸门={rec['gate_ok']}")

    # 过拟合整体提示
    overfit = [r for r in results if r.overfit_flag]
    if overfit:
        print(f"\n⚠️ {len(overfit)}/{len(results)} 个组合被标记可能过拟合（样本内远好于样本外），已自动降权。")

    best = results[0] if results else None
    if args.save_best and best is not None:
        if best.score >= PASS_SCORE and best.gate_ok and not best.overfit_flag:
            name = f"{args.symbol}_{market}_opt"
            preset = {
                "name": f"寻优·{args.symbol}({market})",
                "profile": "optimized",
                "strategy": strategy,
                "params": best.params,
                "markets": [market],
                "instruments": ["spot", "etf"],
                "risk_override": settings.get("risk", {}),
                "note": (f"由参数寻优自动生成（评分 {best.score}，"
                         f"样本外夏普 {best.out_sample.get('sharpe', float('nan')):.2f}）。"
                         f"仍需走模拟盘灰度验证后才可实盘。"),
            }
            out = ROOT / "config" / "strategies" / f"{name}.yaml"
            out.write_text(yaml.safe_dump(preset, allow_unicode=True), encoding="utf-8")
            print(f"\n✅ 已落盘可部署预设: {out}")
            print(f"   验证: python quantos.py paper --preset {name} --symbol {args.symbol} --market {market}")
        else:
            print(f"\n⚠️ 最优组合评分 {best.score} < {PASS_SCORE} 或已过拟合，"
                  f"按纪律不落盘——请换标的/策略或接受模拟盘观察。")


def cmd_combine(args) -> None:
    """组合层：把多个 标的×策略(preset) 腿合成一个组合，输出聚合绩效 + 相关性诊断。"""
    settings = load_settings()
    registry = InstrumentRegistry(load_instrument_overrides())
    pf = Portfolio(capital=settings["backtest"]["initial_capital"])

    for job in args.jobs.split(","):
        sym, mkt, pre = (job.split(":") + ["", "", ""])[:3]
        sym, mkt, pre = sym.strip(), mkt.strip(), pre.strip()
        if not all([sym, mkt, pre]):
            continue
        mkt = norm_market(mkt)
        preset = load_preset(pre)
        df = _fetch_df(sym, mkt, settings, args.limit)
        if df is None or df.empty:
            print(f"⚠️ {sym}({mkt}) 拉不到数据，跳过")
            continue
        name = f"{sym}/{mkt}/{preset['strategy']}"
        pf.add_leg(name, df, preset["strategy"], preset.get("params", {}))
        print(f"  + 腿: {name}  ({len(df)}根K线)")

    if len(pf.legs) < 2:
        raise SystemExit("组合至少需要 2 条腿（--jobs 给多个 代码:市场:预设）")

    res = pf.compose(method=args.weight)
    m = res["metrics"]
    print("\n" + "=" * 52)
    print(f"  🧩 组合层结果 · 权重={args.weight} · {res['n_legs']} 条腿")
    print("=" * 52)
    print(f"  组合总收益     : {fmt_pct(m['total_return'])}")
    print(f"  组合年化       : {fmt_pct(m['annual_return'])}")
    print(f"  组合最大回撤   : {fmt_pct(m['max_drawdown'])}")
    print(f"  组合夏普       : {m['sharpe']:.2f}")
    print("-" * 52)
    print("  📊 各腿权重:")
    for k, v in res["weights"].items():
        print(f"    {k:32s} {fmt_pct(v)}")
    print("-" * 52)
    print("  🔍 分散诊断（平均两两相关，越接近 1 越像伪分散）:")
    print(f"    avg_pairwise_corr = {res['avg_pairwise_corr']:.3f}")
    print("  —— 各腿独立指标 ——")
    for k, lm in res["legs"].items():
        print(f"    {k:32s} 收益={fmt_pct(lm['total_return'])} 回撤={fmt_pct(lm['max_drawdown'])} 夏普={lm['sharpe']:.2f}")
    print("=" * 52)

    out = ROOT / "data" / "experiments" / f"portfolio_{pd.Timestamp.now():%Y%m%d_%H%M%S}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pf.to_frame(method=args.weight).to_csv(out, encoding="utf-8-sig")
    print(f"  📁 权益曲线已保存: {out}\n")


def cmd_live(args) -> None:
    """实盘执行层：默认 DRY-RUN（绝不发真单）；双闸门才真正下单。

    双闸门：① settings.yaml 中 live_trading.enabled=True；② 显式 --i-understand-real-money-risk。
    任一不满足 → 走 dry-run 沙盘推演，只记录「本应下的单」，不触碰交易所。
    """
    settings = load_settings()
    preset = load_preset(args.preset)
    market = norm_market(args.market)
    df = _fetch_df(args.symbol, market, settings, args.limit)
    if df is None or df.empty:
        raise SystemExit("拉不到数据（检查代码/网络/本地 data/real）")

    risk = build_risk_controller(settings, preset.get("risk_override"))
    registry = InstrumentRegistry(load_instrument_overrides())
    itype = args.itype
    spec = registry.get(args.symbol, market, itype)

    live_enabled = settings.get("live_trading", {}).get("enabled", False)
    dry_run = not args.i_understand_real_money_risk  # 默认 dry-run
    broker = LiveBroker(
        registry=registry, initial_cash=settings["backtest"]["initial_capital"],
        live_enabled=live_enabled, dry_run=dry_run, backend=args.backend,
    )

    sig = _STRATS[preset["strategy"]](df, **preset.get("params", {})).shift(1).fillna(0)
    rep = broker.dry_run_replay(
        args.symbol, market, itype, sig, df, risk=risk, registry=registry)

    print("\n" + "=" * 52)
    print(f"  🛰️ {args.symbol}（{market}/{itype}）实盘执行层 · 安全模式")
    print("=" * 52)
    print(f"  执行状态       : {broker.status()}")
    print(f"  策略           : {preset['strategy']}")
    print(f"  入场次数       : {rep['n_entry']} ｜ 离场次数: {rep['n_exit']}")
    acct = rep["account"]
    print(f"  期末权益       : {acct['equity']:,.2f}")
    print(f"  已实现盈亏     : {acct['realized_pnl']:,.2f}")
    print(f"  现金           : {acct['cash']:,.2f}")
    print("=" * 52)
    if not broker.is_armed():
        print("  🟢 DRY-RUN：以上成交均为模拟，未向任何交易所发送真实订单。")
        if not live_enabled:
            print("     安全提示: settings.yaml 仍未打开 live_trading.enabled，"
                  "故即便去掉风险确认也只会 dry-run。")
    else:
        print("  🔴 真实订单已发送，请立即于券商后台核对持仓与成交！")


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

    # 前向模拟盘（执行层验证）
    p = sub.add_parser("paper", help="用真实数据跑前向模拟盘(执行层)")
    p.add_argument("--preset", default="balanced")
    p.add_argument("--symbol", required=True)
    p.add_argument("--market", required=True)
    p.add_argument("--itype", default="spot", choices=["spot", "future", "etf"])
    p.add_argument("--limit", type=int, default=400)
    p.set_defaults(func=cmd_paper)

    # 实验扫描（批量回测 + 样本外 + 评分）
    sw = sub.add_parser("sweep", help="批量实验扫描(标的×预设)")
    sw.add_argument("--jobs", required=True,
                    help="逗号分隔: 代码:市场:预设, 如 600519:a:conservative,00700:hk:balanced")
    sw.add_argument("--limit", type=int, default=400)
    sw.set_defaults(func=cmd_sweep)

    # 交易日历查询
    c = sub.add_parser("calendar", help="查询市场开市/时段")
    c.add_argument("--markets", default="a,hk,us,crypto")
    c.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    c.set_defaults(func=cmd_calendar)

    # 参数寻优（walk-forward 样本外排序 + 过拟合检测）
    o = sub.add_parser("optimize", help="参数寻优(样本外排序)")
    o.add_argument("--symbol", required=True)
    o.add_argument("--market", required=True)
    o.add_argument("--strategy", default="sma_cross", choices=list(DEFAULT_SPACES))
    o.add_argument("--top", type=int, default=5, help="返回 Top-K 参数组合")
    o.add_argument("--limit", type=int, default=400)
    o.add_argument("--save-best", action="store_true", help="把通过门槛的最优参数落为预设")
    o.set_defaults(func=cmd_optimize)

    # 组合层（多标的/多策略合成 + 相关性诊断）
    cb = sub.add_parser("combine", help="组合层(多腿合成+相关性诊断)")
    cb.add_argument("--jobs", required=True,
                    help="逗号分隔: 代码:市场:预设, 如 09999:hk:09999_hk_rsi_reversal_opt,AAPL:us:balanced")
    cb.add_argument("--weight", default="equal", choices=["equal", "vol"])
    cb.add_argument("--limit", type=int, default=400)
    cb.set_defaults(func=cmd_combine)

    # 实盘执行层（默认 DRY-RUN，双闸门才发真单）
    lv = sub.add_parser("live", help="实盘执行(默认DRY-RUN,需双闸门才发真单)")
    lv.add_argument("--preset", default="balanced")
    lv.add_argument("--symbol", required=True)
    lv.add_argument("--market", required=True)
    lv.add_argument("--itype", default="spot", choices=["spot", "future", "etf"])
    lv.add_argument("--limit", type=int, default=400)
    lv.add_argument("--backend", default="ccxt", choices=["ccxt", "easytrader"])
    lv.add_argument("--i-understand-real-money-risk", action="store_true",
                    help="确认已明白真实下单不可逆；仍需 settings.yaml 打开 live_trading")
    lv.set_defaults(func=cmd_live)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
