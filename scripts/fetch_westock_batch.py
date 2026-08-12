#!/usr/bin/env python3
"""批量拉取 westock 港股/美股 K 线并落库为 data/real/{market}_{symbol}_1d.parquet。

用法:
  python scripts/fetch_westock_batch.py

清单在 BATCH 中: (market, symbol, westock_code)
- 港股: hk + 5位代码, westock code = "hk" + "0"*pad + code  (如 01299 -> hk01299)
- 美股: us + ticker,    westock code = ticker        (如 BRK.B)

依赖 westock-mcp 的 data_kline 工具 (通过 MCP 调用，本脚本仅负责本地落库)。
由于 MCP 工具无法在纯脚本内直接调用，这里改为：由调用方把每支标的的
data_kline JSON 写入 data/real/_raw/{market}_{symbol}.json，本脚本统一转换落库。

因此真实调用流程：
  1) 通过 westock-mcp data_kline 逐支拉取，写入 data/real/_raw/<market>_<symbol>.json
  2) python scripts/fetch_westock_batch.py   # 统一转换为 parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.convert_westock import parse  # 复用转换逻辑


def main() -> int:
    root = Path(__file__).parent.parent
    raw_dir = root / "data" / "real" / "_raw"
    out_dir = root / "data" / "real"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not raw_dir.exists():
        print(f"未找到 {raw_dir}，请先用 westock-mcp data_kline 拉取并写入 <market>_<symbol>.json")
        return 1
    raws = sorted(raw_dir.glob("*.json"))
    if not raws:
        print(f"{raw_dir} 下无 json")
        return 1
    ok = 0
    for p in raws:
        # 文件名形如 hk_01299.json / us_BRK.B.json
        stem = p.stem
        try:
            market, symbol = stem.split("_", 1)
        except ValueError:
            print(f"跳过(文件名不符 market_symbol): {p.name}")
            continue
        out = out_dir / f"{market}_{symbol}_1d.parquet"
        try:
            df = parse(str(p))
        except Exception as e:  # noqa: BLE001
            print(f"✗ {stem}: 解析失败 {e}")
            continue
        df.to_parquet(out)
        print(f"OK {out.name}  rows={len(df)}  {df.index[0].date()}~{df.index[-1].date()}  close={df['close'].iloc[-1]:.2f}")
        ok += 1
    print(f"\n完成: {ok}/{len(raws)} 落库成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
