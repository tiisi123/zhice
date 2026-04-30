"""M4D-03 公告监控 / M4D-05 AI 财报解读 / M4D-08 另类数据 / M4D-11 卖方预期时间线 / M4C-10 历史景气周期"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

# ============== 公司公告（M4D-03） ==============
_ANNOUNCEMENT_TYPES = [
    ("业绩预告", "red"), ("重大合同", "orange"), ("股东增减持", "blue"),
    ("回购预案", "green"), ("高管变动", "purple"), ("资产重组", "magenta"),
    ("分红派息", "cyan"), ("定增/可转债", "gold"),
]

_STOCK_POOL = [
    ("600519", "贵州茅台"), ("300750", "宁德时代"), ("002594", "比亚迪"),
    ("601012", "隆基绿能"), ("002475", "立讯精密"), ("000858", "五粮液"),
    ("300760", "迈瑞医疗"), ("002714", "牧原股份"), ("601888", "中国中免"),
    ("300124", "汇川技术"), ("300059", "东方财富"), ("000651", "格力电器"),
]


def list_announcements(days: int = 7, kind: str | None = None) -> list[dict]:
    rng = random.Random(42)
    today = datetime.now()
    rows: list[dict] = []
    for d in range(days):
        dt = today - timedelta(days=d)
        for _ in range(rng.randint(3, 8)):
            code, name = rng.choice(_STOCK_POOL)
            t_name, color = rng.choice(_ANNOUNCEMENT_TYPES)
            if kind and kind != t_name:
                continue
            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "code": code,
                "name": name,
                "kind": t_name,
                "color": color,
                "title": f"{name}关于{t_name}的公告",
                "impact": rng.choice(["正面", "中性", "负面"]),
                "summary": _gen_summary(t_name),
            })
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def _gen_summary(kind: str) -> str:
    mp = {
        "业绩预告": "公司预计本季度净利润同比增长 20%~35%，主营业务持续扩张。",
        "重大合同": "公司与头部客户签订战略合作协议，合同金额显著影响当期营收。",
        "股东增减持": "主要股东拟于未来 6 个月内择机增/减持不超过 2% 公司股份。",
        "回购预案": "拟使用自有资金回购公司股份，计划金额 5-10 亿元。",
        "高管变动": "公司董事、核心高管发生人事变动，经营方向或有调整。",
        "资产重组": "公司正在筹划重大资产重组，详细方案待进一步公告。",
        "分红派息": "2024 年度利润分配预案：每 10 股派发现金红利 X 元。",
        "定增/可转债": "拟发行可转债/定向增发，用于扩产能与补流。",
    }
    return mp.get(kind, "")


# ============== AI 财报解读（M4D-05） ==============
def interpret_financial(code: str, fin: dict | None) -> dict[str, Any]:
    """对财务数据做结构化解读，供 AI Agent 或前端直接展示。"""
    if not fin:
        return {"summary": "无财务数据", "highlights": [], "risks": []}
    highlights = list(fin.get("highlights") or [])
    risks = list(fin.get("risks") or [])
    # 派生规则
    roe = fin.get("roe", 0)
    pe = fin.get("pe", 0)
    rev_yoy = fin.get("revenue_yoy", 0)
    npy = fin.get("net_profit_yoy", 0)
    if roe >= 20 and "高 ROE" not in highlights:
        highlights.append(f"ROE {roe}% 处于行业前列")
    if rev_yoy >= 15 and npy >= rev_yoy:
        highlights.append(f"营收 +{rev_yoy}%、净利 +{npy}%，利润弹性优于营收")
    if pe and fin.get("pe_percentile", 50) < 30:
        highlights.append(f"当前 PE 分位 {fin['pe_percentile']}%，估值较低")
    if rev_yoy < 0 and "营收下滑" not in risks:
        risks.append("营收同比下滑，需关注行业景气")
    if fin.get("gross_margin", 0) < 20:
        risks.append(f"毛利率仅 {fin.get('gross_margin')}%，盈利能力偏弱")

    summary_lines = [
        f"## {fin.get('name','')}（{fin.get('code', code)}）财报解读",
        "",
        "### 一、核心变化",
        f"- 营收同比 {rev_yoy}%，净利同比 {npy}%",
        f"- ROE {roe}%，毛利率 {fin.get('gross_margin', '-')}%",
        f"- PE {pe}（分位 {fin.get('pe_percentile','-')}%），PB {fin.get('pb','-')}",
        "",
        "### 二、亮点",
    ] + [f"- {h}" for h in highlights] + [
        "",
        "### 三、风险",
    ] + [f"- {r}" for r in risks] + [
        "",
        "### 四、综合判断",
        _verdict(roe, rev_yoy, npy, fin.get("pe_percentile", 50)),
        "",
        "> 本解读基于公开披露数据，仅供研究参考，不构成任何投资建议。",
    ]
    return {"summary": "\n".join(summary_lines), "highlights": highlights, "risks": risks}


def _verdict(roe: float, rev: float, np_y: float, pe_pct: float) -> str:
    score = 0
    if roe >= 15: score += 1
    if rev >= 10: score += 1
    if np_y >= rev: score += 1
    if pe_pct < 40: score += 1
    if score >= 3:
        return "基本面扎实，估值合理偏低，具备中长期配置价值；短期关注盈利延续性与资金情绪。"
    if score == 2:
        return "基本面中性，需结合景气度与估值分位综合判断，适合轻仓跟踪。"
    return "基本面存在瑕疵或估值偏高，建议观望或选择更优标的。"


# ============== 另类数据监控（M4D-08） ==============
def list_alt_data(industry: str | None = None) -> list[dict]:
    rng = random.Random(7)
    catalog = [
        {"name": "高速公路货运指数", "industry": "物流", "value": 112.3, "yoy": 6.2, "trend": "up"},
        {"name": "全社会用电量", "industry": "能源", "value": 7832.0, "yoy": 5.1, "trend": "up"},
        {"name": "招聘需求指数(互联网)", "industry": "科技", "value": 89.4, "yoy": -3.6, "trend": "down"},
        {"name": "半导体晶圆价格", "industry": "半导体", "value": 1023.0, "yoy": 8.8, "trend": "up"},
        {"name": "锂精矿进口价", "industry": "锂电", "value": 765.0, "yoy": -14.2, "trend": "down"},
        {"name": "原油运价 BDTI", "industry": "能源", "value": 1120.0, "yoy": 12.4, "trend": "up"},
        {"name": "生猪存栏环比", "industry": "农业", "value": 101.2, "yoy": -1.8, "trend": "flat"},
        {"name": "新能源车周上险", "industry": "新能源车", "value": 198000, "yoy": 34.0, "trend": "up"},
        {"name": "家电零售周指数", "industry": "家电", "value": 102.5, "yoy": 2.1, "trend": "flat"},
        {"name": "医院门诊量指数", "industry": "医药", "value": 108.9, "yoy": 4.0, "trend": "up"},
    ]
    for c in catalog:
        c["delta"] = round(rng.uniform(-3, 3), 2)
    if industry:
        return [c for c in catalog if c["industry"] == industry]
    return catalog


# ============== 卖方预期时间线（M4D-11） ==============
def sellside_timeline(code: str) -> list[dict]:
    """返回最近 8 期上/下修时间线（基于伪数据生成，真实数据需对接研报源）。"""
    rng = random.Random(hash(code) & 0xFFFF)
    today = datetime.now()
    rows = []
    actions = ["维持买入", "上调至买入", "下调至增持", "维持增持", "上调目标价", "下调目标价"]
    brokers = ["中信证券", "中金公司", "华泰证券", "国泰君安", "海通证券", "招商证券", "申万宏源"]
    for i in range(8):
        dt = today - timedelta(days=i * rng.randint(5, 15))
        act = rng.choice(actions)
        rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "broker": rng.choice(brokers),
            "action": act,
            "direction": "up" if "上调" in act or act == "维持买入" else ("down" if "下调" in act else "flat"),
            "target_price": round(rng.uniform(30, 220), 2),
            "eps_revision": round(rng.uniform(-0.15, 0.2), 2),
        })
    return rows


# ============== 历史景气周期（M4C-10） ==============
def historical_prosperity(industry: str) -> dict[str, Any]:
    """返回给定行业 2017-至今 季度景气度轨迹 + 当前相对位置。"""
    rng = random.Random(hash(industry) & 0xFFFF)
    start = datetime(2017, 1, 1)
    rows = []
    base = 50
    for q in range(0, 34):  # ~8 年季度
        base += rng.uniform(-8, 8)
        base = max(10, min(95, base))
        dt = start + timedelta(days=q * 91)
        q_label = f"{dt.year}Q{((dt.month - 1) // 3) + 1}"
        rows.append({"period": q_label, "score": round(base, 1)})
    current = rows[-1]["score"]
    peaks = sorted(rows, key=lambda r: r["score"], reverse=True)[:3]
    troughs = sorted(rows, key=lambda r: r["score"])[:3]
    pct = sum(1 for r in rows if r["score"] <= current) / len(rows) * 100
    return {
        "industry": industry,
        "trajectory": rows,
        "current": current,
        "percentile": round(pct, 1),
        "peaks": peaks,
        "troughs": troughs,
        "interpretation": (
            f"当前 {industry} 景气度 {current}，位于近 8 年 {round(pct)}% 分位，"
            + ("属高位区域，需防止景气拐头。" if pct >= 70 else "属中等区间，有结构性机会。" if pct >= 30 else "属底部区域，具备中长期配置价值。")
        ),
    }
