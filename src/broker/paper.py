"""模拟盘执行器 (Paper Trading Broker)。

- 支持现货/期货/ETF，支持做多、做空、平多、平空。
- 现货按全额现金结算；期货按保证金占用（margin_required）。
- 逐日盯市（mark-to-market），equity = 现金 + 浮盈浮亏。
- 所有成交即时返回 Fill；不做撮合延时（回测用）。

这是实盘前唯一允许的训练场：先在模拟盘把策略+风控跑顺，再切 ccxt/easytrader。
"""
from __future__ import annotations

from datetime import datetime

from .base import BrokerAdapter, Order, Fill, Position
from ..engine.instruments import InstrumentRegistry


class PaperBroker(BrokerAdapter):
    def __init__(self, initial_cash: float = 100000.0,
                 registry: InstrumentRegistry | None = None):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.registry = registry or InstrumentRegistry()
        self.positions: dict[str, Position] = {}
        self.marks: dict[str, float] = {}
        self.realized_pnl = 0.0
        self.fills: list[Fill] = []

    # ------------------------------------------------------------------
    def mark(self, symbol: str, price: float) -> None:
        self.marks[symbol] = price

    def _margin(self, pos: Position) -> float:
        spec = self.registry.get(pos.symbol, pos.market, pos.itype)
        return spec.margin_required(abs(pos.qty), pos.avg_price)

    def margin_used(self) -> float:
        return sum(self._margin(p) for p in self.positions.values())

    def unrealized(self) -> float:
        tot = 0.0
        for sym, pos in self.positions.items():
            price = self.marks.get(sym)
            if price is None or pos.qty == 0:
                continue
            spec = self.registry.get(pos.symbol, pos.market, pos.itype)
            per = spec.multiplier * spec.contract_unit
            tot += pos.qty * (price - pos.avg_price) * per
        return tot

    def equity(self) -> float:
        return self.cash + self.unrealized()

    # ------------------------------------------------------------------
    def submit_order(self, order: Order) -> Fill | None:
        spec = self.registry.get(order.symbol, order.market, order.itype)
        ok, msg = spec.validate_order(order.qty, order.side)
        if not ok:
            return None
        price = order.limit_price if order.limit_price else self.marks.get(order.symbol)
        if price is None or price <= 0:
            return None

        qty = spec.round_qty(order.qty)
        if qty <= 0:
            return None
        delta = qty if order.side == "buy" else -qty   # 带符号的仓位变化
        fee = spec.trade_cost(qty, price)

        pos = self.positions.get(order.symbol)
        old_qty = pos.qty if pos else 0.0
        old_avg = pos.avg_price if pos else 0.0
        per = spec.multiplier * spec.contract_unit

        # —— 已实现盈亏（平仓/减仓部分）——
        realized = 0.0
        if pos and old_qty != 0 and delta * old_qty < 0:
            close_qty = min(abs(delta), abs(old_qty))
            realized = close_qty * (price - old_avg) * (1 if old_qty > 0 else -1) * per

        # —— 更新持仓数量与均价 ——
        new_qty = old_qty + delta
        if abs(new_qty) < 1e-12:
            # 清空
            self.positions.pop(order.symbol, None)
        else:
            if pos is None:
                pos = Position(symbol=order.symbol, qty=0.0, avg_price=price,
                               market=order.market, itype=order.itype)
                self.positions[order.symbol] = pos
            # 同方向加仓才改均价；减仓/平仓不改
            if (old_qty == 0) or (delta * old_qty > 0):
                pos.avg_price = (abs(old_qty) * old_avg + qty * price) / (abs(old_qty) + qty)
            pos.qty = new_qty
            pos.realized_pnl += realized

        # —— 现金/保证金变动 ——
        notional = spec.notional(qty, price)
        if spec.is_leveraged:
            # 期货：按保证金占用变动 + 已实现盈亏 + 费用
            new_margin = self._margin(pos) if pos else 0.0
            old_margin = spec.margin_required(abs(old_qty), old_avg) if old_qty else 0.0
            self.cash += realized - fee - (new_margin - old_margin)
        else:
            # 现货/ETF：开仓按名义额收付现金（买付卖收）；已实现盈亏单独计入。
            # 注意：notional 已含 qty，不能再乘 delta，否则"买入持有到期"会多扣 qty 倍现金，
            # 导致 equity 错算（仅在买卖往返时才恰好抵消，故需持仓到期测试才能发现）。
            cash_flow = -notional if delta > 0 else notional
            self.cash += cash_flow - fee + realized

        self.realized_pnl += realized
        fill = Fill(symbol=order.symbol, market=order.market, side=order.side,
                   qty=qty, price=price, fee=fee,
                   ts=datetime.now().isoformat(timespec="seconds"))
        self.fills.append(fill)
        return fill

    # ------------------------------------------------------------------
    def get_positions(self) -> dict[str, Position]:
        return {k: v for k, v in self.positions.items() if abs(v.qty) > 1e-12}

    def get_account(self) -> dict:
        return {
            "cash": self.cash,
            "margin_used": self.margin_used(),
            "equity": self.equity(),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized(),
            "initial_cash": self.initial_cash,
        }
