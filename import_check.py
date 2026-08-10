"""CI 导入冒烟测试: 显式将仓库根加入 sys.path 后导入全部 src 子模块。

比 `python -c` 更稳健: 脚本自身的目录即仓库根, 会被插入到 sys.path[0],
避免 CI 环境下 -c 的 cwd 语义歧义, 并附带诊断输出以便定位冲突的 src 命名空间。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _find_competing_src():
    hits = []
    for p in sys.path:
        base = p or os.getcwd()
        cand = os.path.join(base, "src")
        if os.path.isdir(cand):
            hits.append((base, sorted(os.listdir(cand))[:14]))
    return hits


try:
    import src.data.unified  # noqa: F401
    import src.data.realtime  # noqa: F401
    import src.engine.signals  # noqa: F401
    import src.engine.backtest  # noqa: F401
    import src.engine.gex  # noqa: F401
    import src.research.report  # noqa: F401
    import src.research.backtest_report  # noqa: F401
    import src.monitor.watchlist  # noqa: F401
    import src.monitor.alert  # noqa: F401
    import src.utils.common  # noqa: F401
    print("imports OK")
except Exception as e:  # noqa: BLE001
    print("IMPORT FAILED:", repr(e))
    print("sys.path[:12]:", sys.path[:12])
    print("competing src dirs:", _find_competing_src())
    raise
