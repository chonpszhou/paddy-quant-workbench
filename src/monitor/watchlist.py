"""关注列表管理 (JSON 持久化), 支持自选分组。

数据模型: 每个条目 {symbol, market, note, group}。
group 缺省为 "默认"; 旧版无 group 字段的条目在加载时自动补齐。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.common import load_settings, PROJECT_ROOT

DEFAULT_GROUP = "默认"


class Watchlist:
    def __init__(self, path: str | None = None):
        self.settings = load_settings()
        self.path = Path(path) if path else PROJECT_ROOT / self.settings["watchlist_path"]
        self.items = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                # 兼容旧版无 group 字段
                for it in raw:
                    it.setdefault("group", DEFAULT_GROUP)
                return raw
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def groups(self) -> list:
        """返回去重且有序的分组名列表 (至少含 "默认")。"""
        seen: list[str] = []
        for it in self.items:
            g = it.get("group", DEFAULT_GROUP)
            if g not in seen:
                seen.append(g)
        if not seen:
            seen.append(DEFAULT_GROUP)
        return seen

    def add(self, symbol: str, market: str = "us", note: str = "",
            group: str = DEFAULT_GROUP) -> bool:
        symbol = symbol.strip().upper()
        group = (group or DEFAULT_GROUP).strip() or DEFAULT_GROUP
        if any(
            i["symbol"] == symbol and i["market"] == market
            and i.get("group", DEFAULT_GROUP) == group
            for i in self.items
        ):
            return False
        self.items.append({"symbol": symbol, "market": market, "note": note, "group": group})
        self._save()
        return True

    def remove(self, symbol: str, market: str = "us", group: str | None = None) -> bool:
        symbol = symbol.strip().upper()
        before = len(self.items)
        self.items = [
            i for i in self.items
            if not (
                i["symbol"] == symbol and i["market"] == market
                and (group is None or i.get("group", DEFAULT_GROUP) == group)
            )
        ]
        if len(self.items) != before:
            self._save()
            return True
        return False

    def list(self, group: str | None = None) -> list:
        if group is None:
            return list(self.items)
        return [i for i in self.items if i.get("group", DEFAULT_GROUP) == group]

    def set_group(self, symbol: str, market: str, new_group: str,
                  old_group: str | None = None) -> bool:
        new_group = (new_group or DEFAULT_GROUP).strip() or DEFAULT_GROUP
        changed = False
        for i in self.items:
            if i["symbol"] == symbol.strip().upper() and i["market"] == market and (
                old_group is None or i.get("group", DEFAULT_GROUP) == old_group
            ):
                i["group"] = new_group
                changed = True
        if changed:
            self._save()
        return changed

    def delete_group(self, group: str) -> bool:
        if group == DEFAULT_GROUP:
            return False
        before = len(self.items)
        self.items = [i for i in self.items if i.get("group", DEFAULT_GROUP) != group]
        if len(self.items) != before:
            self._save()
            return True
        return False
