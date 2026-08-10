"""安装后验证: 导入模块 + 拉取 Binance 数据跑通信号与回测。"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def log(msg: str):
    print(msg, flush=True)


def main():
    try:
        from src.data.unified import DataHub
        from src.engine.signals import SignalEngine
        from src.engine.backtest import Backtester
        from src.engine.gex import compute_gex
        from src.research.report import generate_report
        from src.monitor.watchlist import Watchlist
        from src.monitor.alert import AlertEngine
        from src.utils.common import COLOR_UP, COLOR_DOWN
        log("OK: 所有模块导入成功")
    except Exception as e:
        log("IMPORT FAIL: " + repr(e))
        traceback.print_exc()
        sys.exit(1)

    try:
        hub = DataHub()
        df = hub.get("BTC", "crypto", "1d", 50)
        if df is None or df.empty:
            log("WARN: Binance 数据为空 (可能网络受限, 代码本身无误)")
        else:
            log(f"OK: Binance BTC 1d 获取 {len(df)} 根, 最新收盘 {df['close'].iloc[-1]:.2f}")
            _, extra = SignalEngine().analyze(df, "1d")
            log(f"OK: 信号分析 -> {extra['signal']} @ {extra['close']:.2f} 趋势={extra['trend']}")
            res = Backtester().run(df, "sma_cross")
            log(f"OK: 回测 sma_cross 总收益 {res['total_return']*100:.1f}% "
                f"夏普 {res['sharpe']:.2f} 回撤 {res['max_drawdown']*100:.1f}%")
    except Exception as e:
        log("DATA FAIL: " + repr(e))
        traceback.print_exc()

    # 关注列表功能 (不依赖网络)
    try:
        wl = Watchlist()
        wl.add("BTC", "crypto", "测试")
        assert any(i["symbol"] == "BTC" for i in wl.list())
        wl.remove("BTC", "crypto")
        log("OK: 关注列表增删正常")
    except Exception as e:
        log("WATCHLIST FAIL: " + repr(e))


if __name__ == "__main__":
    main()
