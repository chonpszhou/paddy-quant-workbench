"""实盘适配器安全层 (LiveBroker) —— 默认绝不发真单。

安全原则（比「默认 testnet」更严格，因为真金白银不可逆）：
1. 除非 settings 显式 live_trading.enabled=True 「且」调用方显式 dry_run=False，
   否则一律走 DRY-RUN：用 PaperBroker 记账 + 记录「本应下的单」，但绝不触碰交易所。
2. 即便 armed（真发单），也只在实例化时惰性导入 ccxt/easytrader，
   且 CLI 端还要求 --i-understand-real-money-risk 显式确认标志。
3. 提供 dry_run_replay()：用历史信号 + 历史行情，模拟「若实盘会如何成交」，
   作为实盘前最后一道沙盘推演。

这是把回测 OS 升级为可交易 OS 的最后一公里，但安全优先于便利。
任何试图「偷偷发单」的代码路径都被双闸门堵死。
"""
from __future__ import annotations

from datetime import datetime

from .base import BrokerAdapter, Order, Fill, Position
from .paper import PaperBroker


class LiveBroker(BrokerAdapter):
    def __init__(self, registry=None, initial_cash: float = 100000,
                 live_enabled: bool = False, dry_run: bool = True,
                 backend: str = "ccxt", backend_kwargs: dict | None = None):
        self.live_enabled = bool(live_enabled)
        self.dry_run = bool(dry_run)
        # 双闸门：必须「配置允许」且「未要求 dry-run」才真正发单
        self.armed = self.live_enabled and (not self.dry_run)
        self.registry = registry
        self.backend_name = backend
        self.backend_kwargs = backend_kwargs or {}
        self.marks: dict[str, float] = {}
        self.dry_orders: list[tuple[Order, Fill]] = []

        if self.armed:
            # 仅在真正要下单时才实例化实盘后端（惰性导入，不污染模拟盘环境）
            if backend == "ccxt":
                from .ccxt_adapter import CcxtBroker
                self.backend: BrokerAdapter = CcxtBroker(
                    registry=registry, **self.backend_kwargs)
            elif backend == "easytrader":
                from .easytrader_adapter import EasytraderBroker
                self.backend = EasytraderBroker(
                    registry=registry, **self.backend_kwargs)
            else:
                raise ValueError(f"未知后端: {backend}")
            self.mode = "LIVE"
        else:
            self.backend = PaperBroker(initial_cash=initial_cash, registry=registry)
            self.mode = "DRY-RUN" if dry_run else "DISABLED"

    # —— 安全状态查询 ——
    def status(self) -> str:
        if self.armed:
            return "🔴 LIVE（真实下单，不可逆）"
        return f"🟢 {self.mode}（未触碰任何交易所）"

    def is_armed(self) -> bool:
        return self.armed

    # —— 接口实现 ——
    def mark(self, symbol: str, price: float) -> None:
        self.marks[symbol] = float(price)
        if hasattr(self.backend, "mark"):
            self.backend.mark(symbol, price)

    def submit_order(self, order: Order) -> Fill | None:
        if self.armed:
            # 真实下单（仅在显式 armed 时可达——双闸门已校验）
            return self.backend.submit_order(order)

        # DRY-RUN：用 PaperBroker 记账 + 记录本应下的单，不触碰交易所
        price = self.marks.get(order.symbol, order.limit_price or 0.0)
        fill = Fill(
            symbol=order.symbol, market=order.market, side=order.side,
            qty=float(order.qty), price=float(price), fee=0.0,
            ts=datetime.now().isoformat(timespec="seconds"),
        )
        self.backend.submit_order(order)          # 仅记账（模拟盘）
        self.dry_orders.append((order, fill))     # 留痕
        return fill

    def get_positions(self) -> dict[str, Position]:
        return self.backend.get_positions()

    def get_account(self) -> dict:
        return self.backend.get_account()

    # —— 沙盘推演：历史信号 × 历史行情，模拟若实盘会如何成交 ——
    def dry_run_replay(self, symbol: str, market: str, itype: str,
                       signal: "pd.Series", df: "pd.DataFrame",
                       risk=None, registry=None) -> dict:
        """用历史信号序列 + 历史行情回放（默认 dry-run，绝不发真单）。

        逻辑与 cmd_paper 一致，但通过本适配器执行，使「实盘前推演」与
        「真实盘」共用同一套下单接口——切真盘只需把 armed 打开。
        """
        import pandas as pd  # noqa: F401  (调用方通常已导入，这里兜底)

        spec = (registry or self.registry).get(symbol, market, itype)
        n_entry = n_exit = 0
        for i in range(1, len(df)):
            price = float(df["close"].iloc[i])
            self.mark(symbol, price)
            desired = int(signal.iloc[i])
            cur = self.get_positions().get(symbol)
            cur_qty = cur.qty if cur else 0.0
            if desired != 0 and cur_qty == 0:
                per = spec.multiplier * spec.contract_unit
                qty = (risk.max_position_value() / (price * per)) if risk else (100000 / (price * per))
                qty = spec.round_qty(qty)
                if qty > 0:
                    side = "buy" if desired > 0 else "sell"
                    if self.submit_order(Order(symbol, market, itype, side, qty)):
                        n_entry += 1
            elif desired == 0 and cur_qty != 0:
                side = "sell" if cur_qty > 0 else "buy"
                if self.submit_order(Order(symbol, market, itype, side, abs(cur_qty))):
                    n_exit += 1
        acct = self.get_account()
        return {
            "mode": self.mode,
            "armed": self.armed,
            "n_entry": n_entry,
            "n_exit": n_exit,
            "account": acct,
        }
