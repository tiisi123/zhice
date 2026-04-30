"""策略实验室：策略对比（M3-07）+ 自定义打板规则（M4A-10）+ 多风格组合（M4E-04/05）。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.auth import current_user, consume_quota, update_style
from apps.api.db import execute, query_one, query_all
from apps.api.utils.contract import wrap_contract
from packages.backtest.dsl_schema import StrategyDSL, STRATEGY_TEMPLATES
from packages.backtest.engine import BacktestEngine
from packages.connectors.registry import get_kpl

router = APIRouter()

_engine = BacktestEngine()
_kpl = get_kpl()


# ============== M3-07 策略对比 ==============
class CompareIn(BaseModel):
    # 两种来源：templates=模板名列表；dsls=DSL 列表
    templates: list[str] | None = None
    dsls: list[dict] | None = None
    years: int = 3


@router.post("/compare")
def compare_strategies(inp: CompareIn, _user: dict = Depends(consume_quota("backtest"))):
    if not inp.templates and not inp.dsls:
        raise HTTPException(status_code=400, detail="请提供 templates 或 dsls")
    items: list[tuple[str, StrategyDSL]] = []
    if inp.templates:
        for name in inp.templates[:5]:
            dsl = STRATEGY_TEMPLATES.get(name)
            if not dsl:
                raise HTTPException(status_code=404, detail=f"模板 '{name}' 不存在")
            items.append((name, dsl))
    if inp.dsls:
        for i, d in enumerate(inp.dsls[:5]):
            try:
                dsl = StrategyDSL(**d)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"第 {i+1} 个 DSL 非法: {e}")
            items.append((d.get("name") or f"自定义#{i+1}", dsl))
    if len(items) > 5:
        items = items[:5]

    results = []
    for name, dsl in items:
        r = _engine.run(dsl, inp.years).to_dict()
        r["strategy_name"] = name
        results.append(r)

    # 综合评分：夏普 0.5 + 胜率/100 * 0.3 + (1 - |回撤|/30) * 0.2
    def score(r: dict) -> float:
        sh = r.get("sharpe_ratio") or 0
        wr = (r.get("win_rate") or 0) / 100
        dd = min(abs(r.get("max_drawdown") or 0), 30) / 30
        return round(sh * 0.5 + wr * 0.3 + (1 - dd) * 0.2, 3)

    for r in results:
        r["composite_score"] = score(r)
    ranked = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    return {
        "results": results,
        "ranked": [r["strategy_name"] for r in ranked],
        "winner": ranked[0]["strategy_name"] if ranked else None,
    }


# ============== M4A-10 自定义打板规则 ==============
class AlertRule(BaseModel):
    id: int | None = None
    name: str
    kind: str = "limit_up"  # limit_up / broken / anomaly
    seal_amount_gte: int | None = None           # 封单金额 ≥ 单位 元
    turnover_ratio_lte: float | None = None      # 换手率 ≤
    board_count_gte: int | None = None           # 连板数 ≥
    market_cap_lte: float | None = None          # 流通市值 ≤ 亿
    theme_rank_top: int | None = None            # 所属题材排名 ≤ top N
    enabled: bool = True


@router.get("/alert-rules")
def list_rules(user: dict = Depends(current_user)):
    try:
        rows = query_all(
            "SELECT id, name, kind, rules, enabled, created_at FROM alert_rules WHERE user_id=? ORDER BY id DESC",
            (user["id"],),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="mysql_lab",
            status="unavailable",
            message=f"获取告警规则失败: {str(e)}",
            items=[],
            count=0,
        )
    for r in rows:
        try:
            r["rules"] = json.loads(r["rules"])
        except Exception:
            r["rules"] = {}
    return wrap_contract(
        rows,
        source="mysql_lab",
        status="real",
        items=rows,
        count=len(rows),
    )


@router.post("/alert-rules")
def save_rule(rule: AlertRule, user: dict = Depends(current_user)):
    payload = rule.model_dump(exclude={"id", "name", "kind", "enabled"})
    rules_json = json.dumps(payload, ensure_ascii=False)
    if rule.id:
        execute(
            "UPDATE alert_rules SET name=?, kind=?, rules=?, enabled=? WHERE id=? AND user_id=?",
            (rule.name, rule.kind, rules_json, 1 if rule.enabled else 0, rule.id, user["id"]),
        )
        return {"ok": True, "id": rule.id}
    new_id = execute(
        "INSERT INTO alert_rules(user_id, name, kind, rules, enabled) VALUES (?,?,?,?,?)",
        (user["id"], rule.name, rule.kind, rules_json, 1 if rule.enabled else 0),
    )
    return {"ok": True, "id": new_id}


@router.delete("/alert-rules/{rid}")
def delete_rule(rid: int, user: dict = Depends(current_user)):
    execute("DELETE FROM alert_rules WHERE id=? AND user_id=?", (rid, user["id"]))
    return {"ok": True}


@router.post("/alert-rules/{rid}/evaluate")
def evaluate_rule(rid: int, user: dict = Depends(current_user)):
    """用当日涨停池数据评估命中。"""
    row = query_one("SELECT rules, kind FROM alert_rules WHERE id=? AND user_id=?", (rid, user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="规则不存在")
    try:
        rules = json.loads(row["rules"])
    except Exception:
        rules = {}
    trade_date = datetime.now().strftime("%Y-%m-%d")
    pool = _kpl.get_limit_up(trade_date) or []
    matches: list[dict] = []
    for s in pool:
        if rules.get("seal_amount_gte") is not None and float(s.get("seal_amount") or 0) < rules["seal_amount_gte"]:
            continue
        if rules.get("turnover_ratio_lte") is not None and float(s.get("turnover_ratio") or 0) > rules["turnover_ratio_lte"]:
            continue
        if rules.get("board_count_gte") is not None and int(s.get("board_count") or 0) < rules["board_count_gte"]:
            continue
        if rules.get("market_cap_lte") is not None:
            cap = float(s.get("non_restricted_capital") or 0) / 1e8
            if cap > rules["market_cap_lte"]:
                continue
        matches.append(s)
    return {"trade_date": trade_date, "total": len(pool), "match_count": len(matches), "matches": matches[:50]}


# ============== M4E-04 多风格组合 ==============
class ComboIn(BaseModel):
    styles: list[str]


_ALLOWED = {"short", "hot", "growth", "value"}


@router.get("/style-combo")
def get_combo(user: dict = Depends(current_user)):
    try:
        row = query_one("SELECT styles FROM style_combo WHERE user_id=?", (user["id"],))
    except Exception as e:
        fallback = [user["style"]]
        return wrap_contract(
            fallback,
            source="mysql_lab",
            status="unavailable",
            message=f"获取风格组合失败: {str(e)}",
            styles=fallback,
        )
    if not row:
        styles = [user["style"]]
        return wrap_contract(
            styles,
            source="mysql_lab",
            status="real",
            styles=styles,
        )
    try:
        styles = json.loads(row["styles"])
    except Exception:
        styles = [user["style"]]
    return wrap_contract(
        styles,
        source="mysql_lab",
        status="real",
        styles=styles,
    )


@router.post("/style-combo")
def save_combo(inp: ComboIn, user: dict = Depends(current_user)):
    styles = [s for s in inp.styles if s in _ALLOWED]
    if not styles:
        raise HTTPException(status_code=400, detail="至少选择一个风格")
    payload = json.dumps(styles, ensure_ascii=False)
    row = query_one("SELECT user_id FROM style_combo WHERE user_id=?", (user["id"],))
    if row:
        execute("UPDATE style_combo SET styles=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (payload, user["id"]))
    else:
        execute("INSERT INTO style_combo(user_id, styles) VALUES (?,?)", (user["id"], payload))
    # 主风格 = 第一个
    update_style(user["id"], styles[0])
    return {"ok": True, "styles": styles, "primary": styles[0]}


# ============== M4E-05 风格学习：应用行为识别结果 ==============
@router.post("/style-learn/apply")
def apply_detected_style(user: dict = Depends(current_user)):
    from collections import Counter
    rows = query_all("SELECT page FROM events WHERE user_id=? ORDER BY id DESC LIMIT 300", (user["id"],))
    mapping = {
        "/replay": "short", "/intraday": "short", "/sentiment": "short", "/broken-cases": "short", "/longhu": "short",
        "/theme": "hot", "/chain": "hot", "/rotation": "hot",
        "/growth": "growth", "/etf-rotation": "growth", "/prosperity": "growth",
        "/value": "value", "/valuation": "value", "/research": "value",
    }
    c: Counter[str] = Counter()
    for r in rows:
        p = r.get("page") or ""
        for k, v in mapping.items():
            if p.startswith(k):
                c[v] += 1
                break
    if not c:
        return {"applied": False, "reason": "行为样本不足"}
    top = c.most_common(1)[0][0]
    update_style(user["id"], top)
    return {"applied": True, "style": top, "votes": dict(c)}
