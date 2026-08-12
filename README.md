# Paddy 量化工作台

面向 **A股 / 港股 / 美股 / 加密货币** 四大市场、覆盖 **现货 / ETF / 期货** 多标的的私有量化交易操作系统（参考小隐寺社区产品形态，做成可本地运行的私域工作台）。

> 设计目标：面向金融小白，提供「**可回测、可复盘、强制风控、灰度上实盘**」的纪律化交易操作系统。本系统**不承诺稳定获利**——它只保证任何策略在实盘前必须过回测、过样本外、且强制套用风控最小集。盈亏由市场决定。

配色采用国际惯例：**涨 = 绿，跌 = 红**（目标市场非 A 股）。

## 功能

| 模块 | 说明 |
|------|------|
| 数据接入 | A股走 akshare（前复权），美股/港股走 yfinance，加密走 Binance 公开 API；统一接口 + 本地 parquet 缓存 |
| 历史落库 | 每次取数增量写入 SQLite（`data/market.db`），回测不再重复拉取（规划优先级 #1） |
| 信号引擎 | 多周期（1d/4h/1h/15m）买卖点：均线交叉 + RSI + 量能异常换手 + 趋势连续性 |
| 期权 GEX | 美股期权 Gamma Exposure 估算：Call Wall / Put Wall / Zero Gamma |
| 回测引擎 | 向量化双均线 / 动量 / 均值回归，输出收益、回撤、夏普、胜率、**盈亏比**；内置 **walk-forward 样本外** 防过拟合 |
| **风控最小集** | 单笔/单策略/总仓位上限、固定+ATR 止损、保本移动、单日/总回撤熔断、保守凯利；与策略代码分离、独立评审（实盘前硬门槛） |
| **小白向导 CLI** | `quantos.py`：风险问卷 → 生成配置 → 回测 + 中文风控报告 → 模块自检（详见下方「量化交易操作系统」章节） |
| **多标的规格引擎** | 统一描述 现货/ETF/期货 的保证金、合约乘数、手续费、做空性；风控按名义市值限仓，期货按保证金占用（规划缺口补齐） |
| **执行层（模拟盘）** | `PaperBroker` 支持多空/期货保证金/逐日盯市；与实盘适配器(ccxt/easytrader)同接口，先模拟盘打磨再切实盘 |
| **交易日历** | 四大市场开市/休市/时段判断（A股/港股有午休，美股按时区，数字货币 7x24），回测与调度只在交易日触发 |
| **实验扫描** | 批量跑 标的×预设 + walk-forward 样本外 + 可上实盘评分，横向挑出真正稳健的组合（反过拟合） |
| **参数寻优** | 给定策略在参数网格上遍历，用 **walk-forward 样本外指标排序**（而非样本内），并检测过拟合（样本内/样本外夏普比），自动挑出最稳健参数；通过门槛(≥70)可落为部署预设 |
| 个股研报 | 基于 yfinance 基本面数据自动生成 Markdown 研报 |
| 关注列表 | 关注标的增删查（JSON 持久化） |
| 告警监控 | 扫描关注列表，触发买卖点 / 异常换手告警 |
| Web 面板 | Streamlit 多页：行情看板 / 信号扫描 / 回测 / 研报 / GEX / 关注列表 |

## 量化交易操作系统（小白向导）

核心入口是仓库根目录的 `quantos.py`，面向没有编程基础的金融小白，把「开户 → 选策略 → 回测 → 风控评审 → 模拟盘」串成一条命令链。

