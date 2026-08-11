"""本地行情存储层。

- Storage：轻量 parquet 缓存（原实现，保留）。
- SQLStore：历史数据落库（规划优先级 #1）—— SQLite + parquet 双写，
  支持增量更新与按区间查询，避免每次回测重复拉取。零运维。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from ..utils.common import ensure_dir


class Storage:
    """轻量 parquet 缓存。"""

    def __init__(self, cache_dir: str):
        self.dir = ensure_dir(cache_dir)

    def _path(self, key: str):
        safe = key.replace("/", "_").replace(":", "_")
        return self.dir / f"{safe}.parquet"

    def save(self, key: str, df: pd.DataFrame) -> None:
        try:
            df.to_parquet(self._path(key))
        except Exception:
            pass

    def load(self, key: str) -> pd.DataFrame | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            return None


class SQLStore:
    """历史行情落库（SQLite + parquet 备用）。

    表 quotes(symbol, market, timeframe, ts, open, high, low, close, volume)
    symbol+market+timeframe+ts 唯一。upsert 增量更新。
    """

    def __init__(self, db_path: str = "data/market.db", parquet_dir: str = "data/parquet"):
        self.db = Path(db_path)
        ensure_dir(str(self.db.parent))
        self.parquet_dir = ensure_dir(parquet_dir)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db) as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS quotes (
                    symbol TEXT, market TEXT, timeframe TEXT, ts TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (symbol, market, timeframe, ts))"""
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_quotes_sm "
                "ON quotes(symbol, market, timeframe)"
            )

    def upsert(self, df: pd.DataFrame, symbol: str, market: str, timeframe: str) -> int:
        """写入/更新行情；返回新增行数。df 需含 DatetimeIndex 与 OHLCV 列。"""
        df = df.copy()
        df.index.name = "ts"
        df = df.reset_index()
        df["ts"] = pd.to_datetime(df["ts"]).astype(str)
        df["symbol"], df["market"], df["timeframe"] = symbol, market, timeframe
        cols = ["symbol", "market", "timeframe", "ts", "open", "high", "low", "close", "volume"]
        recs = df[cols].to_dict("records")
        n = 0
        with sqlite3.connect(self.db) as con:
            for r in recs:
                cur = con.execute(
                    """INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(symbol,market,timeframe,ts) DO UPDATE SET
                       open=excluded.open, high=excluded.high, low=excluded.low,
                       close=excluded.close, volume=excluded.volume""",
                    tuple(r[c] for c in cols),
                )
                n += cur.rowcount
        # 同时落 parquet 备用
        try:
            df[cols].to_parquet(self.parquet_dir / f"{market}_{symbol}_{timeframe}.parquet")
        except Exception:
            pass
        return n

    def query(self, symbol: str, market: str, timeframe: str,
              start=None, end=None) -> pd.DataFrame:
        q = ("SELECT ts,open,high,low,close,volume FROM quotes "
             "WHERE symbol=? AND market=? AND timeframe=?")
        params = [symbol, market, timeframe]
        if start:
            q += " AND ts>=?"
            params.append(str(start))
        if end:
            q += " AND ts<=?"
            params.append(str(end))
        q += " ORDER BY ts"
        with sqlite3.connect(self.db) as con:
            df = pd.read_sql_query(q, con, params=params)
        df["ts"] = pd.to_datetime(df["ts"])
        return df.set_index("ts")

    def coverage(self, symbol: str, market: str, timeframe: str) -> tuple[str, str, int]:
        with sqlite3.connect(self.db) as con:
            row = con.execute(
                "SELECT MIN(ts), MAX(ts), COUNT(*) FROM quotes "
                "WHERE symbol=? AND market=? AND timeframe=?",
                (symbol, market, timeframe),
            ).fetchone()
        return (row[0], row[1], row[2] or 0)
