"""数字货币实盘适配器 (基于 ccxt)。

⚠️ 实盘有真金白银风险。默认不启用，需在 config/settings.yaml 显式打开 live_trading，
且建议先用 PaperBroker 跑满 30 天模拟盘 + walk-forward 通过后再切。

使用方式：
  from src.broker.ccxt_adapter import CcxtBroker
  b = CcxtBroker(exchange="binance", api_key=..., secret=..., testnet=True)
  b.submit_order(Order("BTC/USDT", "crypto", "future", "buy", 0.01))
"""
from __future__ import annotations

from .base import BrokerAdapter, Order, Fill, Position


class CcxtBroker(BrokerAdapter):
    def __init__(self, exchange: str = "binance", api_key: str = "", secret: str = "",
                 testnet: bool = True, registry=None):
        try:
            import ccxt  # 仅在实例化时导入，缺失不污染回测/模拟盘环境
        except ImportError as e:
            raise RuntimeError(
                "未安装 ccxt，无法使用数字货币实盘适配器。\n"
                "请先 `pip install ccxt`，或继续用 PaperBroker 模拟盘。"
            ) from e
        self._ccxt = ccxt
        self.exchange = getattr(ccxt, exchange)({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"} if exchange == "binance" else {},
        })
        if testnet and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)
        self.registry = registry

    def submit_order(self, order: Order) -> Fill | None:
        side = "buy" if order.side == "buy" else "sell"
        params = {}
        if order.itype == "future":
            params["reduceOnly"] = False
        resp = self.exchange.create_order(
            symbol=order.symbol, type="market", side=side,
            amount=order.qty, params=params,
        )
        price = float(resp.get("average") or resp["price"])
        return Fill(symbol=order.symbol, market="crypto", side=order.side,
                   qty=float(resp["amount"]), price=price,
                   fee=float(resp.get("fee", {}).get("cost", 0.0)), ts=resp.get("datetime", ""))

    def get_positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self.exchange.fetch_positions():
            if float(p.get("contracts", 0) or 0) == 0:
                continue
            out[p["symbol"]] = Position(
                symbol=p["symbol"], qty=float(p["contracts"]),
                avg_price=float(p.get("entryPrice") or 0.0), market="crypto",
                itype="future",
            )
        return out

    def get_account(self) -> dict:
        bal = self.exchange.fetch_balance()
        eq = float(bal.get("USDT", {}).get("total", 0.0))
        return {"cash": eq, "margin_used": 0.0, "equity": eq,
                "realized_pnl": 0.0, "unrealized_pnl": 0.0,
                "initial_cash": eq}
