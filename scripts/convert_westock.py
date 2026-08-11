#!/usr/bin/env python3
"""把腾讯自选股(westock-mcp) data_kline 返回的 JSON 转为统一 parquet。

westock 返回结构:
  {"ok":true,"data":{"nodes":[{"date","open","last","high","low","volume",...}]}}
其中收盘价在 `last` 字段（非 `close`）。

用法:
  python scripts/convert_westock.py <kline.json> <out.parquet>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def parse(path: str) -> pd.DataFrame:
    text = Path(path).read_text(encoding="utf-8")
    start = text.find("{")
    if start < 0:
        raise ValueError("找不到 JSON")
    obj = json.loads(text[start:])
    nodes = obj.get("data", {}).get("nodes") or obj.get("nodes") or []
    if not nodes:
        raise ValueError("nodes 为空")
    recs = []
    for n in nodes:
        close = n.get("last", n.get("close"))
        if close is None:
            continue
        recs.append({
            "date": pd.to_datetime(str(n["date"])),
            "open": float(n.get("open", 0) or 0),
            "high": float(n.get("high", 0) or 0),
            "low": float(n.get("low", 0) or 0),
            "close": float(close),
            "volume": float(n.get("volume", 0) or 0),
        })
    df = pd.DataFrame(recs).set_index("date").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    return df


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: convert_westock.py <kline.json> <out.parquet>")
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
