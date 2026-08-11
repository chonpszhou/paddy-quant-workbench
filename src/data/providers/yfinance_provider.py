"""美股 / 港股行情提供方 (yfinance)。

- 美股: 原始代码, 如 AAPL
- 港股: 数字代码, 自动补零并加 .HK, 如 700 -> 0700.HK
- yfinance 不支持 4h, 内部用 1h 数据 resample 成 4h
"""
from __future__ import annotations

import pandas as pd

from .base import BaseProvider
from ...utils.common import tf_to_yf_interval

# yfinance 各周期可拉取的历史长度上限
_YF_PERIOD = {"15m": "7d", "1h": "2y", "1d": "2y"}


class YFinanceProvider(BaseProvider):
    market = "us_hk"

    def __init__(self, symbol_suffix: str = ""):
        self.symbol_suffix = symbol_suffix

    def _normalize(self, symbol: str) -> str:
        s = symbol.strip().upper()
        if self.symbol_suffix == ".HK":
            core = s.split(".")[0]  # 去掉可能已有的 .HK
            core = core.zfill(4)  # 港股代码补零到 4 位
            return f"{core}.HK"
        return s + self.symbol_suffix

    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            raise RuntimeError("未安装 yfinance: pip install yfinance "
                               "-i https://pypi.tuna.tsinghua.edu.cn/simple")
        ticker = self._normalize(symbol)
        raw_tf = "1h" if timeframe == "4h" else timeframe
        interval = tf_to_yf_interval(raw_tf)
        period = _YF_PERIOD.get(raw_tf, "2y")

        try:
            df = yf.Ticker(ticker).history(
                period=period, interval=interval, auto_adjust=True, actions=False
            )
        except Exception:
            return self._empty()

        if df is None or df.empty:
            return self._empty()

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index = pd.to_datetime(df.index)
        df = df.dropna()

        if timeframe == "4h":
            df = (
                df.resample("4h")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )

        return df.tail(limit)
