"""交易日历工具 —— 判断某市场在某日/某时刻是否开市。

用途：
- 回测只在交易日产生信号，避免"周末假突破"式过拟合。
- 调度器只在开市时段触发扫描/下单。
- 四大市场节奏差异大：A股/港股有固定休市与午休；美股有时区；数字货币 7x24。

实现原则：用 stdlib 的 holiday/calendar 推算主要节假日，覆盖常见年份；
如需精确，可接入交易所日历（如 exchange_calendars）做覆盖。
"""
from __future__ import annotations

from datetime import datetime, date, time, timedelta

# 固定节假日（公历，月-日）：四大市场大致重合的部分 + A股特有
_FIXED_HOLIDAYS = {
    (1, 1): "元旦",
    (5, 1): "劳动节",
    (10, 1): "国庆/中秋节(近似)",
    (12, 25): "圣诞(港/美)",
}

# 各市场额外休市判断
_A_SHARE_EXTRA = {
    (1, 1): "元旦", (5, 1): "劳动节", (10, 1): "国庆", (4, 5): "清明(近似)",
    (5, 5): "端午(近似)", (8, 15): "中秋(近似)",
}


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun


def _fixed_holiday(market: str, d: date) -> str | None:
    if market == "a":
        if (d.month, d.day) in _A_SHARE_EXTRA:
            return _A_SHARE_EXTRA[(d.month, d.day)]
    else:
        if (d.month, d.day) in _FIXED_HOLIDAYS:
            return _FIXED_HOLIDAYS[(d.month, d.day)]
    return None


def is_trading_day(market: str, d: date | None = None) -> bool:
    """返回该市场当天是否开市（不含具体时段）。"""
    d = d or date.today()
    if market == "crypto":
        return True  # 7x24
    if _is_weekend(d):
        # 港股/美股周末休；A股周末休
        return False
    if _fixed_holiday(market, d):
        return False
    return True


def market_session(market: str, dt: datetime | None = None) -> str:
    """返回当前时段：pre/open/break(午休)/close/overnight。crypto 恒为 open。"""
    dt = dt or datetime.now()
    if market == "crypto":
        return "open"
    d = dt.date()
    if not is_trading_day(market, d):
        return "close"
    t = dt.time()

    # 各市场常规交易时段（本地时间近似）
    if market == "a":
        morning = (time(9, 30), time(11, 30))
        afternoon = (time(13, 0), time(15, 0))
        if morning[0] <= t <= morning[1]:
            return "open"
        if afternoon[0] <= t <= afternoon[1]:
            return "open"
        if time(11, 30) < t < time(13, 0):
            return "break"
        return "close"
    if market == "hk":
        morning = (time(9, 30), time(12, 0))
        afternoon = (time(13, 0), time(16, 0))
        if morning[0] <= t <= morning[1]:
            return "open"
        if afternoon[0] <= t <= afternoon[1]:
            return "open"
        if time(12, 0) < t < time(13, 0):
            return "break"
        return "close"
    if market == "us":
        # 美股常规 09:30-16:00 ET；此处用 UTC 近似（夏令 13:30-20:00 / 冬令 14:30-21:00）
        # 为简化，按 UTC 13:30-20:00 近似
        if time(13, 30) <= t <= time(20, 0):
            return "open"
        return "close"
    return "close"


def next_trading_day(market: str, d: date | None = None) -> date:
    d = d or date.today()
    while not is_trading_day(market, d):
        d = d + timedelta(days=1)
    return d


def prev_trading_day(market: str, d: date | None = None) -> date:
    d = d or date.today()
    while not is_trading_day(market, d):
        d = d - timedelta(days=1)
    return d
