"""执行层 (Broker) 包。

- base: BrokerAdapter 抽象接口（所有执行器共用）
- paper: 模拟盘（默认训练场，现货/期货/ETF/多空）
- ccxt_adapter: 数字货币实盘（需 ccxt，lazy import）
- easytrader_adapter: A股实盘（需 easytrader，lazy import）
"""
from .base import BrokerAdapter, Order, Fill, Position
from .paper import PaperBroker

__all__ = ["BrokerAdapter", "Order", "Fill", "Position", "PaperBroker"]
