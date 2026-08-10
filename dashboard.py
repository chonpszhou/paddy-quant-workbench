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
from src.monitor.price_alert import PriceAlert
from src.utils.common import COLOR_UP, COLOR_DOWN, load_settings

st.set_page_config(page_title="Paddy 量化工作台", layout="wide")

settings = load_settings()
SIG_TF = settings["signal"]["timeframes"]
RT_INTERVAL = int(settings.get("realtime", {}).get("default_interval", 5))

hub = DataHub()
sig = SignalEngine()
wl = Watchlist()
alerter = AlertEngine()
pa = PriceAlert()
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
    st.header("实时行情 · 自选监控")
    st.caption("加密货币经 Binance @ticker 实时推送(涨绿跌红); 美股/港股为延迟数据, 用行情看板轮询")

    # 手动订阅 + 自选分组中的加密标的自动订阅
    syms = st.text_input("手动订阅(逗号分隔, 如 BTC,ETH,SOL)", "", key="rt_syms")
    manual = [s.strip().upper() for s in syms.split(",") if s.strip()]
    wl_crypto = [i["symbol"] for i in wl.list() if i["market"] == "crypto"]
    sym_list = list(dict.fromkeys(manual + wl_crypto))  # 去重保序
    if sym_list:
        ticker.ensure_running(sym_list)

    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.caption("自动订阅" if wl_crypto else "未订阅")
    with col_b:
        interval = st.slider("刷新间隔(秒)", 1, 15, RT_INTERVAL, key="rt_int")
    st_autorefresh(interval=interval * 1000, key="rt_autorefresh")

    status = ticker.status()
    if not status["has_ws"]:
        st.warning("未安装 websocket-client, 实时推送不可用 (pip install websocket-client)")
    elif not status["running"]:
        st.info("无加密订阅; 把 crypto 标的加入关注列表后此处自动订阅实时流")
    else:
        st.success(f"实时流已连接, 订阅: {', '.join(status['symbols'])}")

    snap = ticker.snapshot()

    # ---- 价格预警触发 ----
    triggered = pa.evaluate(snap)
    if triggered:
        st.subheader("🔔 价格预警触发")
        for t in triggered:
            direction = "上破 ≥" if t["direction"] == "above" else "下破 ≤"
            field = "价格" if t["field"] == "price" else "24h涨跌%"
            st.error(f"{t['symbol']} {field} {direction} {t['threshold']} → 当前 {t['cur']}"
                     + (f" ({t['note']})" if t.get("note") else ""))
    else:
        st.caption("当前无触发的价格预警")

    # ---- 分组自选实时表 ----
    st.subheader("分组自选 · 实时")
    any_group = False
    for g in wl.groups():
        items = wl.list(g)
        if not items:
            continue
        any_group = True
        st.markdown(f"**{g}**")
        rows = []
        for it in items:
            s = it["symbol"]
            r = snap.get(s)
            if r:
                color = COLOR_UP if r["change_pct"] >= 0 else COLOR_DOWN
                arrow = "▲" if r["change_pct"] >= 0 else "▼"
                price = f"{r['price']:,.2f}"
                chg = f"<span style='color:{color}'>{arrow} {abs(r['change_pct']):.2f}%</span>"
                live = "实时"
            else:
                price = "—"
                chg = "—"
                live = "延迟/未订阅" if it["market"] == "crypto" else "延迟"
            rows.append({
                "标的": s,
                "市场": it["market"],
                "最新价": price,
                "24h涨跌": chg,
                "备注": it.get("note", ""),
                "数据": live,
            })
        st.write(pd.DataFrame(rows).to_html(escape=False, index=False), unsafe_allow_html=True)
    if not any_group:
        st.info("关注列表为空, 先到「关注列表」页添加标的与分组")

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
    st.header("关注列表 · 自选分组")
    st.caption("分组管理标的; 价格预警在「实时行情」页结合实时流自动触发")

    # ---- 分组选择 / 删除 ----
    groups = wl.groups()
    col_g1, col_g2 = st.columns([3, 1])
    with col_g1:
        sel_group = st.selectbox("当前分组", groups, key="wl_group")
    with col_g2:
        if sel_group != "默认":
            if st.button(f"删除分组「{sel_group}」", key="wl_delgroup"):
                wl.delete_group(sel_group)
                st.success("已删除该分组及其标的")

    # ---- 添加标的到当前分组 ----
    c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
    with c1:
        sym = st.text_input("添加标的", key="wl_sym")
    with c2:
        market = st.selectbox("市场", ["us", "hk", "crypto"], key="wl_mkt")
    with c3:
        note = st.text_input("备注(可选)", key="wl_note")
    with c4:
        new_group = st.text_input("归入新分组(可选)", key="wl_newgroup")
    target_group = new_group.strip() or sel_group
    if st.button("添加到分组", key="wl_add"):
        if sym.strip():
            ok = wl.add(sym, market, note, target_group)
            st.success(f"已添加至「{target_group}」" if ok else "该分组已存在此标的")
        else:
            st.warning("请输入标的")

    # ---- 当前分组标的 ----
    items = wl.list(sel_group)
    if items:
        st.dataframe(pd.DataFrame(items)[["symbol", "market", "note", "group"]],
                     use_container_width=True)
        rm_sym = st.text_input("删除标的(当前分组)", key="wl_rm")
        rm_mkt = st.selectbox("删除标的市场", ["us", "hk", "crypto"], key="wl_rm_mkt")
        if st.button("删除", key="wl_del"):
            ok = wl.remove(rm_sym, rm_mkt, sel_group)
            st.success("已删除" if ok else "未找到")
    else:
        st.info("当前分组暂无标的")

    # ---- 价格预警规则管理 ----
    st.subheader("价格预警规则")
    st.caption("对标的设置 价格/涨跌幅 的 上破/下破 阈值; 实时行情页自动评估触发")
    a1, a2, a3 = st.columns([2, 1, 1])
    with a1:
        a_sym = st.text_input("预警标的", "BTC", key="pa_sym")
    with a2:
        a_mkt = st.selectbox("市场", ["crypto", "us", "hk"], index=0, key="pa_mkt")
    with a3:
        a_field = st.selectbox("指标", ["price", "change_pct"], key="pa_field")
    b1, b2, b3 = st.columns([2, 2, 2])
    with b1:
        a_dir = st.selectbox("方向", ["above", "below"],
                             format_func=lambda x: "上破 ≥" if x == "above" else "下破 ≤",
                             key="pa_dir")
    with b2:
        a_thr = st.number_input("阈值", value=0.0, key="pa_thr")
    with b3:
        a_note = st.text_input("备注", key="pa_note")
    if st.button("添加预警", key="pa_add"):
        if a_sym.strip():
            pa.add(a_sym, a_mkt, a_field, a_dir, a_thr, a_note)
            st.success("预警已添加")
        else:
            st.warning("请输入标的")
    rules = pa.list()
    if rules:
        st.dataframe(
            pd.DataFrame(rules)[["symbol", "market", "field", "direction", "threshold", "note", "id"]],
            use_container_width=True,
        )
        del_id = st.text_input("删除规则ID", key="pa_delid")
        if st.button("删除规则", key="pa_del"):
            ok = pa.remove(del_id)
            st.success("已删除" if ok else "未找到该ID")
    else:
        st.info("暂无预警规则")