```bash
# 1) 开户问卷：按你的风险承受力生成 config/user_profile.yaml，并推荐预设
python quantos.py init

# 2) 回测 + 中文风控报告（默认模拟盘，不碰实盘）
python quantos.py backtest --preset conservative --symbol 600519 --market a      # A股 贵州茅台
python quantos.py backtest --preset balanced    --symbol AAPL   --market us     # 美股
python quantos.py backtest --preset balanced    --symbol 0700   --market hk     # 港股
python quantos.py backtest --preset aggressive  --symbol BTCUSDT --market crypto # 数字货币

# 3) 校验风控配置是否自洽（无网络）
python quantos.py check

# 4) 模块自检（无需联网 / 无需装 akshare，验证风控 + 回测 + 多标的 + 模拟盘 + 日历可用）
python quantos.py selftest

# 5) 用真实数据跑「前向模拟盘」，验证执行层（多空/保证金/风控限仓）
python quantos.py paper --preset balanced --symbol 600519 --market a
python quantos.py paper --preset aggressive --symbol BTCUSDT --market c --itype spot

# 6) 实验扫描：一次比较多个 标的×预设，输出可上实盘评分
python quantos.py sweep --jobs "600519:a:conservative,00700:hk:balanced,AAPL:us:balanced,BTCUSDT:crypto:aggressive"

# 7) 交易日历查询
python quantos.py calendar --date 2026-08-11

# 8) 参数寻优：用真实数据 + walk-forward 样本外，自动找稳健参数（防过拟合）
python quantos.py optimize --symbol 600519 --market a --strategy sma_cross --top 5
python quantos.py optimize --symbol AAPL   --market us --strategy momentum --top 5
# 若最优组合评分≥70 且未过拟合，加 --save-best 落盘为可部署预设
python quantos.py optimize --symbol AAPL --market us --strategy momentum --top 5 --save-best

# 9) 组合层（ensemble）：把多条 标的×策略 腿合成一个组合，输出聚合绩效 + 相关性诊断
python quantos.py combine --jobs "09999:hk:09999_hk_rsi_reversal_opt,AAPL:us:balanced,600519:a:conservative" --weight equal
python quantos.py combine --jobs "09999:hk:09999_hk_rsi_reversal_opt,AAPL:us:balanced" --weight vol   # 波动率目标加权

# 10) 实盘执行层（默认 DRY-RUN，绝不发真单；双闸门才真实下单）
#     —— DRY-RUN 沙盘推演（安全，仅记录"本应下的单"，不触碰交易所）：
python quantos.py live --preset 09999_hk_rsi_reversal_opt --symbol 09999 --market hk --itype spot
#     —— 真正下单需：① settings.yaml 打开 live_trading.enabled=True ② 显式 --i-understand-real-money-risk
#        二者缺一，仍只走 dry-run。详见「实盘安全」章节。
```

> ⚠️ 寻优/扫描/实盘每次运行都会落盘到 `data/experiments/runs.jsonl`（穷人版 MLflow 实验追踪），便于横向比较与防回归。

> 市场代码简写互认：`a`(A股) / `hk`或`h`(港股) / `us`或`u`(美股) / `crypto`或`c`(数字货币)，新手怎么写都行。

预设策略（三档风险，见 `config/strategies/`）：

| 预设 | 定位 | 策略 | 工具 | 风控（在全局最小集上进一步收紧） |
|------|------|------|------|------|
| `conservative` | 守护型·低风险 | 均值回归 | 现货/ETF | 单笔≤1% / 总≤30% / 止损-2% / 单日熔断-3% / 总回撤-12% |
| `balanced` | 均衡型·进阶 | 双均线 | 现货/ETF/期货 | 全局最小集 |
| `aggressive` | 进取型·博弈 | 动量 | 美股/加密/期货 | 全局最小集（更宽） |

**内置策略库（7 个，信号函数统一接收整张 `df`，OHLC 类策略需含开高低收行情）：**

| 策略 | 类型 | 思路 | 是否需要 OHLC |
|------|------|------|---------------|
| `sma_cross` | 趋势 | 双均线金叉/死叉 | 否（close） |
| `momentum` | 趋势 | N 日动量方向 | 否（close） |
| `mean_reversion` | 均值回归 | z-score 偏离均值反向 | 否（close） |
| `donchian` | 趋势跟踪 | 海龟式通道突破（用 t-1 通道防未来函数） | 是 |
| `dual_thrust` | 日内突破 | 前日波动区间构造上下触发线 | 是 |
| `rsi_reversal` | 均值回归 | RSI 超卖做多/超买卖空 | 否（close） |
| `atr_channel` | 趋势跟踪 | 中轨 ± mult×ATR 波动自适应通道 | 是 |

