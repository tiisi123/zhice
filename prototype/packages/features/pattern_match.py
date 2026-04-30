"""
K 线形态匹配（PRD M4A-06 强势股模式匹配）。

输入：个股代码 + 近 N 日归一化 K 线序列。
输出：在历史"牛股形态库"中找出 Top-K 相似形态，附带后续 N 日涨幅统计。

实施说明：
- 查询序列由接口层注入真实历史日 K，当前使用 TuShare daily。
- 距离度量：归一化欧氏距离（先做 z-score）。
"""

from __future__ import annotations

import math
from typing import Iterable


# 预设历史"牛股形态库"：每条 30 天归一化 close 序列 + 后续 5/10/20 日累计涨幅
HISTORY_PATTERNS: list[dict] = [
    {
        "id": "P001", "name": "首板放量启动", "stock": "金山办公(2020)",
        "seq": [0.0, 0.5, 1.0, 0.8, 1.2, 1.5, 2.0, 2.8, 4.0, 5.5,
                7.2, 9.0, 11.5, 14.0, 17.0, 20.5, 24.0, 28.0, 32.0, 35.0,
                33.0, 31.0, 29.0, 27.5, 26.0, 25.0, 24.0, 23.5, 24.0, 25.5],
        "future": {"d5": 8.5, "d10": 15.2, "d20": 22.0, "win_rate": 78},
    },
    {
        "id": "P002", "name": "高位横盘突破", "stock": "中际旭创(2023)",
        "seq": [0.0, 1.0, 2.0, 1.5, 2.5, 3.0, 2.8, 3.5, 3.2, 4.0,
                4.5, 4.0, 4.8, 5.5, 6.0, 5.5, 6.2, 7.0, 8.5, 11.0,
                13.5, 16.0, 18.5, 21.0, 23.0, 24.5, 25.5, 26.0, 25.5, 26.5],
        "future": {"d5": 6.2, "d10": 11.0, "d20": 18.5, "win_rate": 72},
    },
    {
        "id": "P003", "name": "深 V 反转", "stock": "宁德时代(2022)",
        "seq": [0.0, -2.0, -4.5, -7.0, -10.0, -12.5, -15.0, -16.5, -17.0, -16.5,
                -15.0, -12.5, -10.0, -7.0, -4.5, -2.0, 0.5, 3.0, 5.5, 8.0,
                10.5, 13.0, 15.0, 17.5, 20.0, 21.5, 23.0, 24.0, 25.0, 26.0],
        "future": {"d5": 5.5, "d10": 9.5, "d20": 14.5, "win_rate": 65},
    },
    {
        "id": "P004", "name": "连板首阴回踩", "stock": "光迅科技(2024)",
        "seq": [0.0, 5.0, 10.5, 15.0, 19.5, 22.0, 21.0, 19.5, 18.0, 17.0,
                16.5, 17.5, 19.0, 21.0, 23.0, 25.5, 28.0, 31.0, 34.5, 38.0,
                36.0, 34.5, 35.0, 36.5, 38.0, 40.0, 42.0, 44.0, 45.5, 47.0],
        "future": {"d5": 7.8, "d10": 13.0, "d20": 19.5, "win_rate": 71},
    },
    {
        "id": "P005", "name": "圆弧底放量", "stock": "通威股份(2021)",
        "seq": [0.0, -1.0, -2.5, -3.5, -4.0, -4.2, -4.0, -3.5, -3.0, -2.5,
                -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.5, 2.5, 4.0, 5.5,
                7.0, 9.0, 11.0, 13.5, 16.0, 18.5, 21.0, 23.0, 24.5, 26.0],
        "future": {"d5": 4.5, "d10": 8.5, "d20": 13.0, "win_rate": 62},
    },
    {
        "id": "P006", "name": "破位假摔反包", "stock": "比亚迪(2023)",
        "seq": [0.0, 2.0, 1.5, 3.0, 2.0, 1.0, 0.0, -1.5, -3.0, -4.5,
                -5.5, -4.0, -2.5, 0.0, 2.5, 4.5, 6.5, 8.0, 9.5, 11.0,
                12.5, 14.0, 15.5, 17.0, 18.5, 19.5, 20.5, 21.0, 21.5, 22.0],
        "future": {"d5": 4.0, "d10": 7.5, "d20": 11.5, "win_rate": 58},
    },
    {
        "id": "P007", "name": "高潮加速冲顶", "stock": "鸿博股份(2023)",
        "seq": [0.0, 3.0, 7.0, 12.0, 18.0, 25.0, 33.0, 42.0, 52.0, 60.0,
                65.0, 68.0, 70.0, 71.0, 70.5, 69.0, 66.0, 62.0, 57.0, 51.0,
                45.0, 40.0, 36.0, 33.0, 31.0, 30.0, 29.5, 29.0, 28.5, 28.0],
        "future": {"d5": -8.5, "d10": -15.0, "d20": -22.0, "win_rate": 25},
    },
    {
        "id": "P008", "name": "低位涨停启动", "stock": "汤姆猫(2023)",
        "seq": [0.0, 0.5, 1.0, 0.8, 1.2, 0.9, 1.5, 2.0, 2.5, 3.0,
                4.5, 6.5, 9.0, 12.0, 15.5, 19.0, 22.5, 25.5, 28.0, 30.0,
                31.5, 32.5, 33.0, 33.5, 34.0, 34.5, 35.0, 35.5, 36.0, 36.5],
        "future": {"d5": 9.0, "d10": 16.5, "d20": 24.0, "win_rate": 75},
    },
]


