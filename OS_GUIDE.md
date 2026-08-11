# 量化交易操作系统 · 小白操作手册（OS_GUIDE）

> 本手册是 `paddy-quant-workbench` 面向金融小白的实操入口。配套知识库在 Obsidian「量化交易」库（总览：`00_量化交易支撑体系规划.md`）。
> **诚实前提**：本系统不承诺"稳定获利"。它只保证——任何策略在实盘前必须过回测、过样本外、且强制套用风控最小集。能不能赚钱，由市场和你对纪律的执行决定。

---

## 0. 先记住三句话（保命用）

1. **先模拟盘，再实盘。** 永远从 `phase: paper` 开始，跑满 1 个月无重大风控事故，才谈小资金灰度。
2. **风控是硬门槛，不是建议。** 单笔≤2%、单日-5%熔断、总回撤-20%熔断——这些在 `config/settings.yaml` 的 `risk` 段，实盘前不可关、不可绕过。
3. **回测惊艳 ≠ 实盘能赚。** 必须用 `walk-forward` 看样本外表现；样本外夏普 < 0.5 一律不上实盘。

---

## 1. 环境准备（一次就好）

```bash
cd paddy-quant-workbench
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

- A股数据需要 akshare：`pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple`
- 美股/港股走 yfinance（已含在 requirements）；数字货币走 Binance 公开 API（无需 key）。
- 不想装依赖也能跑：`python quantos.py selftest` 用合成数据自检，零网络。

---

## 2. 四步上手（命令链）

### 第 1 步：开户问卷（生成你的风险画像）

```bash
python quantos.py init
```

按提示回答：能接受的最大回撤、想做哪些市场（a/h/u/c）、计划投入金额。
脚本生成 `config/user_profile.yaml`，并推荐一个预设（conservative / balanced / aggressive）。

### 第 2 步：回测 + 中文风控报告

```bash
# A股（贵州茅台）
python quantos.py backtest --preset conservative --symbol 600519 --market a
# 美股（苹果）
python quantos.py backtest --preset balanced --symbol AAPL --market us
# 港股（腾讯）
python quantos.py backtest --preset balanced --symbol 0700 --market hk
# 数字货币（比特币）
python quantos.py backtest --preset aggressive --symbol BTCUSDT --market crypto
```

输出包含：总收益、年化、最大回撤、夏普、胜率、**盈亏比**、交易次数，以及**强制风控最小集**红字提示。
> 市场代码简写互认：`a`/`cn`(A股)、`hk`/`h`(港股)、`us`/`u`(美股)、`crypto`/`c`(数字货币)。

### 第 3 步：校验风控配置自洽

```bash
python quantos.py check
```

无网络即可运行，确认仓位上限、止损、熔断逻辑不自相矛盾。

### 第 4 步：模块自检（交付前兜底）

```bash
python quantos.py selftest
```

用固定随机种子跑风控 + 回测单元断言，确保代码没被改坏。

### 2.1 参数寻优 / 组合层 / 实盘（进阶）

```bash
# 参数寻优：walk-forward 样本外排序 + 双闸门，评分≥70 且未过拟合才 --save-best 落盘
python quantos.py optimize --symbol 09999 --market hk --strategy rsi_reversal --top 5 --save-best

# 组合层：把多条 标的×策略 腿合成一个组合，输出聚合绩效 + 相关性诊断（防"伪分散"）
python quantos.py combine --jobs "09999:hk:09999_hk_rsi_reversal_opt,AAPL:us:balanced" --weight equal

