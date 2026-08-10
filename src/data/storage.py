"""本地行情缓存 (parquet)。"""
from __future__ import annotations

import pandas as pd

from ..utils.common import ensure_dir


class Storage:
    def __init__(self, cache_dir: str):
        self.dir = ensure_dir(cache_dir)

    def _path(self, key: str):
        safe = key.replace("/", "_").replace(":", "_")
        return self.dir / f"{safe}.parquet"

    def save(self, key: str, df: pd.DataFrame) -> None:
        try:
            df.to_parquet(self._path(key))
        except Exception:
            pass  # 缓存失败不影响主流程

    def load(self, key: str) -> pd.DataFrame | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            return None
