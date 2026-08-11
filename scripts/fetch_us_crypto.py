#!/usr/bin/env python3
"""批量拉取美股(Yahoo) + 数字货币(OKX) 真实日K，落库为 data/real 约定格式。

用法（沙箱外运行，需要联网）:
  python scripts/fetch_us_crypto.py

输出: data/real/us_<TICKER>_1d.parquet  /  data/real/crypto_<BASE>USDT_1d.parquet
列: open/high/low/close/volume, index=date
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

OUT = "data/real"
UA = {"User-Agent": "Mozilla/5.0"}


def fetch_yahoo(symbol: str, out_name: str) -> None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d"
    req = urllib.request.Request(url, headers=UA)
    obj = json.loads(urllib.request.urlopen(req, timeout=25).read())
    r = obj["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"open": q["open"], "high": q["high"], "low": q["low"],
         "close": q["close"], "volume": q["volume"]},
        index=pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").normalize(),
    )
    df = df.dropna().sort_index()
    df.to_parquet(f"{OUT}/{out_name}.parquet")
    print(f"[Yahoo] {symbol}: {len(df)} rows "
          f"{df.index[0].date()}->{df.index[-1].date()} close={df['close'].iloc[-1]:.2f}")


def fetch_okx(inst_id: str, out_name: str, need: int = 450) -> None:
    rows_all: list = []
    after = None
    for _ in range(12):
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=1D&limit=100"
        if after:
            url += f"&after={after}"
        req = urllib.request.Request(url, headers=UA)
        obj = json.loads(urllib.request.urlopen(req, timeout=25).read())
        data = obj.get("data", [])
        if not data:
            break
        rows_all.extend(data)
        after = data[-1][0]  # 本页最旧一根的时间戳(ms)，用于翻页取更早期
        if len(rows_all) >= need:
            break
        time.sleep(0.2)
    recs = []
    for r in rows_all:
        ts_ms, o, h, l, c, vol = r[0], r[1], r[2], r[3], r[4], r[5]
        recs.append((
            datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).date(),
            float(o), float(h), float(l), float(c), float(vol),
        ))
    df = pd.DataFrame(recs, columns=["date", "open", "high", "low", "close", "volume"])
    df = df.set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")]
    df.to_parquet(f"{OUT}/{out_name}.parquet")
    print(f"[OKX] {inst_id}: {len(df)} rows "
          f"{df.index[0].date()}->{df.index[-1].date()} close={df['close'].iloc[-1]:.2f}")


def main() -> None:
    import os
    os.makedirs(OUT, exist_ok=True)
    us = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "JPM", "COST"]
    for s in us:
        try:
            fetch_yahoo(s, f"us_{s}_1d")
        except Exception as e:  # noqa: BLE001
            print("YAHOO_FAIL", s, type(e).__name__, str(e)[:120])

    crypto = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT",
              "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT"]
    for c in crypto:
        try:
            fetch_okx(c, f"crypto_{c.replace('-USDT', '')}USDT_1d")
        except Exception as e:  # noqa: BLE001
            print("OKX_FAIL", c, type(e).__name__, str(e)[:120])
    print("DONE")


if __name__ == "__main__":
    main()
