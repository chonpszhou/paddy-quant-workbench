"""加密货币行情提供方 (Binance 公开 REST API, 无需密钥)。"""
from __future__ import annotations

import pandas as pd

from .base import BaseProvider
from ...utils.common import tf_to_binance_interval

_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"


class BinanceProvider(BaseProvider):
    market = "crypto"

    def __init__(self, quote_asset: str = "USDT"):
        self.quote = quote_asset.upper()

    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        try:
            import requests
        except ImportError:
            raise RuntimeError("未安装 requests: pip install requests")
        sym = symbol.upper()
        pair = sym if sym.endswith(self.quote) else f"{sym}{self.quote}"

        params = {
            "symbol": pair,
            "interval": tf_to_binance_interval(timeframe),
            "limit": min(int(limit), 1000),
        }
        try:
            r = requests.get(_BINANCE_KLINES, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return self._empty()

        if not isinstance(data, list) or not data:
            return self._empty()

        rows = []
        for k in data:
            ts = pd.to_datetime(int(k[0]), unit="ms", utc=True)
            rows.append([ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])

        df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
        df = df.set_index("datetime").sort_index()
        return df
