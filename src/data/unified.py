"""统一行情接口。

屏蔽市场差异, 对外提供 get(symbol, market, timeframe, limit)。
market: us | hk | crypto
"""
from __future__ import annotations

import pandas as pd

from .providers.yfinance_provider import YFinanceProvider
from .providers.binance_provider import BinanceProvider
from .providers.akshare_provider import AkshareProvider
from .storage import Storage, SQLStore
from ..utils.common import load_settings


class DataHub:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or load_settings()
        self.storage = Storage(self.settings["data"]["cache_dir"])
        # 历史数据落库（规划优先级 #1）：每次取到的新数据增量写入 SQLite
        db_path = self.settings["data"].get("sql_db", "data/market.db")
        self.sql = SQLStore(db_path)

        mk = self.settings["markets"]
        self.providers = {
            "us": YFinanceProvider(mk["us"]["symbol_suffix"]),
            "hk": YFinanceProvider(mk["hk"]["symbol_suffix"]),
            "crypto": BinanceProvider(mk["crypto"]["quote_asset"]),
        }
        # A股（akshare）按需注册：配置里声明了 a 市场才启用
        if "a" in mk:
            self.providers["a"] = AkshareProvider()

    def get(self, symbol: str, market: str = "us", timeframe: str = "1d",
            limit: int = 200, use_cache: bool = True) -> pd.DataFrame:
        if market not in self.providers:
            raise ValueError(f"不支持的市场: {market}, 可选 {list(self.providers)}")

        key = f"{market}_{symbol}_{timeframe}"
        if use_cache and self.settings["data"]["use_cache"]:
            cached = self.storage.load(key)
            if cached is not None and not cached.empty:
                return cached.tail(limit)

        df = self.providers[market].get_ohlcv(symbol, timeframe, limit)
        if not df.empty:
            self.storage.save(key, df)
            # 落库（失败不影响取数）
            try:
                self.sql.upsert(df, symbol, market, timeframe)
            except Exception:
                pass
        return df
