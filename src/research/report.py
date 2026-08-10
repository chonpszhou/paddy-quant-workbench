"""个股基本面研报自动生成 (基于 yfinance info)。

输出 Markdown 研报: 公司概况 / 估值 / 财务 / 风险。
"""
from __future__ import annotations

import yfinance as yf


def _fmt_cap(v) -> str:
    if v is None:
        return "-"
    if v >= 1e12:
        return f"{v/1e12:.2f} 万亿"
    if v >= 1e9:
        return f"{v/1e9:.2f} 十亿"
    if v >= 1e6:
        return f"{v/1e6:.2f} 百万"
    return str(v)


def _pct(v) -> str:
    return f"{v*100:.2f}%" if isinstance(v, (int, float)) else "-"


def generate_report(symbol: str, market: str = "us") -> str:
    ticker = symbol if market != "hk" else f"{symbol}.HK"
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return f"# 研报生成失败: {symbol}\n\n无法获取公开数据, 请检查标的代码或网络。"

    name = info.get("shortName") or info.get("longName") or symbol
    sector = info.get("sector") or "-"
    industry = info.get("industry") or "-"
    market_cap = info.get("marketCap")
    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    ps = info.get("priceToSalesTrailing12Months")
    profit_margin = info.get("profitMargins")
    revenue = info.get("totalRevenue")
    debt_eq = info.get("debtToEquity")
    roe = info.get("returnOnEquity")
    fifty_two_high = info.get("fiftyTwoWeekHigh")
    fifty_two_low = info.get("fiftyTwoWeekLow")
    current = info.get("currentPrice") or info.get("regularMarketPrice")

    md = f"""# {name} ({symbol}) 个股研报

> 自动生成, 仅供参考, 不构成投资建议。

## 公司概况
- 行业: {sector} / {industry}
- 市值: {_fmt_cap(market_cap)}
- 现价: {current}

## 估值
- PE(TTM): {pe}
- PB: {pb}
- PS(TTM): {ps}
- 52周区间: {fifty_two_low} ~ {fifty_two_high}

## 财务
- 营收(TTM): {_fmt_cap(revenue)}
- 净利率: {_pct(profit_margin)}
- ROE: {_pct(roe)}
- 负债/权益(D/E): {debt_eq}

## 风险提示
- 数据来自公开接口, 可能存在延迟或缺失
- 估值与财务仅为快照, 不构成买卖依据
- 请结合技术面与宏观自行决策
"""
    return md
