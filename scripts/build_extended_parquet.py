"""把 westock data_kline 的原始结果文件（limit=800）转成「更长样本」parquet。

输出到 data/real_ext/（不覆盖原有 data/real/ 的 520 根样本，便于对照）。
用法：python scripts/build_extended_parquet.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("/Users/zhoupeng/.workbuddy/projects/Users-zhoupeng-WorkBuddy-量化交易/982c02b2-afef-420d-8044-254def6f4aea/tool-results")
SRC = {
    "hk09999": BASE / "mcp-connector-proxy-westock-mcp_data_kline-1786498917571-69064b.txt",
    "usV": BASE / "mcp-connector-proxy-westock-mcp_data_kline-1786498922590-0373a1.txt",
}
OUT = ROOT / "data" / "real_ext"
OUT.mkdir(parents=True, exist_ok=True)


def build(code: str, path: Path) -> pd.DataFrame:
    txt = json.loads(path.read_text(encoding="utf-8"))
    nodes = txt["data"]["nodes"]
    rows = []
    for n in nodes:
        rows.append({
            "date": pd.Timestamp(n["date"]),
            "open": float(n["open"]),
            "high": float(n["high"]),
            "low": float(n["low"]),
            "close": float(n["last"]),
            "volume": float(n.get("volume", 0)),
        })
    df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date").set_index("date")
    # westock qfq 日K 偶尔含 0 成交的停牌行，剔除异常
    df = df[df["close"] > 0]
    out = OUT / f"{code}_1d_ext.parquet"
    df.to_parquet(out)
    print(f"  {code}: {len(df)} 根  {df.index[0].date()} → {df.index[-1].date()}  → {out.name}")
    return df


if __name__ == "__main__":
    print("构建更长样本 parquet (data/real_ext/)：")
    for code, p in SRC.items():
        build(code, p)
    print("完成。")
