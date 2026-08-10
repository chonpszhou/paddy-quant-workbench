"""回测结果报告生成 (Markdown / HTML, 含净值曲线 sparkline)。"""
from __future__ import annotations

from datetime import datetime


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _metrics(res: dict) -> list[tuple[str, str]]:
    return [
        ("策略", str(res.get("strategy", "-"))),
        ("总收益", _fmt_pct(res.get("total_return", 0.0))),
        ("年化收益", _fmt_pct(res.get("annual_return", 0.0))),
        ("最大回撤", _fmt_pct(res.get("max_drawdown", 0.0))),
        ("夏普比率", f"{res.get('sharpe', 0.0):.2f}"),
        ("胜率", _fmt_pct(res.get("win_rate", 0.0))),
        ("交易次数", str(res.get("n_trades", 0))),
    ]


def build_backtest_report_md(res: dict, params: dict, symbol: str,
                             market: str, timeframe: str) -> str:
    lines = [
        f"# 回测报告 — {symbol} ({market})",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 周期: {timeframe}",
        f"- 策略参数: `{params}`",
        "",
        "## 绩效指标",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
    ]
    for k, v in _metrics(res):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## 说明",
        "",
        "- 回测基于历史数据, 严格防未来函数(信号滞后一周期)。",
        "- 佣金按仓位发生变化时单边扣除。",
        "- 结果仅供参考, 不构成任何投资建议。",
        "",
    ]
    return "\n".join(lines)


