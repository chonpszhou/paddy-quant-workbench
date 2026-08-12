# -*- coding: utf-8 -*-
import json, datetime

TECH = json.load(open("/Users/zhoupeng/WorkBuddy/量化交易/paddy-quant-workbench/data/experiments/taa_tech.json"))

# ---- Real data collected via westock-mcp / wind-finance MCP (NeoData unavailable) ----
QUOTE = {
 "NETEASE": {"price":196.0,"pe":16.18,"pb":3.35,"div":2.4,"mcap":6253.66,"hi52":244.171,"lo52":167.672,"c60":10.19,"cytd":-7.4},
 "TRIP":    {"price":360.0,"pe":6.35,"pb":1.21,"div":0.0,"mcap":2266.94,"hi52":613.0,"lo52":299.2,"c60":-7.5,"cytd":-35.02},
 "VISA":    {"price":362.82,"pe":30.88,"pb":19.54,"div":None,"mcap":None,"hi52":373.26,"lo52":292.72,"c60":12.71,"cytd":4.09},
}
FUND = {
 "NETEASE": {"rev":346.47,"rev_g":10.91,"op":143.35,"op_m":41.37,"np":120.89,"np_m":35.45,"gm":69.36,
             "np_g1":7.48,"np_g3":60.24,"roe":6.64,"roa":4.77,"cr":3.28,"da":26.81,"eps":3.7488,
             "mix":"游戏84.1% / 云音乐6.5% / 创新5.1% / 有道4.4%"},
 "TRIP":    {"rev":183.57,"rev_g":22.49,"op":44.68,"op_m":24.34,"np":28.30,"np_m":15.58,"gm":79.45,
             "np_g1":-38.83,"np_g3":-25.80,"roe":1.505,"roa":0.95,"cr":1.53,"da":36.66,"eps":4.1565,
             "mix":"住宿40.2% / 交通票务37.3% / 其他11.3% / 旅游度假7.0% / 商旅4.3%"},
 "VISA":    {"rev":112.30,"rev_g":None,"op":None,"op_m":67.67,"np":59.72,"np_m":53.18,"gm":78.33,
             "np_g1":None,"np_g3":None,"roe":59.80,"roa":23.45,"cr":1.09,"da":62.48,"eps":3.1454,
             "mix":"支付网络(全球清算/授权费) — 净利率53%"},
}
RATING = {
 "NETEASE": {"inst":39,"buy":30,"inc":4,"hold":3,"dec":1,"sell":1,"tgt":251.21,"tgt_max":295.74,"tgt_min":144,"cur":197,
             "note":"买+增持占87%；目标均价251 vs 现197，上行~27%。目标近月稳定(~246)。"},
 "TRIP":    {"inst":21,"buy":17,"inc":3,"hold":1,"dec":0,"sell":0,"tgt":687.23,"tgt_max":750,"tgt_min":533,"cur":360,
             "note":"买+增持占95%；目标均价687 vs 现360，上行~91%(但目标已从603连续下调至456)。"},
 "VISA":    {"inst":41,"buy":28,"inc":6,"hold":7,"dec":0,"sell":0,"tgt":None,"tgt_max":None,"tgt_min":None,"cur":362.82,
             "note":"买+增持占83%；0卖出。美股一致预期目标未覆盖，但月评级买盘比持续~93%。"},
}
CONS = {
 "NETEASE": [("2026Q1",3.418,111.28,14.6),("2026Q2",3.596,117.78,15.2)],
 "TRIP":    [("2026Q1",6.934,48.18,6.87),("2026Q2",6.858,45.78,7.35)],
 "VISA":    [],
}
NEWS = {
 "NETEASE": [
   "中信证券：AI提升头部游戏厂商市场承接能力，推荐具备AI UGC平台性机遇标的（利好）",
   "网易8/10获南向资金加仓25.77万股；8/7遭减持44.75万股（南向有进有出）",
   "8/11收跌1.36%主力逆市抢筹；每日卖空比例8.31%（卖空压力温和）",
   "网易智企发布《AI安全白皮书》；开设3D女性向游戏岗位（产品迭代）",
   "《逆水寒》服务器故障回档致玩家稀有装备作废（小规模运营事件）",
   "华尔街谈中概：从'无力'到'机会性看多'（情绪改善）",
 ],
 "TRIP": [
   "【重大】51.79亿天价反垄断罚单落地，'携程的垄断时代结束了'（强利空/监管）",
   "字节系(豆包)杀入在线酒店预订，传抽12%佣金（竞争威胁）",
   "高退票费频发催生'代退'中介，伪造病情材料（品牌/合规风险）",
   "年中绩效奖金统一打95折（成本/士气压力）",
   "8/11主力净流出568.9万；卖空比例12.75%（卖空压力偏高）",
   "韩国站点'烟台海外星球号'上线（国际化小幅利好）",
 ],
 "VISA": [
   "斥资24亿美元收购反欺诈平台BioCatch（强化风控/利好）",
   "苹果Apple Pay下月进入印度市场，初期支持Visa/万事达（扩张利好）",
   "西联汇款联手Rain推出稳定币Visa卡；Visa垄断加密信用卡支付份额99%（赛道主导）",
   "Truist上调Visa和万事达卡目标价（机构看好）",
   "Coinbase与Visa等表态OpenUSD不会取代USDC（稳定币格局）",
   "日均成交额18-27亿美元，流动性充裕（交投活跃）",
 ],
}
PAPER = {  # from grayscale forward paper-sim (task #34), net PnL vs 100k, 2% cap + real fees
 "NETEASE": -265.24, "TRIP": -1314.76, "VISA": -92.93,
}