> 诚实提醒：参数寻优在 33 标的 × 7 策略（231 组）上跑双闸门（多周期 walk-forward 样本外 + 严格 holdout + 过拟合检测），当前仅 **3 组**通过（09999 港股 rsi_reversal 评分 93.7 / OOS夏普 2.41、09961 港股 rsi_reversal 评分 79.3 / OOS夏普 2.1、V 美股 rsi_reversal 评分 74.6 / OOS夏普 1.75，均未过拟合）。这正说明稳健 Alpha 稀缺——系统的价值在于**自动拒绝其余 228 组**（含 8 组过拟合拦截、212 组双闸门未过），而非制造"看起来很美"的曲线。完整结果看板见 `data/experiments/universe_opt_dashboard.html`。

> **灰度验证的诚实补充（必读）**：三个双闸门胜者又经 `quantos.py paper` 前向模拟盘（真实数据 + 强制 2% 单笔下注 + 真实手续费）验证，结果全部落在**接近盈亏平衡到小幅亏损**：09999 网易净额 −265 / 09961 携程 −1,315 / V Visa −93（均相对 10 万初始资金）。原因很直白——样本外夏普是在**满仓单标的**口径下算的，而灰度模拟被 2% 仓位上限 + 约 60 次换手的高费率拖累，信号 Edge 被手续费吃光。**结论：双闸门筛出的是"统计上有 Edge 的参数"，不等于"实盘能赚钱"**；真正上量要看仓位/费率/滑点。系统如实呈现，未粉饰。详见 `data/experiments/paper_grayscale_report.html`。

完整操作手册见 **[OS_GUIDE.md](OS_GUIDE.md)**；配套知识库在 Obsidian「量化交易」库（总览见 `00_量化交易支撑体系规划.md`）。

## 子项目：星辰投研团

仓库内附投研监控与研究子项目（[星辰投研团/README.md](星辰投研团/README.md)），覆盖 A股 / 港股 / 美股 / 虚拟货币 / 期权五类标的：

- **数据源与推送连接检查**：`星辰投研团/scripts/check_connections.py` 一键验证各行情/财务/期权接口与邮件、IM 推送通道，输出带状态标识的检查清单
- **默认自选股清单**：`星辰投研团/config/watchlist.json`（64 条，含期权标的池），可直接导入
- **自动化定时任务配置**：`星辰投研团/config/tasks.yaml`（盘中异动 / 收盘速报 / 周报 / 财报监控 / 期权波动率 / 加密监控）
- **GitHub 量化 Top50 学习笔记**：`星辰投研团/docs/量化交易GitHub顶级项目学习笔记.md`，含分类研读与落地借鉴

## 安装

```bash
cd quant_platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

> 国内网络拉 PyPI 默认源很慢（实测被限速到 ~38KB/s），建议用清华镜像加速：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
> 仅装 Web 面板依赖也可用：`pip install streamlit plotly -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 运行

```bash
streamlit run dashboard.py
```

或在 Python 中直接调用各模块：

```python
from src.data.unified import DataHub
from src.engine.signals import SignalEngine

hub = DataHub()
df = hub.get("BTC", "crypto", "1d", 200)
d, extra = SignalEngine().analyze(df, "1d")
print(extra)   # {'signal': 'BUY', ...}
```

## 部署 (Streamlit Community Cloud)

代码已发布到公开仓库 https://github.com/chonpszhou/paddy-quant-workbench，可一键部署：

1. 打开 https://streamlit.io/cloud，**务必用拥有该仓库的 GitHub 账号登录**（换错账号则下拉框看不到仓库）。
2. 点击 **New app**，Repository 下拉里选 `chonpszhou/paddy-quant-workbench`。
   - 若下拉列表里**看不到此仓库**：说明 GitHub 的 OAuth 授权范围未包含它。去 GitHub → Settings → Developer settings → OAuth Apps（或 Settings → Integrations → Applications）→ 找到 Streamlit 授权 → Repository access 改为 **All repositories** 或显式勾选 `paddy-quant-workbench` → 保存 → 回 Streamlit Cloud 刷新重选。
   - **不要用本地 `streamlit` 的 “Deploy” 按钮**，那条老路径常报 “code is not connected to a remote GitHub repository”，直接走官网网页最稳。
3. Branch 选 `main`，**Main file path 必须填 `dashboard.py`**（默认是 `app.py`，不填会部署后找不到入口）。
4. 点击 **Deploy**（根目录的 requirements.txt 会自动安装依赖）。

部署后得到 `*.streamlit.app` 公网地址；改代码后 `git push` 会自动重新部署。

