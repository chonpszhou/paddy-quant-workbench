"""Paddy 量化工作台 - Streamlit 面板。

运行:
    cd quant_platform
    pip install -r requirements.txt
    streamlit run dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根在 sys.path (便于 import src)
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.data.unified import DataHub
from src.data.realtime import get_live_ticker
from src.engine.signals import SignalEngine
from src.engine.backtest import Backtester
from src.engine.gex import compute_gex
from src.research.report import generate_report
from src.research.backtest_report import build_backtest_report_md, build_backtest_report_html
from src.monitor.watchlist import Watchlist
from src.monitor.alert import AlertEngine
from src.utils.common import COLOR_UP, COLOR_DOWN, load_settings

st.set_page_config(page_title="Paddy 量化工作台", layout="wide")

settings = load_settings()
SIG_TF = settings["signal"]["timeframes"]
RT_INTERVAL = int(settings.get("realtime", {}).get("default_interval", 5))

hub = DataHub()
sig = SignalEngine()
wl = Watchlist()
alerter = AlertEngine()
ticker = get_live_ticker()

st.sidebar.title("Paddy 量化工作台")
st.sidebar.caption("美股 / 港股 / 加密货币 · 绿涨红跌")
page = st.sidebar.radio(
    "导航", ["行情看板", "实时行情", "信号扫描", "策略回测", "个股研报", "期权 GEX", "关注列表"]
)


def candle_fig(df: pd.DataFrame, d: pd.DataFrame):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.03
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线", increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=d.index, y=d["ma_fast"], line=dict(color="#f59e0b", width=1), name="MA快"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=d.index, y=d["ma_slow"], line=dict(color="#8b5cf6", width=1), name="MA慢"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], marker_color="#9ca3af", name="成交量"),
        row=2, col=1,
    )
    fig.update_layout(xaxis_rangeslider_visible=False, height=620, margin=dict(l=20, r=20, t=20, b=20))
    return fig


if page == "行情看板":
    st.header("行情看板")
    c1, c2, c3 = st.columns(3)
    with c1:
        sym = st.text_input("标的", "BTC", key="kb_sym")
    with c2:
        market = st.selectbox("市场", ["us", "hk", "crypto"], key="kb_mkt")
    with c3:
        tf = st.selectbox("周期", SIG_TF, index=0, key="kb_tf")
    limit = st.slider("K线数量", 50, 500, 200, key="kb_limit")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        realtime = st.checkbox("实时模式", key="kb_rt", help="开启后按间隔自动重新拉取最新行情(加密货币最佳)")
    with col_b:
        interval = st.slider("刷新间隔(秒)", 2, 30, RT_INTERVAL, key="kb_int")

    if realtime:
        st_autorefresh(interval=interval * 1000, key="kb_autorefresh")
        use_cache = False
    else:
        use_cache = True

    if st.button("加载", key="kb_load") or realtime:
        df = hub.get(sym, market, tf, limit, use_cache=use_cache)
        if df is None or df.empty:
            st.warning("无数据, 请检查代码或网络")
        else:
            d, extra = sig.analyze(df, tf)
            st.plotly_chart(candle_fig(df, d), use_container_width=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("信号", extra["signal"])
            m2.metric("收盘价", round(extra["close"], 2))
            m3.metric("RSI", round(extra["rsi"], 1))
            m4.metric("趋势", extra["trend"])
            if extra["anomaly_vol"]:
                st.error(f"异常换手提醒 (E): 量能 z = {extra['vol_z']:.1f}")

elif page == "实时行情":
    st.header("实时行情 · 加密货币 WebSocket 推送")
    st.caption("通过 Binance @ticker 实时流推送, 涨绿跌红; 美股/港股为延迟数据请用行情看板轮询")
    syms = st.text_input("标的(逗号分隔, 如 BTC,ETH,SOL)", "BTC,ETH,SOL", key="rt_syms")
    col_a, col_b = st.columns([1, 3])
    with col_a:
        start = st.button("启动 / 更新订阅", key="rt_start")
    with col_b:
        interval = st.slider("刷新间隔(秒)", 1, 15, RT_INTERVAL, key="rt_int")

    sym_list = [s.strip().upper() for s in syms.split(",") if s.strip()]
    if sym_list:
        ticker.ensure_running(sym_list)

    st_autorefresh(interval=interval * 1000, key="rt_autorefresh")
    status = ticker.status()
    if not status["has_ws"]:
        st.warning("未安装 websocket-client, 实时推送不可用 (pip install websocket-client)")
    elif not status["running"]:
        st.info("点击「启动 / 更新订阅」开始接收实时行情")
    else:
        st.success(f"实时流已连接, 订阅: {', '.join(status['symbols'])}")
        snap = ticker.snapshot()
        if not snap:
            st.info("正在等待首条推送...")
        else:
            rows = []
            for s in sym_list:
                r = snap.get(s)
                if r:
                    color = COLOR_UP if r["change_pct"] >= 0 else COLOR_DOWN
                    arrow = "▲" if r["change_pct"] >= 0 else "▼"
                    rows.append({
                        "标的": s,
                        "最新价": f"{r['price']:,.2f}",
                        "24h涨跌": f"<span style='color:{color}'>{arrow} {abs(r['change_pct']):.2f}%</span>",
                        "最高": f"{r['high']:,.2f}",
                        "最低": f"{r['low']:,.2f}",
                    })
            if rows:
                st.write(pd.DataFrame(rows).to_html(escape=False, index=False), unsafe_allow_html=True)

elif page == "信号扫描":
    st.header("信号扫描 · 关注列表")
    tfs = st.multiselect("周期", SIG_TF, default=["1d"], key="ss_tf")
    if st.button("扫描", key="ss_run"):
        results = alerter.scan(wl.list(), tfs)
        if not results:
            st.info("当前关注列表无触发信号")
        else:
            st.dataframe(pd.DataFrame(results), use_container_width=True)

elif page == "策略回测":
    st.header("策略回测 · 参数调优")
    c1, c2, c3 = st.columns(3)
    with c1:
        sym = st.text_input("标的", "BTC", key="bt_sym")
    with c2:
        market = st.selectbox("市场", ["us", "hk", "crypto"], index=2, key="bt_mkt")
    with c3:
        strat = st.selectbox("策略", ["sma_cross", "momentum", "mean_reversion"], key="bt_strat")
    limit = st.slider("数据长度", 100, 600, 300, key="bt_limit")
    tf = st.selectbox("周期", SIG_TF, index=0, key="bt_tf")

    st.subheader("策略参数")
    params: dict = {}
    if strat == "sma_cross":
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            params["fast"] = st.slider("快线周期", 2, 50, settings["signal"]["fast_ma"], key="p_fast")
        with col_p2:
            params["slow"] = st.slider("慢线周期", 5, 200, settings["signal"]["slow_ma"], key="p_slow")
    elif strat == "momentum":
        params["window"] = st.slider("动量窗口", 5, 120, 20, key="p_win")
    elif strat == "mean_reversion":
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            params["window"] = st.slider("均值窗口", 5, 120, 20, key="p_win")
        with col_p2:
            params["n_std"] = st.slider("标准差倍数", 1.0, 4.0, 2.0, 0.1, key="p_nsd")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        capital = st.number_input("初始资金", 1000, 10000000, int(settings["backtest"]["initial_capital"]), key="p_cap")
    with col_c2:
        commission = st.number_input("单边佣金", 0.0, 0.01, float(settings["backtest"]["commission"]), 0.0001, key="p_comm", format="%.4f")

    if st.button("运行回测", key="bt_run"):
        df = hub.get(sym, market, tf, limit)
        if df is None or df.empty:
            st.warning("无数据")
        else:
            res = Backtester(initial_capital=capital, commission=commission).run(df, strat, **params)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("总收益", f"{res['total_return']*100:.1f}%")
            m2.metric("年化", f"{res['annual_return']*100:.1f}%")
            m3.metric("最大回撤", f"{res['max_drawdown']*100:.1f}%")
            m4.metric("夏普", f"{res['sharpe']:.2f}")
            m5.metric("交易次数", res["n_trades"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=res["equity"].index, y=res["equity"].values, name="净值"))
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

            params_disp = ", ".join(f"{k}={v}" for k, v in params.items())
            st.subheader("导出报告")
            col_d1, col_d2 = st.columns(2)
            md = build_backtest_report_md(res, params, sym, market, tf)
            html = build_backtest_report_html(res, params, sym, market, tf)
            with col_d1:
                st.download_button("下载 Markdown", md, file_name=f"backtest_{sym}_{tf}.md", mime="text/markdown")
            with col_d2:
                st.download_button("下载 HTML", html, file_name=f"backtest_{sym}_{tf}.html", mime="text/html")
            with st.expander("预览报告"):
                st.markdown(md)

elif page == "个股研报":
    st.header("个股基本面研报")
    c1, c2 = st.columns(2)
    with c1:
        sym = st.text_input("代码", "AAPL", key="rp_sym")
    with c2:
        market = st.selectbox("市场", ["us", "hk"], index=0, key="rp_mkt")
    if st.button("生成研报", key="rp_run"):
        md = generate_report(sym, market)
        st.markdown(md)

elif page == "期权 GEX":
    st.header("美股期权 GEX (Gamma Exposure)")
    st.caption("基于期权链 + Black-Scholes 估算, 仅供参考")
    sym = st.text_input("美股代码", "AAPL", key="gx_sym")
    if st.button("计算 GEX", key="gx_run"):
        g = compute_gex(sym)
        if not g:
            st.warning("GEX 计算失败 (需美股期权数据)")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("现价", round(g["underlying"], 2))
            m2.metric("Call Wall", g["call_wall"])
            m3.metric("Put Wall", g["put_wall"])
            m4.metric("Zero Gamma", g["zero_gamma"])
            fig = go.Figure()
            gd = g["gex_by_strike"]
            fig.add_trace(go.Bar(x=gd["strike"], y=gd["gex"], name="GEX"))
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

elif page == "关注列表":
    st.header("关注列表")
    c1, c2 = st.columns(2)
    with c1:
        sym = st.text_input("添加标的", key="wl_sym")
    with c2:
        market = st.selectbox("市场", ["us", "hk", "crypto"], key="wl_mkt")
    if st.button("添加", key="wl_add"):
        ok = wl.add(sym, market)
        st.success("已添加" if ok else "已存在")
    st.dataframe(pd.DataFrame(wl.list()), use_container_width=True)
    rm_sym = st.text_input("删除标的", key="wl_rm")
    if st.button("删除", key="wl_del"):
        ok = wl.remove(rm_sym, market)
        st.success("已删除" if ok else "未找到")
