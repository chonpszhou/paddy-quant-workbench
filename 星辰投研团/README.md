# 星辰投研团

跨 A股 / 港股 / 美股 / 虚拟货币 / 期权 的多市场投研监控项目骨架。

## 目录结构

```
星辰投研团/
├── config/
│   ├── sources.yaml        # 数据源配置（行情/财务/期权，含主备通道）
│   ├── push.yaml           # 推送通道配置（邮件 + IM 机器人）
│   ├── watchlist.json      # 默认自选股清单（结构化，可直接导入）
│   ├── watchlist.csv       # 同上，CSV 版（Excel 可直接打开）
│   └── tasks.yaml          # 自动化定时分析任务配置建议
├── scripts/
│   └── check_connections.py # 数据源与推送通道连通性检查
├── docs/
│   ├── 连接检查报告.md       # 带状态标识的连接检查清单（运行脚本自动生成）
│   ├── 连接检查结果.json
│   └── 量化交易GitHub顶级项目学习笔记.md  # GitHub Top50 量化项目研读
├── .env.example            # 凭证模板
└── README.md
```

## 快速开始

1. **检查环境与连通性**

   ```bash
   pip install akshare yfinance ccxt pandas requests
   python3 scripts/check_connections.py
   ```

   运行后自动生成 `docs/连接检查报告.md`，每项带状态标识（✅正常 / ❌异常 / ⚠️未配置）。

2. **配置凭证**

   ```bash
   cp .env.example .env
   # 编辑 .env：邮件 SMTP、飞书/钉钉/企业微信机器人等
   python3 scripts/check_connections.py   # 复检推送通道
   ```

3. **导入自选股**

   `config/watchlist.json` 可直接读取；`watchlist.csv` 为 UTF-8 编码，Excel 双击打开。代码格式说明见 JSON 内 `code_notes`。

4. **部署定时任务**

   参考 `config/tasks.yaml` 中的 cron 表达式与落地方式（系统 crontab / APScheduler / Codex 定时提醒）。

## 数据源速览

| 板块 | 行情 | 财务 | 期权/衍生品 |
|------|------|------|-------------|
| A股 | 东方财富（备用：新浪） | 东方财富F10 | 50ETF/300ETF/科创50ETF 期权、波动率指数 |
| 港股 | 东方财富 | 东方财富 | 窝轮/牛熊证待接入（HKEX） |
| 美股 | Yahoo Finance（备用：东方财富） | Yahoo Finance | 个股/ETF 期权链 |
| 虚拟货币 | ccxt（币安/欧易/Bybit/Gate） | 链上/聚合数据待接入 | Deribit 期权 |

公开接口无需密钥；实盘交易与推送通道需要 `.env` 凭证。
