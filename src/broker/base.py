"""券商/执行适配器抽象层 (Broker Adapter)。

设计意图：
- 策略与风控只产生"买/卖意图"，真正下单由 Broker 适配器完成。
- 模拟盘(PaperBroker)与实盘(ccxt/easytrader 适配器)实现同一接口，
  因此"先在模拟盘打磨、再切实盘"只需换一个适配器，策略代码零改动。
- 这是把回测 OS 升级为可交易 OS 的最后一公里。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Order:
    symbol: str
    market: str
    itype: str = "spot"          # spot / future / etf
    side: str = "buy"            # buy / sell（卖出含平多/开空）
    qty: float = 0.0
    limit_price: float | None = None
    note: str = ""


@dataclass
class Fill:
    symbol: str
    market: str
    side: str
    qty: float
    price: float
    fee: float
    ts: str


@dataclass
class Position:
    symbol: str
    qty: float                   # 正=多仓, 负=空仓
    avg_price: float
    market: str = ""
    itype: str = "spot"
    realized_pnl: float = 0.0


class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> Fill | None:
        """提交订单，返回成交回报（模拟盘立即成交；实盘返回实际成交）。"""

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """返回当前持仓（symbol -> Position）。"""

    @abstractmethod
    def get_account(self) -> dict:
        """返回账户快照：cash / margin_used / equity / realized_pnl。"""

    def mark(self, symbol: str, price: float) -> None:
        """更新标的的最新市价（用于逐日盯市与模拟盘成交）。

        实盘适配器通常从行情源自动更新，模拟盘由回测/调度器驱动。
        """
        raise NotImplementedError