def _area_chart(equity, w: int = 920, h: int = 280) -> str:
    """净值曲线面积图 (内联 SVG, 含渐变填充 + 初始基准线)。"""
    vals = list(equity.values)
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    pad = 10
    pts = []
    for i, v in enumerate(vals):
        x = pad + (i / (n - 1)) * (w - 2 * pad)
        y = h - pad - ((v - lo) / span) * (h - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    base_y = h - pad - ((vals[0] - lo) / span) * (h - 2 * pad)
    area_pts = f"{pad:.1f},{h - pad:.1f} " + poly + f" {w - pad:.1f},{h - pad:.1f}"
    return f'''
<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" class="equity">
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#6366f1" stop-opacity="0.40"/>
      <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#6366f1" flood-opacity="0.55"/>
    </filter>
  </defs>
  <line x1="{pad:.1f}" y1="{base_y:.1f}" x2="{w - pad:.1f}" y2="{base_y:.1f}"
        stroke="#334155" stroke-width="1" stroke-dasharray="5 5"/>
  <polygon points="{area_pts}" fill="url(#fill)"/>
  <polyline points="{poly}" fill="none" stroke="#818cf8" stroke-width="2"
            stroke-linejoin="round" stroke-linecap="round" filter="url(#glow)"/>
</svg>'''


def build_backtest_report_html(res: dict, params: dict, symbol: str,
                               market: str, timeframe: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _card(label, value, kind):
        return (f'<div class="kpi {kind}"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-val">{value}</div></div>')

    tr = res.get("total_return", 0.0)
    ar = res.get("annual_return", 0.0)
    dd = res.get("max_drawdown", 0.0)
    sh = res.get("sharpe", 0.0)
    wr = res.get("win_rate", 0.0)
    nt = res.get("n_trades", 0)
    cards = "".join([
        _card("总收益", _fmt_pct(tr), "pos" if tr >= 0 else "neg"),
        _card("年化收益", _fmt_pct(ar), "pos" if ar >= 0 else "neg"),
        _card("最大回撤", _fmt_pct(dd), "neg"),
        _card("夏普比率", f"{sh:.2f}", "pos" if sh >= 0 else "neg"),
        _card("胜率", _fmt_pct(wr), "neutral"),
        _card("交易次数", str(nt), "neutral"),
    ])
    chart = _area_chart(res.get("equity"))
    chart_html = (f'<div class="chart-box">{chart}</div>'
                  if chart else '<div class="empty">暂无净值数据</div>')
    params_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "默认"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>回测报告 · {symbol}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#09090b; --surface:rgba(15,23,42,.55); --border:#334155;
    --text:#f8fafc; --muted:#94a3b8; --pos:#10b981; --neg:#f43f5e; --accent:#6366f1;
    --radius:14px; --glow:0 18px 40px -18px rgba(99,102,241,.45);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:radial-gradient(1200px 600px at 82% -12%, rgba(99,102,241,.14) 0%, var(--bg) 55%);
         color:var(--text); font-family:"Inter",-apple-system,"PingFang SC","Segoe UI",Roboto,sans-serif;
         -webkit-font-smoothing:antialiased; padding:40px 24px; }}
  .wrap {{ max-width:960px; margin:0 auto; }}
  header, .kpis, section, .note {{ opacity:0; animation:skin-fade-in .3s cubic-bezier(.16,1,.3,1) forwards; }}
  header {{ animation-delay:0s; margin-bottom:28px; }}
  .kpis {{ animation-delay:.05s; }}
  section:nth-of-type(1) {{ animation-delay:.10s; }}
  section:nth-of-type(2) {{ animation-delay:.15s; }}
  .note {{ animation-delay:.20s; }}
  @keyframes skin-fade-in {{ from {{ opacity:0; transform:translateY(12px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .badge {{ display:inline-block; font-size:11px; letter-spacing:.18em; color:var(--accent);
           border:1px solid var(--border); padding:4px 10px; border-radius:999px; margin-bottom:14px; }}
  h1 {{ font-family:"Space Grotesk","Inter",sans-serif; font-size:30px; margin:0; font-weight:700; letter-spacing:-.02em; }}
  h1 .mkt {{ color:var(--muted); font-weight:500; font-size:18px; margin-left:8px; }}
  .sub {{ color:var(--muted); font-size:13px; margin-top:8px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:8px 0 26px; }}
  .kpi {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
         padding:18px 20px; backdrop-filter:blur(10px); box-shadow:var(--glow); }}
  .kpi-label {{ color:var(--muted); font-size:12px; margin-bottom:8px; }}
  .kpi-val {{ font-family:"JetBrains Mono","Inter",monospace; font-size:26px; font-weight:700; letter-spacing:-.01em; }}
  .kpi.pos .kpi-val {{ color:var(--pos); }}
  .kpi.neg .kpi-val {{ color:var(--neg); }}
  .kpi.neutral .kpi-val {{ color:var(--text); }}
  section {{ margin-bottom:26px; }}
  h2 {{ font-size:13px; color:var(--muted); font-weight:600; margin:0 0 12px;
        text-transform:uppercase; letter-spacing:.08em; }}
  .chart-box {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px; box-shadow:var(--glow); }}
  .chart-box .equity {{ display:block; width:100%; height:auto; }}
  .params code {{ background:#0f1623; border:1px solid var(--border); border-radius:10px;
                padding:10px 14px; font-size:13px; color:var(--accent); display:inline-block; }}
  .note {{ color:#64748b; font-size:12px; line-height:1.7; border-top:1px solid var(--border); padding-top:18px; }}
  .empty {{ color:var(--muted); font-size:14px; }}
  @media (max-width:640px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head>
<body><div class="wrap">
  <header>
    <div class="badge">BACKTEST REPORT</div>
    <h1>{symbol}<span class="mkt">{market}</span></h1>
    <div class="sub">{timeframe} · 生成于 {now}</div>
  </header>
  <section class="kpis">{cards}</section>
  <section><h2>净值曲线</h2>{chart_html}</section>
  <section><h2>策略参数</h2><div class="params"><code>{params_str}</code></div></section>
  <div class="note">回测基于历史数据, 严格防未来函数(信号滞后一周期); 佣金按仓位变化单边扣除。
  结果仅供参考, 不构成任何投资建议。</div>
</div></body></html>"""