> ⚠️ 部署报错 “The app’s code is not connected to a remote GitHub repository” 不是代码问题，是 Streamlit Cloud ↔ GitHub 的授权连接没建立，按上面第 2 步排查 OAuth 范围即可。
> 免费版闲置会休眠，首次访问冷启动约 1–2 分钟；行情源（yfinance / Binance）在云端可正常访问。
> 本项目无密钥，公开仓库安全；若以后接入券商 API，请使用 Streamlit Cloud 的 **Secrets** 功能，切勿写入代码。

## 部署 (Docker)

适合本地常驻、内网共享或丢到任意 Linux 服务器。镜像基于 `python:3.11-slim`，非 root 用户运行，内置健康检查。

### 方式一：docker compose（推荐）

```bash
# 构建并后台启动
docker compose up -d --build
# 浏览器打开 http://localhost:8501
```

关注列表与价格预警数据通过 named volume `quant-data` 持久化，重建容器不丢。停止：`docker compose down`。

### 方式二：原生 docker

```bash
docker build -t paddy-quant-workbench .
docker run -d --name paddy-quant -p 8501:8501 \
  -v paddy-quant-data:/app/data \
  --restart unless-stopped \
  paddy-quant-workbench
```

### 说明

- 容器内 Streamlit 监听 `0.0.0.0:8501`，映射到宿主机 `8501`。
- 实时加密行情依赖出网到 `stream.binance.com`（WebSocket），部署机需放行该域名；无外网时实时流会显示「正在等待首条推送」。
- 如需改端口，在 `docker run` 时把左边 `-p 9090:8501` 改成你的端口即可（`8501` 是容器内端口，勿改）。

## 目录结构

```
quant_platform/
├── config/
│   ├── settings.yaml        # 市场/信号/回测/风控参数
│   └── strategies/          # 三档预设：conservative / balanced / aggressive
├── quantos.py               # 小白向导 CLI（init/backtest/check/selftest/paper/sweep/calendar/optimize/combine/live）
├── dashboard.py             # Streamlit 面板入口
├── OS_GUIDE.md              # 小白操作手册
├── requirements.txt
├── src/
│   ├── data/                # 数据接入 / 统一(DataHub) / 存储(Storage+SQLStore)
│   ├── engine/              # signals / gex / backtest(walk-forward) / instruments(多标的) / experiment(扫描) / optimizer(双闸门寻优) / portfolio(组合层)
│   ├── broker/              # 执行层：base(抽象) / paper(模拟盘) / live(实盘安全层·dry-run双闸门) / ccxt(加密实盘) / easytrader(A股实盘)
│   ├── utils/               # 配置 / 配色 / 工具 / calendar(交易日历) / experiment_log(实验追踪)
│   ├── risk/                # 风控最小集（risk_control.py，与策略分离）
│   ├── research/            # 个股研报
│   ├── monitor/             # 关注列表 / 告警
│   └── utils/               # 配置 / 配色 / 工具 / calendar(交易日历)
├── scripts/                 # validate_kline.py(真实行情验证) 等
└── data/                    # 缓存/落库/真实样本 (运行生成, 已 gitignore)
```

## 实盘安全（重要）

本 OS 把"回测 → 模拟盘 → 实盘"设计为**默认不碰真钱**：

- `live` 命令默认 **DRY-RUN**：用模拟盘记账 + 记录"本应下的单"，**绝不触碰任何交易所**。
- 真正发单需要**双闸门同时打开**：① `config/settings.yaml` 中 `live_trading.enabled: true`；② 命令行显式 `--i-understand-real-money-risk`。**二者缺一，仍是 dry-run**。
- 即便 armed，也只在实例化时惰性导入 `ccxt` / `easytrader`，且需要你预先配置好 API Key / 券商客户端。
- 任何"偷偷发单"的代码路径都被上述双闸门堵死；实盘前务必先用 `live` 的 dry-run 推演核对成交逻辑。

> 数字化货币/港美/A股实盘适配器（`ccxt` / `easytrader`）为**可选依赖**，缺失不影响回测与模拟盘。请在本机、小资金、已跑满模拟盘并 walk-forward 通过后再考虑灰度实盘。

## 免责声明

本平台所有信号、研报、GEX 均为基于公开数据的量化辅助工具，**不构成投资建议**。实盘下单前请自行决策并确认风险。