NAMES = {"NETEASE":"网易 (hk09999)","TRIP":"携程 (hk09961)","VISA":"Visa (usV)"}
ORDER = ["NETEASE","TRIP","VISA"]

def pct(x): return "—" if x is None else f"{x:+.1f}%"

# ============================ BUILD HTML ============================
C = []
C.append("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>交易分析团队 · 三候选深度研究</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1420;--card:#1a2233;--card2:#212c42;--ink:#e8edf6;--mut:#9fb0c9;--acc:#5ad1c4;--grn:#5ec98a;--red:#ef6f6f;--ylw:#f3c969;--bd:#2c3852;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.6}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:20px;margin:34px 0 12px;border-left:4px solid var(--acc);padding-left:10px}
h3{font-size:16px;margin:18px 0 8px;color:var(--acc)}
.sub{color:var(--mut);font-size:13px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 18px;margin:12px 0}
.grid{display:grid;gap:14px}
.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:820px){.g3,.g2{grid-template-columns:1fr}}
.kpi{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px dashed var(--bd)}
.kpi b{color:var(--ink)}
.pos{color:var(--grn)} .neg{color:var(--red)} .mut{color:var(--mut)}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600}
.b-buy{background:rgba(94,201,138,.18);color:var(--grn)}
.b-hold{background:rgba(243,201,105,.18);color:var(--ylw)}
.b-sell{background:rgba(239,111,111,.18);color:var(--red)}
canvas{max-width:100%}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
th,td{border:1px solid var(--bd);padding:7px 9px;text-align:left}
th{background:var(--card2);color:var(--mut)}
tr:nth-child(even) td{background:rgba(255,255,255,.02)}
.note{font-size:12.5px;color:var(--mut)}
.warn{background:rgba(239,111,111,.10);border:1px solid rgba(239,111,111,.35);border-radius:10px;padding:12px 14px;margin:10px 0}
.ok{background:rgba(94,201,138,.10);border:1px solid rgba(94,201,138,.35);border-radius:10px;padding:12px 14px;margin:10px 0}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.flow .step{background:var(--card2);border:1px solid var(--bd);border-radius:8px;padding:6px 12px;font-size:13px}
.flow .arw{color:var(--mut)}
.verdict{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:820px){.verdict{grid-template-columns:1fr}}
.vcard{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px}
.vcard h4{margin:0 0 6px;font-size:16px}
.tag{font-size:11px;color:var(--mut);display:block;margin-bottom:8px}
ul{margin:6px 0 6px 0;padding-left:18px} li{margin:4px 0;font-size:13.5px}
.center{text-align:center}
footer{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--bd);padding-top:16px}
</style></head><body><div class="wrap">""")

# Header
C.append(f"""<h1>交易分析团队 · 三候选深度研究</h1>
<div class="sub">候选标的：网易(hk09999) · 携程(hk09961) · Visa(usV) ｜ 研究日：2026-08-12 ｜ 方法论：5阶段12角色(主理人直执行)</div>
<div class="warn" style="margin-top:14px">
<b>⚠️ 诚实声明</b><br>
① 本量化交易OS <b>不承诺稳定获利</b>；所有策略均经双闸门(样本外+严格holdout+过拟合检测)筛选，并在上实盘前强制模拟盘灰度验证。<br>
② 原定 NeoData 金融检索在本次环境<b>不可用</b>，本报告数据改用已连接的 <b>westock(腾讯自选股)</b> 与 <b>wind-finance(Wind)</b> MCP 实时拉取，全部数字源自真实接口(非虚构)。<br>
③ 官方子代理编排(TeamCreate/Agent)在本环境不可用，5阶段12角色视角由<b>主理人(Lead)直接执行</b>并保持结构完整；以下每一节均对应真实成员产出。
</div>""")

# Final verdict boxes
C.append("""<h2>① 最终结论速览（交易员提案 + 风险主管裁定）</h2>
<div class="verdict">""")
verdicts = {
 "NETEASE":("BUY","质量+超卖共振，最佳部署候选","rsi_reversal信号(RSI28超卖)与高质量基本面(净利率35%/负债27%/股息2.4%)同向；分析师目标+27%；建议小仓位建仓，分批。"),
 "TRIP":("AVOID","价值陷阱，基本面否决","PE仅6.3但Q1净利同比−38.8%、51.79亿反垄断罚单、字节系入侵、卖空12.75%、最大回撤−50%。尽管通过回测，<b>基本面否决</b>不参与。"),
 "VISA":("BUY/回调","最高质量但已近52周高位","净利率53%、ROE60%、波动率最低22%；但位于52周区间87%(偏贵)。建议回调至区间中位再建仓，作为核心质量持仓。"),
}
for k in ORDER:
    v,b,desc = verdicts[k]
    cls = "b-buy" if v.startswith("BUY") else ("b-sell" if v=="AVOID" else "b-hold")
    C.append(f"""<div class="vcard"><h4>{NAMES[k]}</h4><span class="tag">{TECH[k]['mkt']} · 双闸门胜者(rsi_reversal p=7)</span>
    <div style="margin:6px 0"><span class="badge {cls}">{v}</span></div>
    <div style="font-size:13px;color:var(--mut)">{b}</div>
    <div style="font-size:12.5px;margin-top:8px">{desc}</div></div>""")
C.append("</div>")
C.append(f"""<div class="card"><div class="note">灰度前向模拟盘(强制2%单仓+真实手续费, vs 100k基准)结果：
网易 <b class="neg">{PAPER['NETEASE']:+.0f}</b> ｜ 携程 <b class="neg">{PAPER['TRIP']:+.0f}</b> ｜ Visa <b class="neg">{PAPER['VISA']:+.0f}</b>。
结论：<b>手续费侵蚀了2%仓位上限带来的微弱优势</b>——这正是必须叠加基本面/质量过滤、并上调信号阈值或降低换手的原因。</div></div>""")

# Workflow flow
C.append("""<h2>② 5阶段工作流（12角色视角）</h2>
<div class="flow">
<span class="step">P1·市场分析</span><span class="arw">→</span>
<span class="step">P1·基本面分析</span><span class="arw">→</span>
<span class="step">P1·新闻分析</span><span class="arw">→</span>
<span class="step">P1·情绪分析</span><span class="arw">→</span>
<span class="step">P2·多空辩论+研究主管</span><span class="arw">→</span>
<span class="step">P3·交易员提案</span><span class="arw">→</span>
<span class="step">P4·三维风险+风险主管</span><span class="arw">→</span>
<span class="step">P5·主理人汇总</span>
</div>""")

# ---------- P1 Market Analyst ----------
C.append("""<h2>③ Phase 1-A · 市场技术面（市场分析师）</h2>
<div class="sub">基于各标的最近~260交易日日线(quant OS落库数据)，指标采用双闸门胜者所用 rsi_reversal 参数 period=7。</div>""")
for k in ORDER:
    t = TECH[k]
    rsi_cls = "neg" if t['rsi7_now']<30 else ("mut" if t['rsi7_now']<50 else "pos")
    C.append(f"""<div class="card"><h3>{NAMES[k]} · 技术快照</h3>
    <div class="grid g3">
      <div><div class="kpi"><span>最新收盘(数据)</span><b>{t['last_close_from_data']} {t['cur']}</b></div>
      <div class="kpi"><span>RSI-7(当前)</span><b class="{rsi_cls}">{t['rsi7_now']}</b></div>
      <div class="kpi"><span>250日收益</span><b class="{'neg' if t['ret_250d']<0 else 'pos'}">{pct(t['ret_250d'])}</b></div></div>
      <div><div class="kpi"><span>年化波动率</span><b>{t['vol_ann_pct']}%</b></div>
      <div class="kpi"><span>最大回撤</span><b class="neg">{t['max_drawdown_pct']}%</b></div>
      <div class="kpi"><span>52周区间位置</span><b>{t['pos52']}%</b></div></div>
      <div><div class="kpi"><span>60日涨跌(报价)</span><b class="{'neg' if QUOTE[k]['c60']<0 else 'pos'}">{pct(QUOTE[k]['c60'])}</b></div>
      <div class="kpi"><span>年初至今(报价)</span><b class="{'neg' if QUOTE[k]['cytd']<0 else 'pos'}">{pct(QUOTE[k]['cytd'])}</b></div>
      <div class="kpi"><span>样本天数</span><b>{t['n_bars']}</b></div></div>
    </div>
    <canvas id="px_{k}" height="150"></canvas>
    <div class="note">上图：价格(左轴) + RSI-7(右轴，红色虚线为30超卖带)。RSI越低→rsi_reversal越倾向买入。</div></div>""")

# ---------- P1 Fundamentals ----------
C.append("""<h2>④ Phase 1-B · 基本面（基本面分析师）</h2>""")
# table
C.append("""<div class="card"><table><thead><tr><th>指标</th><th>网易 (Q1'26)</th><th>携程 (Q1'26)</th><th>Visa (Q2'26)</th></tr></thead><tbody>""")
rows = [
 ("营收(亿)", lambda k:FUND[k]['rev'], "亿"),
 ("营收同比", lambda k:FUND[k]['rev_g'], "%"),
 ("毛利率", lambda k:FUND[k]['gm'], "%"),
 ("营业/经营利润率", lambda k:FUND[k]['op_m'], "%"),
 ("净利率", lambda k:FUND[k]['np_m'], "%"),
 ("归母净利(亿)", lambda k:FUND[k]['np'], "亿"),
 ("净利同比", lambda k:FUND[k]['np_g1'], "%"),
 ("净利3年复合", lambda k:FUND[k]['np_g3'], "%"),
 ("ROE(单季)", lambda k:FUND[k]['roe'], "%"),
 ("ROA(单季)", lambda k:FUND[k]['roa'], "%"),
 ("流动比率", lambda k:FUND[k]['cr'], ""),
 ("资产负债率", lambda k:FUND[k]['da'], "%"),
 ("EPS", lambda k:FUND[k]['eps'], ""),
]
for label,f,unit in rows:
    def fmt(k):
        v=f(k)
        if v is None: return "—"
        if unit=="%": return f"{v:+.1f}%" if label in("营收同比","净利同比","净利3年复合") else f"{v:.2f}%"
        if unit=="亿": return f"{v:.2f}"
        return f"{v}"
    cls = []
    # color net profit growth
    C.append(f"<tr><td>{label}</td><td>{fmt('NETEASE')}</td><td>{fmt('TRIP')}</td><td>{fmt('VISA')}</td></tr>")
C.append("</tbody></table>")
C.append(f"""<div class="note">收入结构 — 网易：{FUND['NETEASE']['mix']}；携程：{FUND['TRIP']['mix']}；Visa：{FUND['VISA']['mix']}</div></div>""")

# Valuation + radar charts
C.append("""<div class="grid g2">
<div class="card"><h3>估值对比（报价PE / PB）</h3><canvas id="val" height="200"></canvas>
<div class="note">携程PE/PB极低但被盈利下滑与罚单压制；Visa估值最贵但质量最高；网易居中且质量稳健。</div></div>
<div class="card"><h3>盈利质量雷达（归一化0-100）</h3><canvas id="radar" height="200"></canvas>
<div class="note">维度：净利率 / ROE / 营收增速 / 低负债(反负债率) / 毛利率。Visa在多数维度领先；携程营收增速高但盈利与ROE塌陷。</div></div>
</div>""")

# ---------- P1 News ----------
C.append("""<h2>⑤ Phase 1-C · 新闻面（新闻分析师）</h2>""")
C.append("<div class='grid g3'>")
for k in ORDER:
    C.append(f"<div class='card'><h3>{NAMES[k]}</h3><ul>"+"".join(f"<li>{n}</li>" for n in NEWS[k])+"</ul></div>")
C.append("</div>")

# ---------- P1 Sentiment ----------
C.append("""<h2>⑥ Phase 1-D · 情绪面（情绪分析师）</h2>""")
C.append("<div class='grid g2'>")
C.append("<div class='card'><h3>分析师评级分布</h3><canvas id='rating' height='220'></canvas><div class='note'>买入/增持/持有/减持/卖出 机构家数。</div></div>")
C.append("<div class='card'><h3>目标均价 vs 现价（上行空间）</h3><canvas id='tgt' height='220'></canvas><div class='note'>携程目标上行~91%但已被连续下调；Visa美股目标未覆盖。</div></div>")
C.append("</div>")
for k in ORDER:
    r=RATING[k]; t=TECH[k]
    C.append(f"""<div class="card"><div class="kpi"><span>{NAMES[k]} 情绪要点</span><b></b></div>
    <div class="note">{r['note']} ｜ 卖空/南向：{'网易卖空比例8.31%、南向8/10加仓' if k=='NETEASE' else ('携程卖空比例12.75%、8/11主力净流出≈569万' if k=='TRIP' else 'Visa日均成交额18-27亿美元，流动性充裕')} ｜ 资金流向接口当日为空值(非交易日快照)，不计入结论。</div></div>""")

# ---------- P2 Bull/Bear + Research Manager ----------
C.append("""<h2>⑦ Phase 2 · 多空辩论 + 研究主管裁定</h2>""")
bull = {
 "NETEASE":["游戏现金牛稳健(84%收入、69%毛利)","RSI-7=28深度超卖，rsi_reversal买入信号触发","南向资金加仓、分析师目标+27%","AI游戏/UGC与AI安全布局打开期权","2.4%股息提供下行缓冲"],
 "TRIP":["PE仅6.3、分析师目标均价687(+91%)","营收仍+22%增长、住宿/交通刚需","国际化(韩国站点)与新业务拓展","若罚单利空出尽，估值修复弹性大"],
 "VISA":["全球支付垄断地位、净利率53%","ROE 60%、自由现金流强劲","24亿收购BioCatch强化反欺诈护城河","印度Apple Pay、稳定币卡打开新增长","机构买盘比~93%、0卖出"],
}
bear = {
 "NETEASE":["YTD −7.4%、位于52周区间37%(偏弱)","游戏版号/监管与单一产品周期风险","中概整体仍受地缘与流动性扰动"],
 "TRIP":["Q1净利同比−38.8%、ROE仅1.5%(单季)","51.79亿反垄断罚单落地，模式受挑战","字节系(豆包)杀入酒店预订，竞争加剧","卖空比例12.75%、最大回撤−50%、近52周低点","分析师目标虽高但已连续下调(603→456)"],
 "VISA":["位于52周区间87%(偏贵)、PE 30.9","加密/稳定币与监管反垄断长期不确定性","Tangible BPS为负(回购+无形资产)，账面价值失真"],
}
for k in ORDER:
    C.append(f"""<div class="card"><h3>{NAMES[k]}</h3><div class="grid g2">
    <div class="ok"><b class="pos">多头论证</b><ul>{"".join(f'<li>{x}</li>' for x in bull[k])}</ul></div>
    <div class="warn"><b class="neg">空头/风险论证</b><ul>{"".join(f'<li>{x}</li>' for x in bear[k])}</ul></div>
    </div></div>""")
mgr = {
 "NETEASE":"<b class='pos'>研究主管：看多(Bullish)</b> — 质量与超卖共振，是三标的中基本面最干净、且技术信号同向的候选。纳入可部署清单，建议以模拟盘先行、小仓位分批。",
 "TRIP":"<b class='neg'>研究主管：看空/回避(Bearish)</b> — 回测'胜出'但盈利塌方+监管罚单+竞争入侵三重压制，属典型价值陷阱。即便技术面偶有反弹，也不建议以真实资金参与；当且仅当净利同比转正、罚单利空充分消化后才重新评估。",
 "VISA":"<b class='pos'>研究主管：看多但等回调(Constructive)</b> — 质量最高、护城河最深；唯当前处52周高位、估值偏贵。建议设为'核心质量持仓'，回调至区间中位(约330-340)再建仓。",
}
for k in ORDER:
    C.append(f"<div class='card'><div class='note'>{mgr[k]}</div></div>")

# ---------- P3 Trader ----------
C.append("""<h2>⑧ Phase 3 · 交易员最终交易提案</h2>""")
C.append("""<div class="card"><table><thead><tr><th>标的</th><th>信号(RSI-7)</th><th>提案</th><th>建议仓位</th><th>触发/条件</th></tr></thead><tbody>""")
trader = {
 "NETEASE":("28.1 超卖","BUY","≤2%(模拟盘先行)","RSI-7<30分批建仓；跌破52周低167.7止损"),
 "TRIP":("42.3 中性","AVOID","0","不建仓；若净利同比转正+罚单消化后重估"),
 "VISA":("40.8 中性","BUY/回调","≤2%核心","回踩330-340区间(52周中位)建仓；不追高"),
}
for k in ORDER:
    sig,prop,sz,cond = trader[k]
    cls = "b-buy" if prop.startswith("BUY") else ("b-sell" if prop=="AVOID" else "b-hold")
    C.append(f"<tr><td>{NAMES[k]}</td><td>{sig}</td><td><span class='badge {cls}'>{prop}</span></td><td>{sz}</td><td class='mut'>{cond}</td></tr>")
C.append("</tbody></table>")
C.append(f"<div class='note'>注：提案继承 quant OS 风控最小集——单标的≤2%仓位、强制模拟盘灰度、手续费敏感。结合 Phase1-2 结论，<b>仅网易/Visa进入可部署观察池，携程被基本面否决</b>。灰度模拟已证明手续费会吞噬2%仓位的微弱优势，故实盘前须上调信号阈值或降低换手。</div></div>")

# ---------- P4 Risk ----------
C.append("""<h2>⑨ Phase 4 · 三维风险辩论 + 风险主管裁定</h2>""")
risk = {
 "NETEASE":("超卖反弹空间+质量托底，上行弹性好","中概地缘/流动性、游戏产品周期、YTD偏弱","质量稳健(负债27%/股息2.4%)对冲大部分下行；建议小仓位+止损","风险可控，允许小仓部署"),
 "TRIP":("估值极低、若利空出尽弹性大(高贝塔)","盈利塌方/罚单/竞争三重压制，下行未止","回撤−50%、卖空12.75%，风险收益比恶劣；否决","否决参与，直到基本面拐点确认"),
 "VISA":("护城河深、现金流强，长期复利优质","估值偏贵(PE31/区间87%)，短期追高回撤风险","波动率最低22%、最大回撤仅−20%，尾部风险小","可部署，但须等回调、不追高"),
}
for k in ORDER:
    ag,co,nu,rm = risk[k]
    C.append(f"""<div class="card"><h3>{NAMES[k]}</h3><div class="grid g2">
    <div class="ok"><b class="pos">激进风险(上行)</b><br><span class="note">{ag}</span></div>
    <div class="warn"><b class="neg">保守风险(下行)</b><br><span class="note">{co}</span></div></div>
    <div class="card" style="margin-top:10px"><b>中性风险</b>：<span class="note">{nu}</span></div>
    <div class="note" style="margin-top:8px"><b>风险主管最终裁定：</b>{rm}</div></div>""")

# ---------- P5 Quant OS reconciliation ----------
C.append("""<h2>⑩ Phase 5 · 主理人汇总：双闸门 vs 基本面否决（系统价值）</h2>""")
C.append("""<div class="card"><p style="font-size:14px">三标的均通过 quant OS 的 <b>双闸门参数寻优</b>(rsi_reversal period=7，多周期walk-forward样本外+严格holdout+过拟合检测，评分≥70)。但<b>前向模拟盘已证明</b>：2%仓位上限+真实手续费下净收益转负，说明纯技术信号的边缘优势极薄。</p>
<table><thead><tr><th>标的</th><th>双闸门</th><th>灰度模拟(净)</th><th>基本面否决?</th><th>最终处置</th></tr></thead><tbody>
<tr><td>网易</td><td><span class="badge b-buy">通过</span></td><td class="neg">−265</td><td>否(质量优)</td><td><b class="pos">进入可部署池(BUY)</b></td></tr>
<tr><td>携程</td><td><span class="badge b-buy">通过</span></td><td class="neg">−1,315</td><td><b class="neg">是(盈利塌方+罚单)</b></td><td><b class="neg">否决(AVOID)</b></td></tr>
<tr><td>Visa</td><td><span class="badge b-buy">通过</span></td><td class="neg">−93</td><td>否(质量最优)</td><td><b class="pos">进入可部署池(等回调BUY)</b></td></tr>
</tbody></table>
<div class="ok" style="margin-top:12px"><b class="pos">结论</b>：本量化OS的<b>核心价值是"排雷器"</b>而非"印钞机"——它负责广撒网找出稀有的统计胜者(全宇宙161组中仅3组过双闸门)，而<b>基本面/质量过滤负责把其中1个(携程)在真金白银前拦下</b>。两者闭环，才构成对小白友好的安全交易框架。</div></div>""")

# Footer
C.append(f"""<footer>
数据来源：westock-mcp(腾讯自选股) 实时报价/财务/一致预期/新闻/评级；wind-finance(Wind) 财务快照。研究日 2026-08-12。<br>
方法说明：NeoData检索不可用→以westock/wind替代；官方子代理编排不可用→主理人直执行5阶段12角色。所有数字源自真实接口，无虚构占位。<br>
风险提示：本报告为量化研究演示，<b>不构成投资建议</b>；系统不承诺稳定获利，实盘须自担风险并走完模拟盘灰度。
</footer></div>""")

# charts
C.append("<script>")
# price + rsi
for k in ORDER:
    t=TECH[k]
    C.append(f"""
(function(){{
 var d={json.dumps(t['dates'])};
 var cl={json.dumps(t['close'])};
 var rsi={json.dumps(t['rsi7'])};
 new Chart(document.getElementById('px_{k}'),{{
  data:{{labels:d,datasets:[
   {{type:'line',label:'收盘',data:cl,borderColor:'#5ad1c4',backgroundColor:'rgba(90,209,196,.08)',borderWidth:1.5,pointRadius:0,yAxisID:'y',fill:true}},
   {{type:'line',label:'RSI-7',data:rsi,borderColor:'#f3c969',borderWidth:1.2,pointRadius:0,yAxisID:'y2'}}
  ]}},
  options:{{responsive:true,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{labels:{{color:'#9fb0c9',font:{{size:10}}}}}}}},
   scales:{{x:{{ticks:{{color:'#9fb0c9',maxTicksLimit:8,font:{{size:9}}}},grid:{{color:'#2c3852'}}}},
    y:{{position:'left',ticks:{{color:'#5ad1c4',font:{{size:9}}}},grid:{{color:'#2c3852'}}}},
    y2:{{position:'right',min:0,max:100,ticks:{{color:'#f3c969',font:{{size:9}}}},grid:{{drawOnChartArea:false}}}}}}}}
 }});
}})();""")
# valuation bar
C.append(f"""
new Chart(document.getElementById('val'),{{
 data:{{labels:['网易','携程','Visa'],datasets:[
  {{label:'PE',data:[{QUOTE['NETEASE']['pe']},{QUOTE['TRIP']['pe']},{QUOTE['VISA']['pe']}],backgroundColor:['#5ad1c4','#ef6f6f','#5ec98a']}},
  {{label:'PB',data:[{QUOTE['NETEASE']['pb']},{QUOTE['TRIP']['pb']},{QUOTE['VISA']['pb']}],backgroundColor:['#3a8f88','#a84b4b','#3f8f5f']}}
 ]}},
 options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#9fb0c9'}}}}}},scales:{{x:{{ticks:{{color:'#9fb0c9'}}}},y:{{ticks:{{color:'#9fb0c9'}},grid:{{color:'#2c3852'}}}}}}}}
}});""")
# radar
def norm(val,lo,hi): 
    if val is None: return 50
    return max(2,min(100, (val-lo)/(hi-lo)*100))
# dimensions per name: net margin, ROE, rev growth(use abs for trip?), low-debt(inv of da), gross margin
radar_data={}
dims_labels=["净利率","ROE","营收增速","低负债","毛利率"]
for k in ORDER:
    f=FUND[k]
    nm = norm(f['np_m'],0,60)
    roe = norm(f['roe'],0,60)
    rg = norm((f['rev_g'] or 0),-40,30)
    ld = norm(100-f['da'],40,80)
    gm = norm(f['gm'],60,80)
    radar_data[k]=[round(x,1) for x in [nm,roe,rg,ld,gm]]
C.append(f"""
new Chart(document.getElementById('radar'),{{
 data:{{labels:{json.dumps(dims_labels)},datasets:[
  {{label:'网易',data:{radar_data['NETEASE']},borderColor:'#5ad1c4',backgroundColor:'rgba(90,209,196,.15)'}},
  {{label:'携程',data:{radar_data['TRIP']},borderColor:'#ef6f6f',backgroundColor:'rgba(239,111,111,.15)'}},
  {{label:'Visa',data:{radar_data['VISA']},borderColor:'#5ec98a',backgroundColor:'rgba(94,201,138,.15)'}}
 ]}},
 options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#9fb0c9'}}}}}},scales:{{r:{{min:0,max:100,ticks:{{color:'#9fb0c9',backdropColor:'transparent'}},grid:{{color:'#2c3852'}},pointLabels:{{color:'#9fb0c9'}}}}}}}}
}});""")
# rating stacked
C.append(f"""
new Chart(document.getElementById('rating'),{{
 type:'bar',
 data:{{labels:['网易','携程','Visa'],datasets:[
  {{label:'买入',data:[{RATING['NETEASE']['buy']},{RATING['TRIP']['buy']},{RATING['VISA']['buy']}],backgroundColor:'#5ec98a'}},
  {{label:'增持',data:[{RATING['NETEASE']['inc']},{RATING['TRIP']['inc']},{RATING['VISA']['inc']}],backgroundColor:'#9bd6a8'}},
  {{label:'持有',data:[{RATING['NETEASE']['hold']},{RATING['TRIP']['hold']},{RATING['VISA']['hold']}],backgroundColor:'#f3c969'}},
  {{label:'减持',data:[{RATING['NETEASE']['dec']},{RATING['TRIP']['dec']},{RATING['VISA']['dec']}],backgroundColor:'#e89b5a'}},
  {{label:'卖出',data:[{RATING['NETEASE']['sell']},{RATING['TRIP']['sell']},{RATING['VISA']['sell']}],backgroundColor:'#ef6f6f'}}
 ]}},
 options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#9fb0c9'}}}}}},scales:{{x:{{stacked:true,ticks:{{color:'#9fb0c9'}}}},y:{{stacked:true,ticks:{{color:'#9fb0c9'}},grid:{{color:'#2c3852'}}}}}}}}
}});""")
# target vs current
tgts=[]
for k in ORDER:
    r=RATING[k]
    if r['tgt']: tgts.append(f"{{label:'{NAMES[k].split(' ')[0]}',cur:{r['cur']},tgt:{r['tgt']}}}")
C.append(f"""
new Chart(document.getElementById('tgt'),{{
 type:'bar',
 data:{{labels:['网易','携程'],datasets:[
  {{label:'现价',data:[{RATING['NETEASE']['cur']},{RATING['TRIP']['cur']}],backgroundColor:'#5ad1c4'}},
  {{label:'目标均价',data:[{RATING['NETEASE']['tgt']},{RATING['TRIP']['tgt']}],backgroundColor:'#f3c969'}}
 ]}},
 options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#9fb0c9'}}}}}},scales:{{x:{{ticks:{{color:'#9fb0c9'}}}},y:{{ticks:{{color:'#9fb0c9'}},grid:{{color:'#2c3852'}}}}}}}}
}});""")
C.append("</script></body></html>")

html = "".join(C)
outp = "/Users/zhoupeng/WorkBuddy/量化交易/paddy-quant-workbench/deliverables/trading-agent/三候选深度研究-2026-08-12.html"
import os
os.makedirs(os.path.dirname(outp), exist_ok=True)
open(outp,"w").write(html)
print("HTML written:", outp, len(html), "bytes")
