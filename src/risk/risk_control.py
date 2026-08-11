"""风控最小集 —— 量化交易操作系统的安全底座。

设计原则（来自用户规划 + 龙源体系 + Kova 四原则）：
- 风控代码与策略代码分离、独立评审。
- 任何策略在实盘前必须套用本模块，不可绕过。
- 目标不是"赚最多"，而是"活得久 + 回撤可控"——这是长期正期望的前提。

所有阈值可由 config/settings.yaml 的 risk 段覆盖；小白向导会基于风险问卷自动生成。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskConfig:
    # —— 仓位上限（占总资产比例）——
    max_single_position_pct: float = 0.02   # 单笔 ≤ 2%（规划硬门槛）
    max_strategy_position_pct: float = 0.30  # 单策略 ≤ 30%
    max_total_position_pct: float = 0.50    # 总开仓 ≤ 50%（龙源体系）

    # —— 止损 ——
    stop_loss_pct: float = 0.03             # 单笔固定止损 -3%
    use_atr_stop: bool = True               # 同时用 ATR 止损，取较宽（更严格）者
    atr_stop_multiplier: float = 1.5
    breakeven_at_profit_pct: float = 0.06   # 浮盈 ≥ +6% → 止损移至保本

    # —— 熔断 ——
    daily_loss_circuit_pct: float = 0.05    # 单日亏损 -5% → 暂停当日交易
    max_drawdown_circuit_pct: float = 0.20  # 总回撤 -20% → 全面暂停

    # —— 凯利（保守版）——
    kelly_fraction: float = 0.5             # 仅用半凯利或更保守

    # —— 执行纪律 ——
    no_chase_on_disconnect: bool = True     # 断线不追单


@dataclass
class PositionState:
    symbol: str
    qty: float
    entry_price: float
    current_price: float = 0.0
    atr: float = 0.0
    highest_since_entry: float = 0.0
    stop_price: float = 0.0
    side: str = "long"


class RiskController:
    """可复用、可测试的风控引擎。策略层在开仓/持仓/收盘时调用。"""

    def __init__(self, cfg: RiskConfig | None = None, total_equity: float = 100000.0):
        self.cfg = cfg or RiskConfig()
        self.equity = total_equity
        self.peak_equity = total_equity
        self.daily_pnl_pct = 0.0
        self.positions: dict[str, PositionState] = {}

    # —— 仓位校验 ——
    def max_position_value(self) -> float:
        return self.equity * self.cfg.max_single_position_pct

    def proposed_size_ok(self, symbol: str, proposed_value: float,
                         strategy_used_pct: float = 0.0) -> tuple[bool, str]:
        if proposed_value > self.max_position_value():
            return False, (f"单笔仓位 {proposed_value:,.0f} 超过上限 "
                           f"{self.max_position_value():,.0f} (= {self.cfg.max_single_position_pct*100:.0f}%)")
        total = sum(p.qty * p.current_price for p in self.positions.values()) + proposed_value
        if total > self.equity * self.cfg.max_total_position_pct:
            return False, f"总开仓将超过上限 {self.cfg.max_total_position_pct*100:.0f}%"
        if strategy_used_pct + (proposed_value / self.equity) > self.cfg.max_strategy_position_pct:
            return False, f"单策略仓位将超过上限 {self.cfg.max_strategy_position_pct*100:.0f}%"
        return True, "OK"

    # —— 止损 / 保本移动 ——
    def compute_stop(self, pos: PositionState) -> float:
        fixed = pos.entry_price * (1 - self.cfg.stop_loss_pct)
        stop = fixed
        if self.cfg.use_atr_stop and pos.atr > 0:
            atr_stop = pos.entry_price - pos.atr * self.cfg.atr_stop_multiplier
            stop = min(stop, atr_stop)  # 取更严格的（更低）
        if pos.highest_since_entry >= pos.entry_price * (1 + self.cfg.breakeven_at_profit_pct):
            stop = max(stop, pos.entry_price)  # 浮盈达标 → 移至保本
        return stop

    def check_exit(self, pos: PositionState) -> tuple[bool, str]:
        stop = self.compute_stop(pos)
        if pos.current_price <= stop:
            return True, f"触发止损 {stop:.4f}"
        return False, ""

    # —— 熔断 ——
    def register_daily_pnl(self, pnl_pct: float) -> None:
        self.daily_pnl_pct = pnl_pct

    def daily_circuit_triggered(self) -> bool:
        return self.daily_pnl_pct <= -self.cfg.daily_loss_circuit_pct

    def update_equity(self, equity: float) -> None:
        self.equity = equity
        self.peak_equity = max(self.peak_equity, equity)

    def drawdown_circuit_triggered(self) -> bool:
        dd = (self.equity - self.peak_equity) / (self.peak_equity + 1e-12)
        return dd <= -self.cfg.max_drawdown_circuit_pct

    # —— 凯利保守仓位 ——
    def kelly_fraction_value(self, win_rate: float, payoff_ratio: float) -> float:
        """返回建议仓位比例（已乘保守系数）。win_rate/payoff_ratio 来自样本外回测。"""
        if payoff_ratio <= 0:
            return 0.0
        f = win_rate - (1 - win_rate) / payoff_ratio
        f = max(0.0, f)
        return min(f * self.cfg.kelly_fraction, self.cfg.max_single_position_pct)

    def summary(self) -> dict:
        return {
            "max_single_position_pct": self.cfg.max_single_position_pct,
            "max_strategy_position_pct": self.cfg.max_strategy_position_pct,
            "max_total_position_pct": self.cfg.max_total_position_pct,
            "stop_loss_pct": self.cfg.stop_loss_pct,
            "daily_loss_circuit_pct": self.cfg.daily_loss_circuit_pct,
            "max_drawdown_circuit_pct": self.cfg.max_drawdown_circuit_pct,
        }
