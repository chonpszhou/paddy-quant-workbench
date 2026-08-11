"""A股实盘适配器 (基于 easytrader，对接券商客户端)。

⚠️ 实盘有真金白银风险。默认不启用。easytrader 需要本机运行券商客户端
（如 同花顺/东方财富），并读取客户端窗体——仅适合本机部署，不适合云端沙箱。

使用方式：
  from src.broker.easytrader_adapter import EasytraderBroker
  b = EasytraderBroker(client="ths", account="...", password="...")
  b.submit_order(Order("600519", "a", "spot", "buy", 100))
"""
from __future__ import annotations

from .base import BrokerAdapter, Order, Fill, Position


class EasytraderBroker(BrokerAdapter):
    def __init__(self, client: str = "ths", account: str = "", password: str = "",
                 registry=None):
        try:
            import easytrader  # 仅在实例化时导入
        except ImportError as e:
            raise RuntimeError(
                "未安装 easytrader，无法使用 A股实盘适配器。\n"
                "请本机 `pip install easytrader` 并安装对应券商客户端。"
            ) from e
        self._user = easytrader.use(client)  # ths / yh / gf ...
        if account:
            self._user.connect(account=account, password=password)
        self.registry = registry

    def submit_order(self, order: Order) -> Fill | None:
        # easytrader 以股数下单；A股不可碎股，已向下取整
        vol = int(order.qty)
        if order.side == "buy":
            self._user.buy(order.symbol, price=order.limit_price, volume=vol)
        else:
            self._user.sell(order.symbol, price=order.limit_price, volume=vol)
        return Fill(symbol=order.symbol, market="a", side=order.side,
                   qty=vol, price=order.limit_price or 0.0, fee=0.0, ts="")

    def get_positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self._user.position:
            out[p["stock_code"]] = Position(
                symbol=p["stock_code"], qty=float(p["current_amount"]),
                avg_price=float(p.get("cost_price", 0.0)), market="a", itype="spot",
            )
        return out

    def get_account(self) -> dict:
        bal = self._user.balance
        eq = float(bal.get("asset_balance", 0.0))
        return {"cash": float(bal.get("current_balance", 0.0)), "margin_used": 0.0,
                "equity": eq, "realized_pnl": 0.0, "unrealized_pnl": 0.0,
                "initial_cash": eq}
