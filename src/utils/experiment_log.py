"""轻量实验追踪（穷人版 MLflow）。

每次参数寻优 / 全宇宙扫描的结果追加到 data/experiments/runs.jsonl，
便于横向比较、防回归、复盘「哪些参数空间曾经出过线」。

设计：零依赖（纯标准库 + json），落盘为 JSON Lines，一行一次运行。
不会因记录实验而拖慢寻优；失败的运行也会记一笔（便于排查）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "experiments" / "runs.jsonl"


def record_run(symbol, market, strategy, top_result,
               mode: str = "single", n_scanned: int | None = None) -> dict:
    """记录一次寻优运行的最优结果。

    top_result: 需具备 params / score / gate_ok / overfit_flag / verdict /
                in_sample(dict) / out_sample(dict) / note 属性（OptResult 即可）。
    """
    oos = top_result.out_sample or {}
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,                       # single / universe
        "symbol": symbol,
        "market": market,
        "strategy": strategy,
        "n_scanned": n_scanned,
        "best_params": top_result.params,
        "best_score": top_result.score,
        "gate_ok": top_result.gate_ok,
        "overfit_flag": top_result.overfit_flag,
        "verdict": top_result.verdict,
        "quality_veto": bool(getattr(top_result, "quality", None)
                             and top_result.quality.get("veto")) if hasattr(top_result, "quality") else None,
        "quality_score": _round((getattr(top_result, "quality", None) or {}).get("score"))
                        if hasattr(top_result, "quality") else None,
        "is_sharpe": _round(top_result.in_sample.get("sharpe")),
        "wf_sharpe": _round(oos.get("wf_sharpe")),
        "holdout_sharpe": _round(oos.get("holdout_sharpe")),
        "n_valid_windows": oos.get("n_valid_windows"),
        "holdout_trades": oos.get("holdout_trades"),
        "note": getattr(top_result, "note", "") or "",
    }
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _round(x, nd: int = 3):
    try:
        if x is None or (isinstance(x, float) and x != x):  # NaN
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def load_runs() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def summary() -> dict:
    rows = load_runs()
    winners = [r for r in rows
               if r.get("gate_ok") and r.get("best_score", 0) >= 70
               and not r.get("overfit_flag")]
    return {
        "total_runs": len(rows),
        "winners": len(winners),
        "winner_list": winners,
    }
