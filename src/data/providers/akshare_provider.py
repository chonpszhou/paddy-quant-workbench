"""A股数据接入 (akshare 免费接口) —— 补齐四市场最大缺口。

统一输出列：open/high/low/close/volume，DatetimeIndex。
已实现：6 位代码归一化、前复权(默认)、中文列映射、基础缺失处理。
"""
from __future__ import annotations

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


def normalize_a_symbol(code: str) -> str:
    """支持 600519 / sh600519 / 600519.SH / 600519.XSHG 多种写法。"""
    s = code.strip().upper()
    for prefix in ("SH", "SZ", "XSHG", "XSHE", "."):
        s = s.replace(prefix, "")
    return s[:6]


def get_a_history(code: str, period: str = "daily", adjust: str = "qfq",
                  years: int = 3) -> pd.DataFrame:
    """获取 A股历史 K 线。adjust='qfq' 前复权 / 'hfq' 后复权 / '' 不复权。"""
    if ak is None:
        raise RuntimeError(
            "未安装 akshare，请先: pip install akshare "
            "-i https://pypi.tuna.tsinghua.edu.cn/simple"
        )
    symbol = normalize_a_symbol(code)
    df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust=adjust)
    if df is None or df.empty:
        raise ValueError(f"未取到 {symbol} 数据（可能退市或代码错误）")
    rename = {
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume",
    }
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    # 基础清洗：去重、缺失向前填充
    df = df[~df.index.duplicated(keep="last")]
    df = df.ffill().dropna()
    return df


class AkshareProvider:
    """与 YFinanceProvider / BinanceProvider 同接口，便于 DataHub 统一调度。"""

    _TF_MAP = {"1d": "daily", "1w": "weekly", "1mo": "monthly",
               "daily": "daily", "weekly": "weekly", "monthly": "monthly"}

    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        period = self._TF_MAP.get(timeframe, "daily")
        # 用 limit 反推需要的年数（akshare 按区间拉，多拉一点无妨）
        years = max(1, -(-limit // 252) + 1)
        df = get_a_history(symbol, period=period, adjust="qfq", years=years)
        return df.tail(limit)
