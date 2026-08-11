#!/usr/bin/env python3
"""把通达信 MCP (tdx-connector) 返回的 K线 JSON 转为统一 parquet。

用法:
  python scripts/convert_tdx.py <kline.json> <out.parquet> [market]

输入兼容 tdx-connector 输出:
  {"Rows":[{"Data":"20241217","Open":...,"High":...,"Low":...,"Close":...,"Volume":...}]}

输出: data/real 约定格式（open/high/low/close/volume，index=date）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def parse(path: str) -> pd.DataFrame:
    text = Path(path).read_text(encoding="utf-8")
    start = text.find("{")
    if start < 0:
        raise ValueError("找不到 JSON")
    import json
    obj = json.loads(text[start:])
    rows = obj.get("Rows") or obj.get("rows") or []
    if not rows:
        raise ValueError("Rows 为空")
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
    return df


def main():
    if len(sys.argv) < 3:
        print("用法: convert_tdx.py <kline.json> <out.parquet> [market]")
        return 1
    df = parse(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    print(f"OK {out}  rows={len(df)}  "
          f"{df.index[0].date()}~{df.index[-1].date()}  close={df['close'].iloc[-1]:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
