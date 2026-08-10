"""实时价格预警 (JSON 持久化)。

规则: 对某个标的设置 价格 或 24h涨跌幅 的 上破/下破 阈值,
结合实时快照 (LiveTicker.snapshot()) 评估是否触发。

snapshot 键为展示符号(大写, 去 USDT), 如 "BTC" -> {price, change_pct, ...}。
"""
from __future__ import annotations

import json
import time
import uuid
import warnings
from pathlib import Path

from ..utils.common import load_settings, PROJECT_ROOT, resolve_data_path


class PriceAlert:
    def __init__(self, path: str | None = None):
        self.settings = load_settings()
        self.path = Path(path) if path else resolve_data_path(
            self.settings.get("price_alert_path", "data/price_alerts.json")
        )
        self.rules = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        # 云端应用目录可能只读; 保存失败仅降级为内存, 不崩溃 App
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.rules, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as e:
            warnings.warn(f"价格预警保存失败(只读环境?), 本次改动仅内存生效: {e}")

    @staticmethod
    def _norm(sym: str) -> str:
        s = sym.strip().upper()
        if s.endswith("USDT"):
            s = s[:-4]
        return s

    def add(self, symbol: str, market: str = "crypto", field: str = "price",
            direction: str = "above", threshold: float = 0.0, note: str = "") -> dict:
        rule = {
            "id": uuid.uuid4().hex[:8],
            "symbol": self._norm(symbol),
            "market": market,
            "field": field,          # price | change_pct
            "direction": direction,  # above | below
            "threshold": float(threshold),
            "note": note,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.rules.append(rule)
        self._save()
        return rule

    def remove(self, rule_id: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r["id"] != rule_id]
        if len(self.rules) != before:
            self._save()
            return True
        return False

    def list(self) -> list:
        return list(self.rules)

    def evaluate(self, snapshot: dict) -> list:
        """snapshot: 展示符号(大写, 去 USDT) -> {price, change_pct, ...}。

        返回当前已触发的规则副本 (附带当前值 cur 与评估时刻 ts)。
        无实时数据的标的自动跳过。
        """
        triggered: list[dict] = []
        for r in self.rules:
            live = snapshot.get(r["symbol"])
            if not live:
                continue
            val = live.get(r["field"])
            if val is None:
                continue
            hit = (r["direction"] == "above" and val >= r["threshold"]) or \
                  (r["direction"] == "below" and val <= r["threshold"])
            if hit:
                rec = dict(r)
                rec["cur"] = round(val, 4)
                rec["ts"] = time.time()
                triggered.append(rec)
        return triggered
