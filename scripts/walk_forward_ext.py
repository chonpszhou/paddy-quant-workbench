"""网易/Visa 更长样本(~3.2yr, 800根) walk-forward 稳健性验证。

对比「原 520 根(2yr)」与「扩展 800 根(3.2yr)」下 rsi_reversal(p=7) 的样本外表现：
  - 逐窗口 OOS 夏普（看信号在不同时段是否稳定为正）
  - 有效窗口占比、正收益窗口占比
  - 双闸门聚合：WF 均值夏普 + 严格保留集夏普
  - 分段稳定性：前半段 vs 后半段 是否一致（避免"只靠某一波行情"）

用法：python scripts/walk_forward_ext.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.backtest import Backtester  # noqa: E402
from src.engine.optimizer import (  # noqa: E402
    ParameterOptimizer, WF_TRAIN, WF_TEST, WF_STEP, MIN_TRADES_WINDOW,
)

PARAMS = {"period": 7, "oversold": 25, "overbought": 70}
STRAT = "rsi_reversal"

TARGETS = {
    "网易(hk09999)": ("data/real_ext/hk09999_1d_ext.parquet", "data/real/hk_09999_1d.parquet"),
    "Visa(usV)":     ("data/real_ext/usV_1d_ext.parquet", "data/real/us_V_1d.parquet"),
}


def wf_windows(df: pd.DataFrame) -> list[dict]:
    bt = Backtester()
    return bt.walk_forward(df, STRAT, WF_TRAIN, WF_TEST, WF_STEP, **PARAMS)


def summarize_windows(windows: list[dict]) -> dict:
    valid = [w for w in windows if w["n_trades"] >= MIN_TRADES_WINDOW]
    if not valid:
        return {"n_windows": len(windows), "n_valid": 0}
    sharpe = np.array([w["sharpe"] for w in valid])
    ret = np.array([w["total_return"] for w in valid])
    return {
        "n_windows": len(windows),
        "n_valid": len(valid),
        "wf_sharpe_mean": float(np.mean(sharpe)),
        "wf_sharpe_med": float(np.median(sharpe)),
        "pct_positive_sharpe": float((sharpe > 0).mean() * 100),
        "pct_positive_ret": float((ret > 0).mean() * 100),
        "worst_window_sharpe": float(sharpe.min()),
        "mean_return_per_win": float(np.mean(ret)),
    }


def aggregate(df: pd.DataFrame) -> dict:
    opt = ParameterOptimizer({"risk": {"max_drawdown_circuit_pct": 0.20}})
    return opt._out_of_sample(df, STRAT, PARAMS)


def robustness_row(label: str, ext_path: str, orig_path: str) -> dict:
    ext = pd.read_parquet(ROOT / ext_path)
    orig = pd.read_parquet(ROOT / orig_path)

    ext_w = wf_windows(ext)
    orig_w = wf_windows(orig)
    ext_s = summarize_windows(ext_w)
    orig_s = summarize_windows(orig_w)
    agg = aggregate(ext)

    # 分段稳定性：前 400 vs 后 400
    half = len(ext) // 2
    front = summarize_windows(wf_windows(ext.iloc[:half]))
    back = summarize_windows(wf_windows(ext.iloc[half:]))

    # 稳健判据：有效窗口 WF 均值夏普≥0.8 且 正收益窗口≥55%
    robust = (ext_s.get("wf_sharpe_mean", -99) >= 0.8
              and ext_s.get("pct_positive_ret", 0) >= 55.0)
    return {
        "label": label,
        "ext_bars": len(ext), "ext_range": [str(ext.index[0].date()), str(ext.index[-1].date())],
        "ext": ext_s, "orig": orig_s,
        "agg_wf_sharpe": agg.get("wf_sharpe"),
        "agg_holdout_sharpe": agg.get("holdout_sharpe"),
        "agg_holdout_trades": agg.get("holdout_trades"),
        "front_half": front, "back_half": back,
        "robust": robust,
    }


def main() -> None:
    print("=" * 100)
    print("  更长样本 walk-forward 稳健性：rsi_reversal(p=7, oversold=25) on 网易/Visa")
    print("=" * 100)
    out_rows = []
    for label, (ext_p, orig_p) in TARGETS.items():
        r = robustness_row(label, ext_p, orig_p)
        out_rows.append(r)
        print(f"\n### {label}")
        print(f"  扩展样本: {r['ext_bars']} 根  {r['ext_range'][0]}→{r['ext_range'][1]}")
        e, o = r["ext"], r["orig"]
        print(f"  逐窗口 OOS 夏普 均值(扩展/原): {e.get('wf_sharpe_mean'):.2f} / {o.get('wf_sharpe_mean'):.2f}"
              f"  正收益窗口%(扩展/原): {e.get('pct_positive_ret'):.0f}% / {o.get('pct_positive_ret'):.0f}%")
        print(f"  有效窗口数(扩展/原): {e.get('n_valid')} / {o.get('n_valid')}"
              f"  最差窗口夏普(扩展): {e.get('worst_window_sharpe'):.2f}")
        print(f"  双闸门聚合 WF夏普={r['agg_wf_sharpe']:.2f}  保留集夏普={r['agg_holdout_sharpe']:.2f}"
              f"(交易 {r['agg_holdout_trades']}次)")
        print(f"  分段稳定性 前半段WF均值={r['front_half'].get('wf_sharpe_mean'):.2f}"
              f"  后半段WF均值={r['back_half'].get('wf_sharpe_mean'):.2f}")
        print(f"  ➜ 稳健性判定: {'✅ 稳健（长样本下信号仍有效）' if r['robust'] else '⚠️ 不稳健'}")

    # 全局结论
    all_robust = all(r["robust"] for r in out_rows)
    print("\n" + "-" * 100)
    print(f"总判定：{len(out_rows)} 个候选中 {sum(r['robust'] for r in out_rows)} 个在 3.2 年样本下仍稳健。"
          if all_robust else f"总判定：存在不稳健候选，需谨慎。")
    print("=" * 100)

    out = ROOT / "data" / "experiments" / "wf_robustness.json"
    out.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()
