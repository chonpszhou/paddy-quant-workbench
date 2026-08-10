# Paddy 量化工作台

面向 **美股 / 港股 / 加密货币** 的私有量化交易工作平台（参考小隐寺社区产品形态，做成可本地运行的私域工作台）。

配色采用国际惯例：**涨 = 绿，跌 = 红**（目标市场非 A 股）。

## 功能

| 模块 | 说明 |
|------|------|
| 数据接入 | 美股/港股走 yfinance，加密走 Binance 公开 API；统一接口 + 本地 parquet 缓存 |
| 信号引擎 | 多周期（1d/4h/1h/15m）买卖点：均线交叉 + RSI + 量能异常换手 + 趋势连续性 |
| 期权 GEX | 美股期权 Gamma Exposure 估算：Call Wall / Put Wall / Zero Gamma |
| 回测引擎 | 向量化双均线 / 动量 / 均值回归，输出收益、回撤、夏普、胜率 |
| 个股研报 | 基于 yfinance 基本面数据自动生成 Markdown 研报 |
| 关注列表 | 关注标的增删查（JSON 持久化） |
| 告警监控 | 扫描关注列表，触发买卖点 / 异常换手告警 |
| Web 面板 | Streamlit 多页：行情看板 / 信号扫描 / 回测 / 研报 / GEX / 关注列表 |

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

1. 打开 https://streamlit.io/cloud，用 GitHub（仓库所属账号）登录。
2. 点击 **New app**。
3. Repository 选 `chonpszhou/paddy-quant-workbench`，Branch 选 `main`，Main file path 填 `dashboard.py`。
4. 点击 **Deploy**（根目录的 requirements.txt 会自动安装依赖）。

部署后得到 `*.streamlit.app` 公网地址；改代码后 `git push` 会自动重新部署。

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
├── config/settings.yaml     # 市场/信号/回测参数
├── dashboard.py             # Streamlit 面板入口
├── requirements.txt
├── src/
│   ├── data/                # 数据接入 / 统一 / 存储
│   ├── engine/              # signals / gex / backtest
│   ├── research/            # 个股研报
│   ├── monitor/             # 关注列表 / 告警
│   └── utils/               # 配置 / 配色 / 工具
└── data/                    # 缓存与关注列表 (运行生成)
```

## 免责声明

本平台所有信号、研报、GEX 均为基于公开数据的量化辅助工具，**不构成投资建议**。实盘下单前请自行决策并确认风险。
