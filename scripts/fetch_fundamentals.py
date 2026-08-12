"""基本面快照采集器（第四道闸门质量否决的数据入口）。

为什么需要它：quality_filter 只消费「结构化基本面」，但 westock/wind 的原始返回
是嵌套 JSON，且字段名不一致。本脚本把「人工/半自动整理好的基本面清单」落盘为
运行时存储 data/fundamentals/{code}.json，供 optimize / demo 读取。

注意：纯 Python 无法直连 westock MCP（需在 WorkBuddy 对话里调用 data_finance 等），
所以这里采用「manifest 入库」模式——你先把从 westock 整理出的基本面写成 JSON，
再用本脚本转为标准化存储。

用法：
  python scripts/fetch_fundamentals.py --manifest path/to/manifest.json
  # manifest 形如: {"hk09999": {"symbol":"hk09999","name":"网易",...}, ...}
  # 也可只更新单个标的:
  python scripts/fetch_fundamentals.py --manifest one.json --code hk09999
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.quality_filter import Fundamentals  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="基本面快照采集 → data/fundamentals/")
    ap.add_argument("--manifest", required=True, help="基本面清单 JSON 路径")
    ap.add_argument("--code", default=None, help="仅更新该 code（可选）")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    store = ROOT / "data" / "fundamentals"
    store.mkdir(parents=True, exist_ok=True)

    keys = [args.code] if args.code else list(manifest.keys())
    for key in keys:
        if key not in manifest:
            print(f"  ⚠️ manifest 中无 {key}，跳过")
            continue
        f = Fundamentals.from_dict(manifest[key])
        out = store / f"{key}.json"
        out.write_text(json.dumps(f.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ 已存 {key}: {out}")

    print(f"\n完成。运行时存储目录: {store}")
    print("提示：演示/寻优读取的是受版本控制的种子 config/fundamentals/candidates.json；")
    print("      本脚本写入的是运行时存储 data/fundamentals/（被 .gitignore 忽略）。")


if __name__ == "__main__":
    main()
