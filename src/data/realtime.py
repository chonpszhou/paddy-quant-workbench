"""Binance 实时行情 WebSocket 推送 (加密货币)。

使用 websocket-client 在后台守护线程连接 Binance 合并流(@ticker),
维护最新价格 / 24h 涨跌幅, 供 Streamlit 面板读取。
美股 / 港股依赖 yfinance 延迟数据, 用面板自动刷新轮询即可。
"""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict

try:
    import websocket  # websocket-client
    _HAS_WS = True
except Exception:  # pragma: no cover
    _HAS_WS = False

WS_BASE = "wss://stream.binance.com:9443/stream"


class LiveTicker:
    """单例风格的实时行情管理器 (模块级 _ticker 复用)。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.latest: dict[str, dict] = {}   # 展示符号(大写, 如 BTC) -> 行情
        self._ws = None
        self._thread = None
        self._running = False
        self._symbols: list[str] = []

    @staticmethod
    def _to_pair(sym: str) -> str:
        s = sym.strip().upper()
        if not s.endswith("USDT"):
            s = s + "USDT"
        return s.lower()

    def ensure_running(self, symbols: list[str]) -> list[str]:
        """确保 WS 已启动并订阅给定符号; 返回当前订阅列表。"""
        syms = [s.strip().upper() for s in symbols if s and s.strip()]
        new = [s for s in syms if s not in self._symbols]
        with self._lock:
            if not self._running and _HAS_WS and syms:
                self._symbols = list(syms)
                self._start()
            elif new and self._symbols:
                self._symbols = list(dict.fromkeys(self._symbols + new))
                self._resubscribe()
        return self._symbols

    def _streams(self) -> str:
        return "/".join(f"{self._to_pair(s)}@ticker" for s in self._symbols)

    def _start(self):
        url = f"{WS_BASE}?streams={self._streams()}"
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(url,), daemon=True)
        self._thread.start()

    def _resubscribe(self):
        self._running = False
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        if _HAS_WS and self._symbols:
            self._start()

    def _run(self, url):
        try:
            self._ws = websocket.WebSocketApp(
                url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self._ws.run_forever()
        except Exception:  # pragma: no cover
            self._running = False

    def _on_message(self, ws, msg):
        try:
            obj = json.loads(msg)
            d = obj.get("data", {})
            pair = d.get("s")  # 例如 BTCUSDT
            if not pair:
                return
            sym = pair.replace("USDT", "").upper()
            with self._lock:
                self.latest[sym] = {
                    "price": float(d.get("c", 0)),
                    "change_pct": float(d.get("P", 0)),
                    "high": float(d.get("h", 0)),
                    "low": float(d.get("l", 0)),
                    "ts": time.time(),
                }
        except Exception:  # pragma: no cover
            pass

    def _on_error(self, ws, err):  # pragma: no cover
        self._running = False

    def _on_close(self, ws, *a):  # pragma: no cover
        self._running = False

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.latest)

    def status(self) -> dict:
        return {
            "running": self._running,
            "has_ws": _HAS_WS,
            "symbols": list(self._symbols),
        }


_ticker = LiveTicker()


def get_live_ticker() -> LiveTicker:
    return _ticker
