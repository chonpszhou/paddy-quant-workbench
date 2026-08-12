"""演示第四道闸门（基本面质量否决）的价值。

场景：用 3 个「双闸门已过」的候选（网易/携程/Visa，rsi_reversal p=7），
分别跑「仅双闸门」与「双闸门 + 质量否决」：
  - 携程：双闸门通过 → 但基本面是价值陷阱 → 被第四道闸门否决（AVOID）。
  - 网易/Visa：双闸门通过 → 质量过关 → 允许进模拟盘。

用法：python scripts/demo_quality_gate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.optimizer import ParameterOptimizer  # noqa: E402
from src.engine.quality_filter import Fundamentals  # noqa: E402

SETTINGS = {"risk": {"max_drawdown_circuit_pct": 0.20}}

# 代码 → (市场, parquet 路径, 基本面 key)
CANDIDATES = {
    "网易 (hk09999)":   ("hk", "data/real/hk_09999_1d.parquet", "hk09999"),
    "携程 (hk09961)":   ("hk", "data/real/hk_09961_1d.parquet", "hk09961"),
    "Visa (usV)":       ("us", "data/real/us_V_1d.parquet", "usV"),
}


def _load_fund(key: str) -> Fundamentals:
    # 读取受版本控制的种子（config/fundamentals/）；data/fundamentals/ 为运行时存储(被 gitignore)
    path = ROOT / "config" / "fundamentals" / "candidates.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Fundamentals.from_dict(data[key])


def main() -> None:
    print("=" * 92)
    print("  第四道闸门演示：双闸门(统计) + 质量否决(基本面) → 真钱前的最后护栏")
    print("=" * 92)

    opt = ParameterOptimizer(SETTINGS)
    rows = []
    for label, (mkt, parquet, fkey) in CANDIDATES.items():
        df = pd.read_parquet(ROOT / parquet)
        fund = _load_fund(fkey)

        # 仅双闸门
        r_noq = opt.optimize(df, "rsi_reversal", fundamentals=None)[0]
        # 双闸门 + 质量否决
        r_q = opt.optimize(df, "rsi_reversal", fundamentals=fund)[0]

        dg = "✓ 通过" if r_noq.gate_ok else "✗ 未过"
        final = r_q.verdict
        qtag = "❌ 否决" if (r_q.quality and r_q.quality.get("veto")) else "✓ 通过"
        disposition = "允许进模拟盘" if r_q.gate_ok else "拦截(AVOID)"
        rows.append((label, dg, qtag, final, disposition,
                     "; ".join((r_q.quality or {}).get("reasons", [])) or "—"))

    print(f"\n{'标的':<16}{'双闸门':<8}{'质量否决':<10}{'最终处置':<18}{'拦截原因'}")
    print("-" * 92)
    for label, dg, qtag, final, disp, reason in rows:
        print(f"{label:<16}{dg:<8}{qtag:<10}{final:<18}{reason}")
    print("-" * 92)

    # 小结
    vetoed = [r for r in rows if "否决" in r[2]]
    passed = [r for r in rows if "通过" in r[2]]
    print(f"\n结论：双闸门放行 {len(rows)} 个候选；第四道闸门再拦下 {len(vetoed)} 个"
          f"（{', '.join(r[0] for r in vetoed) or '无'}），最终允许 {len(passed)} 个进模拟盘。")
    print("价值：双闸门只管「信号历史有用」，不管「公司是不是雷」——")
    print("      携程正是「统计过关、基本面是价值陷阱」的典型，第四道闸门在真钱前把它拦下。")
    print("=" * 92)


if __name__ == "__main__":
    main()
