#!/usr/bin/env python3
"""拉取 westock 港股/美股 K 线，写入 data/real/_raw/{market}_{symbol}.json。

注意: westock code 格式
  港股: hk + 5位代码 (如 00700 -> hk00700, 无下划线)
  美股: us + TICKER   (如 AAPL -> usAAPL, BRK.B -> usBRK.B)

落库命名仍用 data/real/{market}_{symbol}_1d.parquet (market= hk/us, 有下划线)。

本脚本只负责把 MCP data_kline 的返回 JSON 存盘，避免长 JSON 粘进对话。
调用方式: 由 Agent 逐个 DeferExecuteTool 调用 data_kline 后，把返回文本
写入 _raw 目录；或本脚本预留 BATCH 由外部注入。

为自动化，这里改为: 读取 _raw_fetch_jobs.txt (每行 westock_code<TAB>market<TAB>symbol)
然后逐个通过 stdin 传入的 JSON 落盘 —— 但 MCP 调用要在对话内完成。
因此实际流程见 fetch_westock_batch 的说明，本文件仅作占位/清单。
"""
from __future__ import annotations

# 扩池清单 (market, symbol, westock_code)
BATCH = [
    ("hk", "01299", "hk01299"),   # 友邦保险
    ("hk", "01024", "hk01024"),   # 快手
    ("hk", "02318", "hk02318"),   # 中国平安
    ("hk", "01211", "hk01211"),   # 比亚迪
    ("hk", "09961", "hk09961"),   # 携程
    ("us", "BRK.B", "usBRK.B"),   # 伯克希尔
    ("us", "V", "usV"),           # Visa
    ("us", "UNH", "usUNH"),       # 联合健康
    ("us", "XOM", "usXOM"),       # 埃克森美孚
    ("us", "BAC", "usBAC"),       # 美国银行
]

if __name__ == "__main__":
    for market, symbol, code in BATCH:
        print(f"{code}\t{market}\t{symbol}")
