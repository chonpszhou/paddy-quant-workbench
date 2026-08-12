import pandas as pd, numpy as np, json, sys

BASE = "/Users/zhoupeng/WorkBuddy/量化交易/paddy-quant-workbench/data/real"

# Parameters from the dual-gate winners (all rsi_reversal, period=7)
CFGS = {
    "NETEASE":   {"file": f"{BASE}/hk_09999_1d.parquet", "name": "网易",   "mkt": "港股", "code": "hk09999", "cur": "HKD", "qprice": 196.0,  "hi52": 244.171, "lo52": 167.672},
    "TRIP":      {"file": f"{BASE}/hk_09961_1d.parquet", "name": "携程",   "mkt": "港股", "code": "hk09961", "cur": "HKD", "qprice": 360.0,  "hi52": 613.0,   "lo52": 299.2},
    "VISA":      {"file": f"{BASE}/us_V_1d.parquet",     "name": "Visa",   "mkt": "美股", "code": "usV",     "cur": "USD", "qprice": 362.82, "hi52": 373.26,  "lo52": 292.72},
}

def rsi(series, period=7):
    series = series.astype(float)
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100)
    return out

out = {}
for key, c in CFGS.items():
    df = pd.read_parquet(c["file"])
    df = df.reset_index()  # date becomes a column
    df = df[["date","open","high","low","close","volume"]]
    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)
    df["rsi7"] = rsi(close, 7)
    # Drawdown from running peak
    peak = close.cummax()
    dd = (close / peak - 1) * 100
    # 52w range position using last 252 bars
    recent = close.tail(252)
    last = float(close.iloc[-1])
    # Use quote's 52w hi/lo for position
    pos52 = (c["qprice"] - c["lo52"]) / (c["hi52"] - c["lo52"]) * 100
    # Returns
    ret_20 = (close.iloc[-1]/close.iloc[-21]-1)*100 if len(close)>21 else None
    ret_60 = (close.iloc[-1]/close.iloc[-61]-1)*100 if len(close)>61 else None
    ret_ytd = None  # unknown start; use 250d
    ret_250 = (close.iloc[-1]/close.iloc[max(0,len(close)-250)]-1)*100
    # Volatility (daily ret std annualized)
    dret = close.pct_change().dropna()
    vol_ann = dret.std()*np.sqrt(252)*100
    # max drawdown
    mdd = float(dd.min())
    out[key] = {
        "name": c["name"], "mkt": c["mkt"], "code": c["code"], "cur": c["cur"],
        "qprice": c["qprice"], "hi52": c["hi52"], "lo52": c["lo52"], "pos52": round(pos52,1),
        "last_close_from_data": round(last,2),
        "rsi7_now": round(float(df["rsi7"].iloc[-1]),1),
        "ret_20d": round(ret_20,1) if ret_20 is not None else None,
        "ret_60d": round(ret_60,1) if ret_60 is not None else None,
        "ret_250d": round(ret_250,1),
        "vol_ann_pct": round(vol_ann,1),
        "max_drawdown_pct": round(mdd,1),
        "n_bars": int(len(close)),
        # time series (downsample to ~120 pts for chart)
        "dates": df["date"].astype(str).tolist()[-260:],
        "close": [round(x,2) for x in close.tolist()[-260:]],
        "rsi7": [None if pd.isna(x) else round(x,1) for x in df["rsi7"].tolist()[-260:]],
        "drawdown": [round(x,2) for x in dd.tolist()[-260:]],
    }

with open("/Users/zhoupeng/WorkBuddy/量化交易/paddy-quant-workbench/data/experiments/taa_tech.json","w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print("OK")
for k,v in out.items():
    print(f"{v['name']:8s} close={v['last_close_from_data']:>9} rsi7={v['rsi7_now']:>5} 250d={v['ret_250d']:>6}% vol={v['vol_ann_pct']:>5}% mdd={v['max_drawdown_pct']}% pos52={v['pos52']}% bars={v['n_bars']}")
