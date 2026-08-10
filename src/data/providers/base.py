"""行情数据提供方基类。

所有市场的 provider 都统一返回 pandas.DataFrame:
    index : DatetimeIndex (按时间升序)
    columns: open, high, low, close, volume
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseProvider(ABC):
    """行情数据提供方抽象基类。"""

    market: str = "base"

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        """获取 OHLCV 行情。

        Args:
            symbol: 标的代码 (不带市场后缀的原始代码, 如 AAPL / 0700 / BTC)
            timeframe: 周期, 支持 1d/4h/1h/15m
            limit: K 线数量

        Returns:
            含 open/high/low/close/volume 的 DataFrame, 以时间升序索引
        """
        raise NotImplementedError

    @staticmethod
    def _empty() -> pd.DataFrame:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
