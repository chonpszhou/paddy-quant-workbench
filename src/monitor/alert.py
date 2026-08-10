"""告警引擎: 扫描关注列表, 输出买卖点 / 异常换手异动。"""
from __future__ import annotations

from ..data.unified import DataHub
from ..engine.signals import SignalEngine


class AlertEngine:
    def __init__(self):
        self.hub = DataHub()
        self.sig = SignalEngine()

    def scan(self, watchlist: list, timeframes: list | None = None) -> list:
        if timeframes is None:
            timeframes = ["1d"]

        alerts = []
        for item in watchlist:
            symbol = item["symbol"]
            market = item.get("market", "us")
            for tf in timeframes:
                df = self.hub.get(symbol, market, tf, limit=120)
                if df is None or df.empty:
                    continue
                _, extra = self.sig.analyze(df, tf)
                if extra["signal"] in ("BUY", "SELL"):
                    alerts.append({
                        "symbol": symbol, "market": market, "timeframe": tf,
                        "type": extra["signal"], "close": extra["close"],
                        "note": item.get("note", ""),
                    })
                if extra.get("anomaly_vol"):
                    alerts.append({
                        "symbol": symbol, "market": market, "timeframe": tf,
                        "type": "ANOMALY_VOL", "close": extra["close"],
                        "vol_z": round(extra["vol_z"], 2),
                        "note": item.get("note", ""),
                    })
        return alerts
