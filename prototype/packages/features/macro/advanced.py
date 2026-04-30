from __future__ import annotations


def calc_diffusion_index(industries: list[dict]) -> dict:
    up = [i for i in industries if i["trend"] == "up"]
    flat = [i for i in industries if i["trend"] == "flat"]
    down = [i for i in industries if i["trend"] == "down"]
    total = len(industries)
    idx = round((len(up) + len(flat) * 0.5) / total * 100, 1) if total else 50.0
    return {
        "diffusion_index": idx,
        "up_count": len(up),
        "flat_count": len(flat),
        "down_count": len(down),
        "total": total,
        "interpretation": "扩张" if idx > 60 else "收缩" if idx < 40 else "中性",
    }


def detect_turning_points(industries: list[dict], threshold: int = 10) -> list[dict]:
    alerts = []
    for ind in industries:
        q3 = ind.get("q3", 0)
        q4 = ind.get("q4", 0)
        delta = q4 - q3
        if abs(delta) >= threshold:
            direction = "向上拐点" if delta > 0 else "向下拐点"
            alerts.append({
                "industry": ind["industry"],
                "direction": direction,
                "q3": q3,
                "q4": q4,
                "delta": delta,
                "level": ind.get("level", ""),
                "severity": "high" if abs(delta) >= 15 else "medium",
            })
    return alerts


def macro_to_industry_transmission(macro_change: str) -> list[dict]:
    transmissions = {
        "PMI上升": [
            {"layer": "宏观", "signal": "PMI回升至荣枯线上方", "lag": "即时"},
            {"layer": "中观-制造业", "signal": "订单增加、开工率提升", "lag": "1-2月"},
            {"layer": "中观-原材料", "signal": "需求拉动价格上行", "lag": "1-3月"},
            {"layer": "微观-设备商", "signal": "产能利用率提升、新增投资", "lag": "3-6月"},
        ],
        "CPI上升": [
            {"layer": "宏观", "signal": "通胀预期升温", "lag": "即时"},
            {"layer": "中观-消费", "signal": "提价预期、渠道补库", "lag": "1月"},
            {"layer": "中观-食品", "signal": "猪肉/蔬菜价格传导", "lag": "即时"},
            {"layer": "微观-消费龙头", "signal": "收入增长、估值修复", "lag": "1-3月"},
        ],
        "利率下调": [
            {"layer": "宏观", "signal": "LPR下调、流动性宽松", "lag": "即时"},
            {"layer": "中观-地产", "signal": "按揭成本降低、销售回暖", "lag": "1-3月"},
            {"layer": "中观-基建", "signal": "融资成本下降、项目加速", "lag": "2-4月"},
            {"layer": "微观-银行", "signal": "息差收窄但规模扩张", "lag": "1-2季"},
        ],
    }
    return transmissions.get(macro_change, [{"layer": "未知", "signal": "无匹配的传导路径", "lag": ""}])


def chain_prosperity_transmission(chain_name: str) -> list[dict]:
    chains = {
        "半导体": [
            {"stream": "上游-设备材料", "prosperity": 85, "signal": "国产替代加速，订单饱满"},
            {"stream": "中游-设计制造", "prosperity": 78, "signal": "产能利用率回升"},
            {"stream": "下游-封测应用", "prosperity": 72, "signal": "需求跟随回暖，滞后1-2季"},
        ],
        "新能源车": [
            {"stream": "上游-锂矿材料", "prosperity": 50, "signal": "锂价低位，材料企业承压"},
            {"stream": "中游-电池", "prosperity": 65, "signal": "量增价跌，以量换利"},
            {"stream": "下游-整车充电", "prosperity": 75, "signal": "渗透率持续提升"},
        ],
        "AI人工智能": [
            {"stream": "上游-芯片算力", "prosperity": 90, "signal": "算力需求爆发，供不应求"},
            {"stream": "中游-大模型", "prosperity": 80, "signal": "模型能力快速迭代"},
            {"stream": "下游-应用", "prosperity": 60, "signal": "商业化落地中，收入尚待验证"},
        ],
    }
    return chains.get(chain_name, [])
