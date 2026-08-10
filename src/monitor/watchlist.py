"""关注列表管理 (JSON 持久化)。"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.common import load_settings, PROJECT_ROOT


class Watchlist:
    def __init__(self, path: str | None = None):
        self.settings = load_settings()
        self.path = Path(path) if path else PROJECT_ROOT / self.settings["watchlist_path"]
        self.items = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, symbol: str, market: str = "us", note: str = "") -> bool:
        if any(i["symbol"] == symbol and i["market"] == market for i in self.items):
            return False
        self.items.append({"symbol": symbol, "market": market, "note": note})
        self._save()
        return True

    def remove(self, symbol: str, market: str = "us") -> bool:
        before = len(self.items)
        self.items = [
            i for i in self.items if not (i["symbol"] == symbol and i["market"] == market)
        ]
        if len(self.items) != before:
            self._save()
            return True
        return False

    def list(self) -> list:
        return self.items