def _zscore(seq: list[float]) -> list[float]:
    n = len(seq)
    if n == 0:
        return []
    mean = sum(seq) / n
    var = sum((x - mean) ** 2 for x in seq) / max(n - 1, 1)
    std = math.sqrt(var) if var > 0 else 1.0
    return [(x - mean) / std for x in seq]


def _euclidean(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return float("inf")
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(n)) / n)


def match_patterns(
    query_seq: list[float], top_k: int = 5,
    library: Iterable[dict] | None = None,
) -> list[dict]:
    """
    返回与查询序列最相似的 Top-K 历史形态，附带相似度评分（0-100）和后续表现。
    """
    if not query_seq:
        return []
    q = _zscore(query_seq)
    pool = list(library) if library is not None else HISTORY_PATTERNS
    scored: list[tuple[float, dict]] = []
    for p in pool:
        seq = p.get("seq", [])
        if len(seq) < 10:
            continue
        # 重采样到查询长度
        if len(seq) != len(q):
            seq = _resample(seq, len(q))
        ref = _zscore(seq)
        d = _euclidean(q, ref)
        scored.append((d, p))

    scored.sort(key=lambda x: x[0])
    out = []
    if not scored:
        return out
    # 把距离归一化到 0-100 相似度（最佳=100，最差=0）
    max_d = max(s[0] for s in scored) or 1.0
    min_d = min(s[0] for s in scored)
    span = max_d - min_d or 1.0
    for d, p in scored[:top_k]:
        sim = round(100 * (1 - (d - min_d) / span), 1)
        out.append({
            "id": p["id"],
            "name": p["name"],
            "stock": p.get("stock", ""),
            "similarity": sim,
            "distance": round(d, 4),
            "future": p.get("future", {}),
            "seq": p.get("seq", []),
        })
    return out


def _resample(seq: list[float], target_len: int) -> list[float]:
    """线性插值把 seq 重采样到 target_len。"""
    n = len(seq)
    if n == target_len or n == 0:
        return list(seq)
    out = []
    for i in range(target_len):
        pos = i * (n - 1) / (target_len - 1) if target_len > 1 else 0
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        out.append(seq[lo] * (1 - frac) + seq[hi] * frac)
    return out


def aggregate_outlook(matches: list[dict]) -> dict:
    """从 Top-K 匹配中加权聚合后续表现：相似度作权重。"""
    if not matches:
        return {}
    weights = [m["similarity"] for m in matches]
    total_w = sum(weights) or 1.0

    def wavg(key: str) -> float:
        s = 0.0
        for m, w in zip(matches, weights):
            v = m["future"].get(key)
            if v is not None:
                s += v * w
        return round(s / total_w, 2)

    return {
        "expected_d5": wavg("d5"),
        "expected_d10": wavg("d10"),
        "expected_d20": wavg("d20"),
        "avg_win_rate": wavg("win_rate"),
        "n_samples": len(matches),
    }
