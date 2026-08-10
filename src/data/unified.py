"""统一行情接口。

屏蔽市场差异, 对外提供 get(symbol, market, timeframe, limit)。
market: us | hk | crypto
"""
from __future__ import annotations

import pandas as pd

from .providers.yfinance_provider import YFinanceProvider
from .providers.binance_provider import BinanceProvider
from .storage import Storage
from ..utils.common import load_settings


class DataHub:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or load_settings()
        self.storage = Storage(self.settings["data"]["cache_dir"])

        mk = self.settings["markets"]
        self.providers = {
            "us": YFinanceProvider(mk["us"]["symbol_suffix"]),
            "hk": YFinanceProvider(mk["hk"]["symbol_suffix"]),
            "crypto": BinanceProvider(mk["crypto"]["quote_asset"]),
        }

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
        return df