# 实盘执行层：默认 DRY-RUN（绝不发真单），双闸门才真正下单
python quantos.py live --preset 09999_hk_rsi_reversal_opt --symbol 09999 --market hk
```

- 每次寻优/扫描/实盘都会落盘 `data/experiments/runs.jsonl`（实验追踪，便于横向比较）。
- `live` 双闸门：① `settings.yaml` 打开 `live_trading.enabled` ② 显式 `--i-understand-real-money-risk`；**缺一不可发真单**。

---

## 3. 三档预设怎么选

| 预设 | 适合谁 | 策略 | 工具 | 在全局最小集上额外收紧 |
|------|--------|------|------|------------------------|
| `conservative` 守护型 | 刚入门、怕大波动 | 均值回归（跌多买、涨多卖） | 现货/ETF | 单笔≤1% / 总≤30% / 止损-2% / 单日熔断-3% / 总回撤-12% |
| `balanced` 均衡型 | 有点经验、想进阶 | 双均线交叉 | 现货/ETF/期货 | 维持全局最小集 |
| `aggressive` 进取型 | 能承受博弈、只看美股/加密 | 动量 | 美股/加密/期货 | 维持全局最小集（参数更宽） |

预设文件在 `config/strategies/` 下，可直接改 `params`（策略参数）和 `risk_override`（风控覆盖）。

---

## 4. 风控最小集（实盘前硬门槛）

定义在 `src/risk/risk_control.py`，阈值来自 `config/settings.yaml` 的 `risk` 段：

| 项目 | 默认值 | 含义 |
|------|--------|------|
| 单笔仓位上限 | 2% | 任一标的最多占总资产 2% |
| 单策略仓位上限 | 30% | 同一策略累计不超过 30% |
| 总开仓上限 | 50% | 永远保留 ≥50% 现金 |
| 单笔止损 | -3% | 固定止损；同时用 ATR×1.5，取更严格者 |
| 保本移动 | +6% | 浮盈≥6% 后止损上移至成本价 |
| 单日熔断 | -5% | 当日亏损达 5% 立即停手 |
| 总回撤熔断 | -20% | 累计回撤达 20% 全面暂停，重新评估 |
| 凯利系数 | 0.5 | 仅用半凯利，保守仓位 |
| 断线不追单 | 开 | 网络断开时禁止追价下单 |

**设计原则**：风控代码与策略代码分离、独立评审。改策略不能顺手把风控关了。

---

## 5. 数据从哪来（四市场）

`src/data/unified.py` 的 `DataHub` 统一收口：

| 市场 | 数据源 | 复权 | 备注 |
|------|--------|------|------|
| A股 | akshare `stock_zh_a_hist` | 前复权(qfq) | 代码自动归一化：600519 / sh600519 / 600519.SH 都认 |
| 美股 | yfinance | — | ticker 如 AAPL |
| 港股 | yfinance | — | 后缀 .HK，如 0700.HK |
| 数字货币 | Binance 公开 API | — | 如 BTCUSDT |

每次取数会：① 写本地 parquet 缓存（`data/cache`）；② **增量落库 SQLite**（`data/market.db`，规划优先级 #1）。回测再次跑同一标的时优先读库，不再重复拉取。

---

## 6. 回测与防过拟合纪律

`src/engine/backtest.py` 提供 **7 个策略**：`sma_cross`（双均线）、`momentum`（动量）、`mean_reversion`（均值回归）、`rsi_reversal`（RSI 逆向均值回归，close）、`donchian`（海龟通道突破）、`dual_thrust`（日内突破）、`atr_channel`（ATR 通道突破·波动自适应，后三者需 OHLC 行情）。
**严格防未来函数**：信号用 `shift(1)` 后的仓位计算，避免偷看次日价格；OHLC 类策略用 t-1 通道/区间构造触发线，同样不偷看。

每份回测报告都带 **walk-forward 样本外验证**：把历史切成多段，前段训练、后段测试滚动进行。
- 样本内漂亮、样本外稀烂 = 过拟合警告，绝不上实盘。
- 判定线：样本外平均夏普 < 0.5 → 不上实盘。

绩效口径固定为：总收益 / 年化 / 最大回撤 / 夏普 / 胜率 / **盈亏比**。

---

## 7. 从模拟盘到实盘的路线图（与 Obsidian 规划对齐）

| 阶段 | 目标 | 本仓库对应能力 |
|------|------|----------------|
| 一·研究地基 | 数据可落库、回测可复现 | `DataHub` + `SQLStore` + `Backtester` |
| 二·策略验证 | 策略库版本化、进模拟盘 | `config/strategies/*` + walk-forward |
| 三·小资金实盘 | 最小风控 + 灰度 | `src/risk` + `src/broker/live`（dry-run 双闸门安全层）+ ccxt/easytrader 适配器 |
| 四·迭代优化 | 组合管理、月度归因 | `src/engine/portfolio`（组合层）+ `src/utils/experiment_log`（实验追踪） |

> 当前进度（2026-08-11）：落库 ✅、风控最小集 ✅、四市场真实数据 ✅、小白向导 ✅、七策略库 ✅、双闸门寻优 ✅、组合层 ✅、实验追踪 ✅、实盘安全层（dry-run）✅。
> 仍待建：实盘适配器的**真实下单灰度**（需本机配置券商/交易所凭证 + 小资金验证）、更长样本与更大标的池、ML 特征工程。详见 Obsidian `00_量化交易支撑体系规划.md` 第 3 节"现状盘点"。

---

## 8. 常见问题

- **Q：`--market u` 报错？** 不会了。现已互认 `u`/`us`、`h`/`hk`、`c`/`crypto`、`a`/`cn`。
- **Q：拉不到 A股数据？** 没装 akshare，或网络被限。先 `pip install akshare`，再确认能访问 East Money。
- **Q：回测最大回撤超过熔断线？** 报告会红字警告。先降仓位（用 conservative 预设）或换参数，别急着上实盘。
- **Q：selftest 用联网吗？** 不用，纯合成数据，适合没网时验证代码。

---

## 9. 免责声明

本平台所有信号、研报、回测、风控均为基于公开数据的量化辅助工具，**不构成投资建议**。实盘下单前请自行决策并确认风险；任何实盘亏损与本系统及作者无关。
